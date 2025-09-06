import asyncio
import logging
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from typing import List

from src.core.state import GlobalState, AgentName, \
    ValidationStatus, ReportSection, Doc
from src.external_knowledge.deep_search import DeepSearch
from src.llm_adapter import llm_client
from src.utils.observability import user_friendly_progress_event, measure
from src.utils.prompt import BASE_REPORT_SYSTEM_PROMPT, KNOWLEDGE_SECTION_USER_PROMPT

logger = logging.getLogger(__name__)


def update_section_draft_report(state, section, section_content):
    draft_report = state.get('draft_report') or ""
    separator = "\n\n" if draft_report else ""
    draft_report = f"{draft_report}{separator}[{section.title}]\n{section_content}"
    state['draft_report'] = draft_report


@measure("agent.knowledge_retrieval")
def knowledge_retrieval_node(state: GlobalState) -> GlobalState:
    logger.info("执行知识提取与论证 Agent")

    processed_sections = list(state.get("processed_sections", []))
    try:
        if not state.get("structure"):
            error_state = {
                **state,
                "current_agent": AgentName.KNOWLEDGE,
                "error_message": "无法提取知识：缺少报告结构",
                "validation_status": ValidationStatus.FAILED,
                "last_updated": state.get("start_time") or state.get(
                    "last_updated")
            }
            return GlobalState(**error_state)

        report_structure = state['structure']

        # 如果所有章节均已处理，直接返回（重入保护）
        if report_structure.sections and len(processed_sections) >= len(report_structure.sections):
            return GlobalState(**{
                **state,
                "current_agent": AgentName.KNOWLEDGE,
            })

        user_friendly_progress_event("agent.knowledge_retrieval", "external_search_start")
        external_resources = asyncio.run(DeepSearch().run(state['user_query']))
        user_friendly_progress_event("agent.knowledge_retrieval", "external_search_done", 
                      docs=len(external_resources), 
                      doc_titles=[doc.title for doc in external_resources[:5]])  # 前5个文档标题
        # 章节受限并发生成（线程池，避免事件循环依赖）
        concurrency = int(os.getenv("SECTION_CONCURRENCY", 2))
        tasks = []
        with ThreadPoolExecutor(max_workers=concurrency) as executor:
            for section in report_structure.sections:
                if section.title in processed_sections:
                    continue
                def _work(sec: ReportSection):
                    logger.info(f"正在处理章节: {sec.title}")
                    state["active_section"] = sec.title
                    state["last_updated"] = datetime.now()
                    content = generate_final_content(sec, state, external_resources)
                    return (sec.title, content)
                tasks.append(executor.submit(_work, section))

            for fut in as_completed(tasks):
                title, content = fut.result()
                user_friendly_progress_event("agent.knowledge_retrieval", "section_done", 
                              title=title, content_length=len(content))
                update_section_draft_report(state, ReportSection(title=title, key_questions=[], content=""), content)
                processed_sections.append(title)

        updated_state = {
            **state,
            "current_agent": AgentName.KNOWLEDGE,
            "last_updated": datetime.now(),
            "warnings": state.get("warnings", []),
            "processed_sections": processed_sections
        }

        logger.info(f"知识提取完成，共处理{len(processed_sections)}个章节")
        return GlobalState(**updated_state)
    except Exception as e:
        logger.exception(f"知识提取过程中出现错误: {str(e)}")
        from src.utils.agent_utils import create_error_state
        return create_error_state(
            state,
            AgentName.KNOWLEDGE,
            f"知识提取失败: {str(e)}",
            ValidationStatus.FAILED
        )


def generate_final_content(section: ReportSection,
                                  state: GlobalState,
                                  external_sources: List[
                                      Doc]) -> str:
    """生成最终的章节内容"""
    try:
        requirements = state['requirements']
        print(f"Requirements type: {type(requirements)}")
        print(f"Requirements: {requirements}")
        
        # 处理不同的 requirements 类型
        if hasattr(requirements, 'domain'):
            # 如果是 AnalysisQuery 对象
            domain = requirements.domain.value if hasattr(requirements.domain, 'value') else str(requirements.domain)
        elif isinstance(requirements, dict) and 'domain' in requirements:
            # 如果是字典
            domain = requirements['domain']
        else:
            # 默认值
            domain = "通用"
        
        print(f"Domain: {domain}")
        base_prompt = BASE_REPORT_SYSTEM_PROMPT.format(domain=domain)

        # 准备输入数据
        external_summary = format_external_sources(external_sources)
        input_data = {
            "query": state['user_query'],
            "title": section.title,
            "key_questions": ";".join(section.key_questions),
            "external_summary": external_summary
        }

        # 构建完整的提示
        user_prompt = KNOWLEDGE_SECTION_USER_PROMPT.format(
            query=input_data['query'],
            title=input_data['title'],
            key_questions=input_data['key_questions'],
            external_summary=input_data['external_summary']
        )
        full_prompt = f"{base_prompt}\n\n{user_prompt}"
        
        # 使用统一的LLM调用
        from src.utils.llm_utils import call_llm_sync
        response_content = call_llm_sync(
            prompt=full_prompt,
            agent_name="agent.knowledge_retrieval"
        )
        print(f"{section.title}生成的内容：{response_content}")
        return response_content

    except Exception as e:
        logger.exception(f"生成最终内容失败: {str(e)}")
        raise

def format_external_sources(sources: List[Doc]) -> str:
    """格式化外部知识源"""
    if not sources:
        return "无外部信息"

    formatted = []
    for i, source in enumerate(sources, 1):
        formatted.append(
            f"来源{i} ({source.doc_type}): {source.title or '无标题'}\n"
            f"链接: {source.link or '无链接'}\n"
            f"摘要: {source.content}\n"
        )

    return "\n---\n".join(formatted)


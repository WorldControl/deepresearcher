import logging

from langchain_core.output_parsers import JsonOutputParser

from src import utils
from src.core.state import GlobalState, AgentName, ValidationStatus, \
    ReportStructure, ReportSection
from src.llm_adapter import llm_client
from src.utils.observability import measure, user_friendly_progress_event
from src.utils.prompt import STRUCTURE_DESIGN_SYSTEM_PROMPT, STRUCTURE_DESIGN_USER_PROMPT
from src.utils.template_manager import TemplateManager

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@measure("agent.structure_planning")
def structure_planning_node(state: GlobalState) -> GlobalState:
    logger.info("执行报告结构规划 Agent")
    try:
        user_friendly_progress_event("agent.structure_planning", "start")
        # 重入保护：已有 structure 则跳过
        if state.get("structure"):
            user_friendly_progress_event("agent.structure_planning", "skip", reason="structure exists")
            return GlobalState(**{
                **state,
                "current_agent": AgentName.STRUCTURING,
            })

        if not state.get("requirements"):
            error_state = {
                **state,
                "current_agent": AgentName.STRUCTURING,
                "error_message": "无法生成报告结构：缺少题目解析结果",
                "validation_status": ValidationStatus.FAILED,
                "last_updated": state.get("start_time") or state.get(
                    "last_updated")
            }
            return GlobalState(**error_state)

        # 统一读取 requirements，兼容 pydantic 模型/字典
        requirements = state['requirements']
        if hasattr(requirements, 'domain'):
            domain = requirements.domain
        else:
            domain = requirements['domain']
        if hasattr(requirements, 'analysis_intent'):
            analysis_intent = requirements.analysis_intent
        else:
            analysis_intent = requirements['analysis_intent']

        template_manager = TemplateManager()
        sections = template_manager.create_report_structure(
            analysis_intent, domain
        )
        template_sections = "\n".join([
            f"- {section.title}: {', '.join(section.key_questions)}"
            for section in sections
        ])

        # 构建完整的提示
        user_prompt = STRUCTURE_DESIGN_USER_PROMPT.format(
            user_query=state['user_query'],
            domain=domain,
            analysis_intent=analysis_intent,
            template_sections=template_sections
        )
        full_prompt = f"{STRUCTURE_DESIGN_SYSTEM_PROMPT}\n\n{user_prompt}"
        
        # 使用统一的LLM调用
        from src.utils.llm_utils import call_llm_sync
        response_content = call_llm_sync(
            prompt=full_prompt,
            agent_name="agent.structure_planning"
        )
        
        # 解析结果
        parser = JsonOutputParser()
        response_data = parser.parse(utils.rm_think(response_content))
        
        sections = []
        for section_data in response_data:
            section = ReportSection(
                title=section_data["title"],
                key_questions=section_data["key_questions"],
                content="",
                status="outlined"
            )
            sections.append(section)
        
        user_friendly_progress_event("agent.structure_planning", "parse_result", 
                      sections_count=len(sections), sections=[s.title for s in sections])

        report_structure = ReportStructure(
                template_type=analysis_intent,
                sections=sections,
                executive_summary_required=True,
                recommendations_required=True,
                target_length=state['word_limit']
            )

        updated_state = {
            **state,
            "structure": report_structure,
            "current_agent": AgentName.STRUCTURING,
            "last_updated": state.get("start_time") or state.get("last_updated"),
            "warnings": state.get("warnings", [])
        }
        logger.info(
            f"报告结构规划完成，共{len(report_structure.sections)}个章节")

        user_friendly_progress_event("agent.structure_planning", "done", sections=len(sections))
        return GlobalState(**updated_state)
    except Exception as e:
        logger.exception(f"报告结构规划过程中出现错误: {str(e)}")
        from src.utils.agent_utils import create_error_state
        return create_error_state(
            state,
            AgentName.STRUCTURING,
            f"报告结构规划失败: {str(e)}",
            ValidationStatus.FAILED
        )

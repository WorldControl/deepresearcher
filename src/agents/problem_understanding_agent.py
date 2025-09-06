"""
题目解析与意图理解 Agent
"""

import logging

from langchain_core.output_parsers import JsonOutputParser

from src import utils
from src.core.state import GlobalState, AnalysisQuery, DomainCategory, AnalysisIntent, ValidationStatus, AgentName
from src.llm_adapter import llm_client
from src.utils.domain_classifier import (
    classify_domain_rule_based, classify_intent_rule_based,
)
from src.utils.observability import measure, user_friendly_progress_event
from src.utils.prompt import DOMAIN_INTENT_CLASSIFY_PROMPT

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DOMAIN_CONFIDENCE_THRESHOLD = 0.7  # 领域识别置信度阈值
INTENT_CONFIDENCE_THRESHOLD = 0.6  # 意图识别置信度阈值


@measure("agent.problem_understanding")
def problem_understanding_node(state: GlobalState) -> GlobalState:
    logger.info("开始识别领域和意图")
    print("执行题目解析与意图识别Agent")
    try:
        user_friendly_progress_event("agent.problem_understanding", "start")
        # 重入保护：已存在 requirements 则跳过
        if state.get('requirements'):
            user_friendly_progress_event("agent.problem_understanding", "skip", reason="requirements exists")
            return GlobalState(**{
                **state,
                'current_agent': AgentName.UNDERSTANDING,
            })

        query = state['user_query']

        domain, domain_confidence, domain_matched_keywords = classify_domain_rule_based(query)

        intent, intent_confidence, intent_matched_keywords = classify_intent_rule_based(query)

        logger.info(
            f"规则识别结果 - 领域置信度: {domain_confidence:.2f}, 意图置信度: {intent_confidence:.2f}")

        # 2. 决策逻辑：领域和意图分别判断
        use_rule_domain = domain_confidence >= DOMAIN_CONFIDENCE_THRESHOLD
        use_rule_intent = intent_confidence >= INTENT_CONFIDENCE_THRESHOLD

        existing_analysis_parts = []
        if use_rule_intent and use_rule_domain:
            requirements = AnalysisQuery(
                domain=DomainCategory(domain) or DomainCategory.GENERAL,
                analysis_intent=AnalysisIntent(intent) or AnalysisIntent.OVERVIEW
            )
            updated_state = {
                **state,
                'requirements': requirements,
                'current_agent': AgentName.UNDERSTANDING,
                "last_updated": state.get("start_time") or state.get("last_updated"),
                    "warnings": state.get("warnings", []) + [
                        f"使用规则识别，领域置信度: {domain_confidence:.2f}, 意图置信度: {intent_confidence:.2f}"
                    ]
            }
            user_friendly_progress_event("agent.problem_understanding", "done", method="rule", 
                          domain=domain, intent=intent, domain_confidence=domain_confidence, intent_confidence=intent_confidence)
            return GlobalState(**updated_state)
        elif use_rule_domain:
            existing_analysis_parts.append(f"✅ 高置信度领域识别: {domain} (置信度: {domain_confidence:.2f})")
            existing_analysis_parts.append(f"✅ 匹配的领域关键词: {', '.join(domain_matched_keywords)}")
        elif use_rule_intent:
            existing_analysis_parts.append(f"✅ 高置信度意图识别: {intent} (置信度: {intent_confidence:.2f})")
            existing_analysis_parts.append(f"✅ 匹配的意图关键词: {', '.join(intent_matched_keywords)}")

        existing_analysis = "\n".join(existing_analysis_parts) if (
            existing_analysis_parts) else "无可用的规则分析结果"
        print(f"规则分析结果：{existing_analysis}")
        system_prompt = DOMAIN_INTENT_CLASSIFY_PROMPT.replace("{existing_analysis}", existing_analysis)

        # 构建完整的提示
        full_prompt = f"{system_prompt}\n\n请分析以下报告题目：{query}"
        
        # 使用统一的LLM调用
        from src.utils.llm_utils import call_llm_sync
        response_content = call_llm_sync(
            prompt=full_prompt,
            agent_name="agent.problem_understanding"
        )
        
        # 解析结果
        parser = JsonOutputParser(pydantic_object=AnalysisQuery)
        requirements = parser.parse(utils.format_result(response_content))
        user_friendly_progress_event("agent.problem_understanding", "parse_result", 
                      domain=requirements.get("domain") if isinstance(requirements, dict) else requirements.domain, 
                      intent=requirements.get("analysis_intent") if isinstance(requirements, dict) else requirements.analysis_intent)
        
        updated_state = {
            **state,
            'requirements': requirements,
            'current_agent': AgentName.UNDERSTANDING,
            "last_updated": state.get("start_time") or state.get("last_updated"),
        }
        user_friendly_progress_event("agent.problem_understanding", "done", method="llm",
                      domain=requirements.get("domain") if isinstance(requirements, dict) else requirements.domain, 
                      intent=requirements.get("analysis_intent") if isinstance(requirements, dict) else requirements.analysis_intent)
        return GlobalState(**updated_state)
    except Exception as e:
        logger.exception(f"ERROR {e}")
        logger.error(f"题目解析过程中出现错误: {str(e)}")
        from src.utils.agent_utils import create_error_state
        return create_error_state(
            state,
            AgentName.UNDERSTANDING,
            f"题目解析失败: {str(e)}",
            ValidationStatus.FAILED
        )

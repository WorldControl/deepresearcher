# src/agents/validation.py
"""
质量校验 Agent
负责对最终报告进行严格审核
"""
import logging
from datetime import datetime

from src.core.state import GlobalState, ValidationStatus, AgentName
from src.utils.observability import measure, user_friendly_progress_event
from src.utils.quality_system import evaluate_report_quality, should_report_pass_quality_check

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@measure("agent.validation")
def validation_node(state: GlobalState) -> GlobalState:
    """
    质量校验 Agent 节点

    Args:
        state: 当前工作流状态

    Returns:
        更新后的状态
    """
    logger.info("执行质量校验 Agent")

    try:
        user_friendly_progress_event("agent.validation", "start")
        # 重入保护：若已验证通过则跳过
        if state.get("validation_status") == ValidationStatus.VALIDATED:
            user_friendly_progress_event("agent.validation", "skip", reason="validated")
            return GlobalState(**{**state, "current_agent": AgentName.VALIDATION})
        
        if not state.get("final_report"):
            error_state = {
                **state,
                "current_agent": AgentName.VALIDATION,
                "error_message": "无法校验报告：缺少最终报告",
                "validation_status": ValidationStatus.FAILED,
                "last_updated": state.get("start_time") or state.get(
                    "last_updated")
            }
            return GlobalState(**error_state)

        # 使用统一的质量评估系统
        user_friendly_progress_event("agent.validation", "start")
        quality_metrics = evaluate_report_quality(
            report=state["final_report"],
            word_limit=state.get("word_limit"),
            evaluation_method="validation"
        )
        
        # 判断是否通过质量检查
        validation_passed = should_report_pass_quality_check(quality_metrics)
        validation_status = ValidationStatus.VALIDATED if validation_passed else ValidationStatus.NEEDS_REVISION
        
        user_friendly_progress_event("agent.validation", "parse_result",
                      score=quality_metrics.overall_score,
                      major_issues=quality_metrics.major_issues,
                      feedback=quality_metrics.feedback)

        # 更新状态，使用统一的质量指标格式
        updated_state = {
            **state,
            "validation_status": validation_status,
            "current_agent": AgentName.VALIDATION,
            "last_updated": datetime.now(),
            "warnings": state.get("warnings", []),
            "quality_metrics": {
                **state.get("quality_metrics", {}),
                **quality_metrics.to_dict(),  # 使用统一的质量指标
                "overall_score": quality_metrics.overall_score,  # 保持兼容性
                "validation_score": quality_metrics.overall_score,
                "word_count_accuracy": quality_metrics.word_count_accuracy,
                "actual_word_count": quality_metrics.actual_word_count,
                "major_issues": quality_metrics.major_issues,
                "feedback": quality_metrics.feedback
            }
        }

        logger.info(f"质量校验完成，评分为{quality_metrics.overall_score}")
        user_friendly_progress_event("agent.validation", "done", score=quality_metrics.overall_score, status=validation_status.value)
        return GlobalState(**updated_state)

    except Exception as e:
        logger.error(f"质量校验过程中出现错误: {str(e)}")
        from src.utils.agent_utils import create_error_state
        return create_error_state(
            state,
            AgentName.VALIDATION,
            f"质量校验失败: {str(e)}",
            ValidationStatus.FAILED
        )
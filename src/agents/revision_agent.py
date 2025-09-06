# src/agents/revision.py
"""
修订智能体
负责根据质量校验结果对报告进行针对性修改
"""

import logging
from datetime import datetime

from src.core.state import GlobalState, ValidationStatus, AgentName
from src.utils import rm_only_think
from src.utils.improved_revision import (
    generate_conservative_revision_prompt, 
    get_revision_strategy,
    should_use_conservative_revision
)
from src.utils.observability import measure, user_friendly_progress_event
from src.utils.prompt import REVISION_PROMPT
from src.utils.quality_system import evaluate_report_quality, should_report_pass_quality_check

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@measure("agent.revision")
def revision_node(state: GlobalState) -> GlobalState:
    """
    修订智能体节点

    Args:
        state: 当前工作流状态

    Returns:
        更新后的状态
    """
    logger.info("执行修订智能体")

    try:
        user_friendly_progress_event("agent.revision", "start")
        
        # 检查修订次数限制（最多3次）
        max_revisions = 3
        current_revision_count = state.get("revision_count", 0)
        
        if current_revision_count >= max_revisions:
            user_friendly_progress_event("agent.revision", "skip", reason="达到最大修订次数")
            logger.info(f"已达到最大修订次数 {max_revisions}，停止修订")
            # 强制设置为验证通过状态，避免无限循环
            return GlobalState(**{
                **state, 
                "current_agent": AgentName.REVISION,
                "validation_status": ValidationStatus.VALIDATED,
                "warnings": state.get("warnings", []) + [f"已达到最大修订次数 {max_revisions}，停止修订"]
            })
        
        # 重入保护：如果已经修订过且校验状态不是 NEEDS_REVISION，则跳过
        if current_revision_count > 0 and state.get("validation_status") != ValidationStatus.NEEDS_REVISION:
            user_friendly_progress_event("agent.revision", "skip", reason="no_need")
            return GlobalState(**{**state, "current_agent": AgentName.REVISION})
        
        if not state.get("final_report"):
            error_state = {
                **state,
                "current_agent": AgentName.REVISION,
                "error_message": "无法修订报告：缺少最终报告",
                "validation_status": ValidationStatus.FAILED,
                "last_updated": state.get("start_time") or state.get(
                    "last_updated")
            }
            return GlobalState(**error_state)

        if not state.get("error_message") and state.get(
                "validation_status") == ValidationStatus.VALIDATED:
            # 如果已经通过校验，直接返回
            logger.info("报告已通过校验，无需修订")
            return state

        # 获取反馈信息
        feedback = state.get("quality_metrics", {}).get("feedback", "")
        major_issues = state.get("quality_metrics", {}).get("major_issues", [])
        
        # 保存原始报告和评分
        original_report = state["final_report"]
        original_score = state.get("quality_metrics", {}).get("overall_score", 0)
        
        # 获取当前的质量评估（用于智能修订）
        current_quality_metrics = evaluate_report_quality(
            report=original_report,
            word_limit=state.get("word_limit"),
            evaluation_method="pre_revision"
        )
        
        # 执行智能修订
        revised_report = _execute_smart_revisions(
            original_report,
            current_quality_metrics,
            state['word_limit'],
            state.get("revision_count", 0)
        )
        
        # 使用统一质量评估系统评估修订后的报告
        user_friendly_progress_event("agent.revision", "quality_evaluation")
        revised_quality_metrics = evaluate_report_quality(
            report=revised_report,
            word_limit=state.get("word_limit"),
            evaluation_method="revision"
        )
        revised_score = revised_quality_metrics.overall_score
        
        # 检查修订后报告是否满足条件
        revised_passes_check = should_report_pass_quality_check(revised_quality_metrics)
        
        # 比较评分和质量，选择最佳版本
        if revised_passes_check and revised_score >= original_score:
            # 修订版本更好且满足质量要求
            final_report = revised_report
            final_quality_metrics = revised_quality_metrics
            score_message = f"修订后评分更高且满足要求 ({revised_score:.1f} >= {original_score:.1f})，采用修订版本"
            decision = "keep_revised"
            # 如果修订后的报告满足质量要求，直接设置为验证通过
            if revised_passes_check:
                validation_status_after_revision = ValidationStatus.VALIDATED
                logger.info(f"修订后报告满足质量要求({revised_score:.1f}分)，直接通过验证")
            else:
                validation_status_after_revision = ValidationStatus.NEEDS_REVISION
        elif revised_score > original_score:
            # 修订版本评分更高但可能不满足质量要求
            final_report = revised_report
            final_quality_metrics = revised_quality_metrics
            score_message = f"修订后评分更高 ({revised_score:.1f} > {original_score:.1f})，采用修订版本"
            decision = "keep_revised"
            validation_status_after_revision = ValidationStatus.NEEDS_REVISION
        else:
            # 保留原版本
            final_report = original_report
            # 保持原有的质量指标
            final_quality_metrics = None
            score_message = f"原版本评分更高 ({original_score:.1f} >= {revised_score:.1f})，保留原版本"
            decision = "keep_original"
            validation_status_after_revision = ValidationStatus.NEEDS_REVISION
        
        user_friendly_progress_event("agent.revision", "score_comparison", 
                      original_score=original_score, revised_score=revised_score, 
                      decision=decision)

        # 若修订版本字数仍偏离±5%，尝试进行一次自动微调
        try:
            target = int(state.get("word_limit")) if state.get("word_limit") else None
        except Exception:
            target = None
        if target and (not revised_quality_metrics.word_count_accuracy):
            from src.utils.llm_utils import call_llm_sync
            adjust_prompt = (
                f"请将以下报告调整至约{target}字（±5%），保持结构完整与要点不丢失，不要输出说明：\n\n" + revised_report
            )
            adjusted = call_llm_sync(
                prompt=adjust_prompt,
                agent_name="agent.revision",
                operation_name="llm_call_traditional_revision",
                max_tokens=6000,
            )
            revised_report = rm_only_think(adjusted)
            # 重新评估以获得新的字数与准确性
            revised_quality_metrics = evaluate_report_quality(
                report=revised_report,
                word_limit=state.get("word_limit"),
                evaluation_method="revision_adjusted"
            )

        # 更新状态
        updated_state = {
            **state,
            "final_report": final_report,
            "current_agent": AgentName.REVISION,
            "last_updated": datetime.now(),
            "revision_count": state.get("revision_count", 0) + 1,
            "validation_status": validation_status_after_revision,  # 根据质量检查结果设置状态
            "warnings": state.get("warnings", []) + [
                f"已完成第{state.get('revision_count', 0) + 1}轮修订 - {score_message}"]
        }
        
        # 如果有新的质量指标，更新它
        if final_quality_metrics is not None:
            updated_state["quality_metrics"] = {
                **state.get("quality_metrics", {}),
                **final_quality_metrics.to_dict(),
                "overall_score": final_quality_metrics.overall_score,
                "revision_score": final_quality_metrics.overall_score,
                "word_count_accuracy": final_quality_metrics.word_count_accuracy,
                "actual_word_count": final_quality_metrics.actual_word_count,
                "major_issues": final_quality_metrics.major_issues,
                "feedback": final_quality_metrics.feedback
            }
        # 发送正确的修订完成消息
        final_revision_count = state.get("revision_count", 0) + 1
        user_friendly_progress_event("agent.revision", "done", revision_count=final_revision_count)
        return GlobalState(**updated_state)

    except Exception as e:
        logger.error(f"修订过程中出现错误: {str(e)}")
        error_state = {
            **state,
            "current_agent": AgentName.REVISION,
            "error_message": f"修订失败: {str(e)}",
            "validation_status": ValidationStatus.NEEDS_REVISION,
            "last_updated": state.get("start_time") or state.get(
                "last_updated")
        }
        user_friendly_progress_event("agent.revision", "error", message=str(e))
        return GlobalState(**error_state)


def _execute_smart_revisions(report: str, quality_metrics, target_length, revision_count: int = 0) -> str:
    """
    执行智能修订任务 - 根据报告质量选择合适的修订策略
    """
    from src.utils.llm_utils import call_llm_sync
    
    try:
        # 确定修订策略
        revision_strategy = get_revision_strategy(quality_metrics)
        logger.info(f"执行智能修订任务，策略: {revision_strategy}, 原评分: {quality_metrics.overall_score:.1f}")
        
        # 生成改进的修订prompt
        prompt = generate_conservative_revision_prompt(
            original_report=report,
            quality_metrics=quality_metrics,
            target_length=target_length,
            revision_strategy=revision_strategy
        )
        
        # 使用统一的LLM调用，增加max_tokens以支持完整的修订
        response = call_llm_sync(
            prompt=prompt,
            agent_name="agent.revision",
            operation_name="llm_call_smart_revision",
            max_tokens=6000  # 为修订agent增加更大的token限制
        )

        logger.info(f"完成智能修订任务，策略: {revision_strategy}")
        revised_content = rm_only_think(response)

        user_friendly_progress_event("agent.revision", "done",
                      original_length=len(report),
                      revised_length=len(revised_content),
                      revision_count=revision_count + 1,
                      strategy=revision_strategy)
        return revised_content
    except Exception as e:
        logger.error(f"执行智能修订任务失败: {str(e)}")
        return report


def _execute_revisions(report: str, feedback, major_issues, target_length, revision_count: int = 0) -> str:
    """
    执行传统修订任务（保留作为备用）
    """
    from src.utils.llm_utils import call_llm_sync
    
    logger.info(f"执行传统修订任务, major issues:{major_issues}, feedback:{feedback}")
    issues = '\n'.join(major_issues) if isinstance(major_issues, list) else str(major_issues)

    try:
        prompt = REVISION_PROMPT.format(
            report=report, issues=issues, feedback=feedback, target_length=target_length
        )
        
        # 使用统一的LLM调用，增加max_tokens以支持完整的修订
        response = call_llm_sync(
            prompt=prompt,
            agent_name="agent.revision",
            operation_name="llm_call_traditional_revision",
            max_tokens=6000  # 为修订agent增加更大的token限制
        )

        logger.info(f"完成传统修订任务")
        revised_content = rm_only_think(response)

        user_friendly_progress_event("agent.revision", "done",
                      original_length=len(report),
                      revised_length=len(revised_content),
                      revision_count=revision_count + 1)
        return revised_content
    except Exception as e:
        logger.error(f"执行传统修订任务失败: {str(e)}")
        return report


# 注意：_evaluate_report_quality 函数已被统一的质量评估系统替代
# 现在使用 src.utils.quality_system.evaluate_report_quality

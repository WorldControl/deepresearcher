import logging
from datetime import datetime

from src import utils
from src.core.state import GlobalState, AgentName, ValidationStatus
from src.utils import word_count
from src.utils.agent_utils import (
    create_error_state, 
    create_success_state, 
    check_required_field,
    should_skip_agent,
    log_agent_start,
    log_agent_complete
)
from src.utils.llm_utils import call_llm_sync
from src.utils.observability import measure
from src.utils.prompt import REPORT_WRITER_PROMPT, WRITING_USER_PROMPT

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@measure("agent.writing_polishing")
def writing_polishing_node(state: GlobalState) -> GlobalState:
    """报告撰写与润色 Agent"""
    log_agent_start(AgentName.WRITING, "报告撰写与润色")

    try:
        # 重入保护：已有 final_report 则跳过
        skip_state = should_skip_agent(
            state, 
            AgentName.WRITING,
            [{"field": "final_report", "value": None, "check_func": lambda s: s.get("final_report")}],
            "already_has_final_report"
        )
        if skip_state:
            return skip_state

        # 检查必需字段
        error_state = check_required_field(
            state, 
            "draft_report", 
            AgentName.WRITING,
            "无法润色报告：缺少报告草稿"
        )
        if error_state:
            return error_state

        # 构建提示词模板
        user_prompt = WRITING_USER_PROMPT.format(draft_report=state['draft_report'])
        full_prompt = f"{REPORT_WRITER_PROMPT.format(word_limit=state['word_limit'], task=state['user_query'])}\n\n{user_prompt}"
        
        logger.info("=" * 50)
        
        # 使用统一的LLM调用，增加max_tokens以支持更长的报告
        final_report = call_llm_sync(
            prompt=full_prompt,
            agent_name="agent.writing_polishing",
            max_tokens=6000  # 为写作agent增加更大的token限制
        )

        # 处理LLM响应
        processed_report = utils.rm_only_think(final_report)
        final_word_count = word_count.count_words(processed_report)

        # 若超出±5%，进行自动长度校正（裁剪或扩写提示一次）
        try:
            target = int(state['word_limit']) if state.get('word_limit') else None
        except Exception:
            target = None
        if target:
            lower, upper = int(target * 0.95), int(target * 1.05)
            if final_word_count > upper or final_word_count < lower:
                # 调整提示，要求在目标附近输出
                adjust_prompt = (
                    f"请在不损失关键信息的前提下将上文报告调整到约{target}字（允许±5%），"
                    f"若过长请精炼冗余描述，若过短请补充必要论据与细节；"
                    "保持结构完整、逻辑连贯，不要输出除报告正文外的任何说明。\n\n上文报告：\n" + processed_report
                )
                adjusted = call_llm_sync(
                    prompt=adjust_prompt,
                    agent_name="agent.writing_polishing",
                    max_tokens=6000,
                )
                processed_report = utils.rm_only_think(adjusted)
                final_word_count = word_count.count_words(processed_report)
        
        # 使用统一的成功状态创建
        updated_fields = {
            "final_report": processed_report,
            "warnings": state.get("warnings", [])
        }
        
        # 记录完成信息
        logger.info(f"报告撰写与润色完成，生成{len(final_report)}字符的最终报告")
        logger.info("**********************************")
        logger.info(f"最终报告内容：{final_report}")
        logger.info("**********************************")
        logger.info(f"报告字数：{final_word_count}, 目标字数:{state['word_limit']}")
        
        log_agent_complete(
            AgentName.WRITING,
            "报告撰写与润色完成",
            {
                "length": len(final_report),
                "word_count": final_word_count,
                "target_word_limit": state['word_limit']
            }
        )
        
        return create_success_state(state, AgentName.WRITING, updated_fields)
        
    except Exception as e:
        logger.exception(f"报告撰写与润色过程中出现错误: {str(e)}")
        return create_error_state(
            state,
            AgentName.WRITING,
            f"报告撰写与润色失败: {str(e)}",
            ValidationStatus.FAILED
        )
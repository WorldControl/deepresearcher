# src/utils/agent_utils.py
"""
Agent通用工具函数
统一agent中的重复代码模式
"""

import logging
from datetime import datetime
from typing import Optional, Dict, Any, List
from src.core.state import GlobalState, AgentName, ValidationStatus
from src.utils.observability import user_friendly_progress_event

logger = logging.getLogger(__name__)


def create_error_state(
    state: GlobalState,
    agent_name: AgentName,
    error_message: str,
    validation_status: ValidationStatus = ValidationStatus.FAILED,
    additional_fields: Optional[Dict[str, Any]] = None
) -> GlobalState:
    """
    创建统一的错误状态
    
    Args:
        state: 当前状态
        agent_name: 发生错误的agent名称
        error_message: 错误消息
        validation_status: 验证状态，默认为FAILED
        additional_fields: 额外的状态字段
        
    Returns:
        包含错误信息的新状态
    """
    error_state = {
        **state,
        "current_agent": agent_name,
        "error_message": error_message,
        "validation_status": validation_status,
        "last_updated": datetime.now()
    }
    
    # 添加额外字段
    if additional_fields:
        error_state.update(additional_fields)
    
    # 记录错误事件
    agent_name_str = agent_name.value if hasattr(agent_name, 'value') else str(agent_name)
    user_friendly_progress_event(
        f"agent.{agent_name_str.replace('_agent', '')}", 
        "error", 
        message=error_message
    )
    
    logger.error(f"Agent {agent_name_str} 发生错误: {error_message}")
    
    return GlobalState(**error_state)


def create_success_state(
    state: GlobalState,
    agent_name: AgentName,
    updated_fields: Dict[str, Any],
    warning_message: Optional[str] = None
) -> GlobalState:
    """
    创建统一的成功状态
    
    Args:
        state: 当前状态
        agent_name: 执行成功的agent名称
        updated_fields: 需要更新的状态字段
        warning_message: 可选的警告消息
        
    Returns:
        更新后的成功状态
    """
    # 基础更新字段
    base_updates = {
        "current_agent": agent_name,
        "last_updated": datetime.now()
    }
    
    # 合并所有更新
    success_state = {
        **state,
        **base_updates,
        **updated_fields
    }
    
    # 添加警告消息（如果有）
    if warning_message:
        warnings = success_state.get("warnings", [])
        if isinstance(warnings, list):
            warnings.append(warning_message)
        else:
            warnings = [warning_message]
        success_state["warnings"] = warnings
    
    return GlobalState(**success_state)


def check_required_field(
    state: GlobalState,
    field_name: str,
    agent_name: AgentName,
    custom_error_message: Optional[str] = None
) -> Optional[GlobalState]:
    """
    检查必需字段是否存在，如果不存在则返回错误状态
    
    Args:
        state: 当前状态
        field_name: 需要检查的字段名
        agent_name: 当前agent名称
        custom_error_message: 自定义错误消息
        
    Returns:
        如果字段不存在返回错误状态，否则返回None
    """
    if not state.get(field_name):
        error_message = custom_error_message or f"无法执行操作：缺少必需字段 '{field_name}'"
        return create_error_state(state, agent_name, error_message)
    return None


def should_skip_agent(
    state: GlobalState,
    agent_name: AgentName,
    skip_conditions: List[Dict[str, Any]],
    skip_reason: str = "condition_met"
) -> Optional[GlobalState]:
    """
    检查是否应该跳过当前agent的执行
    
    Args:
        state: 当前状态
        agent_name: 当前agent名称
        skip_conditions: 跳过条件列表，每个条件是字典 {"field": "field_name", "value": expected_value}
        skip_reason: 跳过原因
        
    Returns:
        如果应该跳过返回跳过状态，否则返回None
    """
    for condition in skip_conditions:
        field_name = condition.get("field")
        expected_value = condition.get("value")
        check_func = condition.get("check_func")  # 自定义检查函数
        
        if check_func:
            # 使用自定义检查函数
            if check_func(state):
                logger.info(f"Agent {agent_name} 跳过执行: {skip_reason}")
                user_friendly_progress_event(
                    f"agent.{agent_name.value.replace('_agent', '')}", 
                    "skip", 
                    reason=skip_reason
                )
                return create_success_state(state, agent_name, {})
        elif field_name and expected_value is not None:
            # 简单字段值比较
            if state.get(field_name) == expected_value:
                logger.info(f"Agent {agent_name} 跳过执行: {skip_reason}")
                user_friendly_progress_event(
                    f"agent.{agent_name.value.replace('_agent', '')}", 
                    "skip", 
                    reason=skip_reason
                )
                return create_success_state(state, agent_name, {})
    
    return None


def log_agent_start(agent_name: AgentName, description: str = ""):
    """
    统一的agent开始日志记录
    
    Args:
        agent_name: agent名称
        description: 可选的描述信息
    """
    agent_name_str = agent_name.value if hasattr(agent_name, 'value') else str(agent_name)
    log_message = f"开始执行 {agent_name_str}"
    if description:
        log_message += f" - {description}"
    
    logger.info(log_message)
    user_friendly_progress_event(
        f"agent.{agent_name_str.replace('_agent', '')}", 
        "start"
    )


def log_agent_complete(
    agent_name: AgentName, 
    description: str = "",
    metrics: Optional[Dict[str, Any]] = None
):
    """
    统一的agent完成日志记录
    
    Args:
        agent_name: agent名称
        description: 可选的描述信息
        metrics: 可选的性能指标
    """
    agent_name_str = agent_name.value if hasattr(agent_name, 'value') else str(agent_name)
    log_message = f"完成执行 {agent_name_str}"
    if description:
        log_message += f" - {description}"
    
    logger.info(log_message)
    
    # 构建进度事件参数
    event_params = {}
    if metrics:
        event_params.update(metrics)
    
    user_friendly_progress_event(
        f"agent.{agent_name_str.replace('_agent', '')}", 
        "done",
        **event_params
    )


def safe_get_field(state: GlobalState, field_path: str, default_value: Any = None) -> Any:
    """
    安全获取嵌套字段值
    
    Args:
        state: 状态对象
        field_path: 字段路径，支持点分隔的嵌套路径，如 "requirements.domain"
        default_value: 默认值
        
    Returns:
        字段值或默认值
    """
    try:
        current = state
        for field in field_path.split('.'):
            if hasattr(current, field):
                current = getattr(current, field)
            elif isinstance(current, dict) and field in current:
                current = current[field]
            else:
                return default_value
        return current
    except Exception:
        return default_value


def merge_quality_metrics(
    state: GlobalState,
    new_metrics: Dict[str, Any],
    preserve_existing: bool = True
) -> Dict[str, Any]:
    """
    合并质量指标
    
    Args:
        state: 当前状态
        new_metrics: 新的指标
        preserve_existing: 是否保留现有指标
        
    Returns:
        合并后的质量指标字典
    """
    if preserve_existing:
        existing_metrics = state.get("quality_metrics", {})
        if isinstance(existing_metrics, dict):
            return {**existing_metrics, **new_metrics}
    
    return new_metrics


class AgentExecutionContext:
    """Agent执行上下文管理器"""
    
    def __init__(self, agent_name: AgentName, description: str = ""):
        self.agent_name = agent_name
        self.description = description
        self.start_time = None
    
    def __enter__(self):
        self.start_time = datetime.now()
        log_agent_start(self.agent_name, self.description)
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is None:
            # 正常完成
            duration = (datetime.now() - self.start_time).total_seconds()
            log_agent_complete(
                self.agent_name, 
                self.description,
                {"duration_seconds": round(duration, 2)}
            )
        else:
            # 发生异常
            logger.error(f"Agent {self.agent_name} 执行失败: {exc_val}")


# 便捷的装饰器
def agent_execution_wrapper(agent_name: AgentName, description: str = ""):
    """
    Agent执行装饰器，自动处理开始和结束日志
    
    Args:
        agent_name: agent名称
        description: 描述信息
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            with AgentExecutionContext(agent_name, description):
                return func(*args, **kwargs)
        return wrapper
    return decorator

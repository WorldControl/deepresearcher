# src/utils/agent_common.py
"""
Agent通用模式和标准化操作
提供agent开发的最佳实践模板
"""

from datetime import datetime
from typing import Optional, Dict, Any, List
from src.core.state import GlobalState, AgentName, ValidationStatus
from src.utils.llm_utils import call_llm_sync
from src.utils.agent_utils import (
    create_error_state, 
    create_success_state, 
    check_required_field,
    should_skip_agent,
    log_agent_start,
    log_agent_complete,
    safe_get_field
)
from src.utils.observability import measure, user_friendly_progress_event
import logging

logger = logging.getLogger(__name__)


class AgentTemplate:
    """
    标准化的Agent模板类
    提供通用的agent执行模式
    """
    
    def __init__(
        self,
        agent_name: AgentName,
        description: str = "",
        required_fields: Optional[List[str]] = None,
        skip_conditions: Optional[List[Dict[str, Any]]] = None
    ):
        self.agent_name = agent_name
        self.description = description
        self.required_fields = required_fields or []
        self.skip_conditions = skip_conditions or []
    
    def execute(
        self,
        state: GlobalState,
        main_logic: Callable[[GlobalState], Dict[str, Any]],
        success_message: str = "执行完成",
        error_validation_status: ValidationStatus = ValidationStatus.FAILED
    ) -> GlobalState:
        """
        标准化的agent执行流程
        
        Args:
            state: 当前状态
            main_logic: 主要业务逻辑函数，返回更新字段字典
            success_message: 成功消息
            error_validation_status: 错误时的验证状态
            
        Returns:
            更新后的状态
        """
        log_agent_start(self.agent_name, self.description)
        
        try:
            # 1. 检查跳过条件
            skip_state = should_skip_agent(state, self.agent_name, self.skip_conditions)
            if skip_state:
                return skip_state
            
            # 2. 检查必需字段
            for field in self.required_fields:
                error_state = check_required_field(state, field, self.agent_name)
                if error_state:
                    return error_state
            
            # 3. 执行主要逻辑
            updated_fields = main_logic(state)
            
            # 4. 记录完成
            log_agent_complete(self.agent_name, success_message, updated_fields.get("metrics"))
            
            # 5. 返回成功状态
            return create_success_state(state, self.agent_name, updated_fields)
            
        except Exception as e:
            logger.exception(f"{self.agent_name} 执行失败: {str(e)}")
            return create_error_state(
                state,
                self.agent_name,
                f"{self.description}失败: {str(e)}",
                error_validation_status
            )


class LLMAgentTemplate(AgentTemplate):
    """
    专门用于LLM调用的Agent模板
    """
    
    def __init__(
        self,
        agent_name: AgentName,
        description: str = "",
        required_fields: Optional[List[str]] = None,
        skip_conditions: Optional[List[Dict[str, Any]]] = None,
        llm_timeout: int = 60
    ):
        super().__init__(agent_name, description, required_fields, skip_conditions)
        self.llm_timeout = llm_timeout
    
    def execute_with_llm(
        self,
        state: GlobalState,
        prompt_builder: Callable[[GlobalState], str],
        response_processor: Callable[[str, GlobalState], Dict[str, Any]],
        success_message: str = "LLM调用完成",
        llm_operation_name: str = "llm_call"
    ) -> GlobalState:
        """
        专门用于LLM调用的执行流程
        
        Args:
            state: 当前状态
            prompt_builder: 构建提示词的函数
            response_processor: 处理LLM响应的函数，返回更新字段
            success_message: 成功消息
            llm_operation_name: LLM操作名称
            
        Returns:
            更新后的状态
        """
        def main_logic(state: GlobalState) -> Dict[str, Any]:
            # 构建提示词
            prompt = prompt_builder(state)
            
            # 调用LLM
            agent_name_str = f"agent.{self.agent_name.value.replace('_agent', '')}"
            response = call_llm_sync(
                prompt=prompt,
                agent_name=agent_name_str,
                operation_name=llm_operation_name,
                timeout_seconds=self.llm_timeout
            )
            
            # 处理响应
            return response_processor(response, state)
        
        return self.execute(state, main_logic, success_message)


def create_standard_agent_decorator(
    agent_name: AgentName,
    description: str = "",
    required_fields: Optional[List[str]] = None,
    skip_conditions: Optional[List[Dict[str, Any]]] = None
):
    """
    创建标准agent装饰器
    
    Args:
        agent_name: agent名称
        description: 描述
        required_fields: 必需字段列表
        skip_conditions: 跳过条件列表
        
    Returns:
        装饰器函数
    """
    def decorator(func):
        def wrapper(state: GlobalState) -> GlobalState:
            template = AgentTemplate(agent_name, description, required_fields, skip_conditions)
            
            def main_logic(state: GlobalState) -> Dict[str, Any]:
                return func(state)
            
            return template.execute(state, main_logic)
        
        # 保持原函数的measure装饰器
        return measure(f"agent.{agent_name.value.replace('_agent', '')}")(wrapper)
    
    return decorator


def create_llm_agent_decorator(
    agent_name: AgentName,
    description: str = "",
    required_fields: Optional[List[str]] = None,
    skip_conditions: Optional[List[Dict[str, Any]]] = None,
    llm_timeout: int = 60
):
    """
    创建LLM agent装饰器
    """
    def decorator(func):
        def wrapper(state: GlobalState) -> GlobalState:
            template = LLMAgentTemplate(
                agent_name, description, required_fields, skip_conditions, llm_timeout
            )
            
            # 假设func返回(prompt_builder, response_processor)元组
            prompt_builder, response_processor = func(state)
            
            return template.execute_with_llm(
                state, prompt_builder, response_processor
            )
        
        return measure(f"agent.{agent_name.value.replace('_agent', '')}")(wrapper)
    
    return decorator


# 常用的agent配置预设
AGENT_CONFIGS = {
    "writing_polishing": {
        "required_fields": ["draft_report"],
        "skip_conditions": [
            {"field": "final_report", "check_func": lambda s: s.get("final_report")}
        ]
    },
    "knowledge_retrieval": {
        "required_fields": ["structure"],
        "skip_conditions": [
            {"field": "draft_report", "check_func": lambda s: s.get("draft_report")}
        ]
    },
    "problem_understanding": {
        "required_fields": ["user_query"],
        "skip_conditions": [
            {"field": "requirements", "check_func": lambda s: s.get("requirements")}
        ]
    },
    "structure_planning": {
        "required_fields": ["requirements"],
        "skip_conditions": [
            {"field": "structure", "check_func": lambda s: s.get("structure")}
        ]
    },
    "validation": {
        "required_fields": ["final_report"],
        "skip_conditions": []
    },
    "revision": {
        "required_fields": ["final_report"],
        "skip_conditions": [
            {
                "field": "validation_status", 
                "check_func": lambda s: s.get("validation_status") == ValidationStatus.VALIDATED
            }
        ]
    }
}


def get_agent_config(agent_type: str) -> Dict[str, Any]:
    """获取agent配置"""
    return AGENT_CONFIGS.get(agent_type, {})


# 便捷函数，用于快速创建标准化的agent
def create_simple_agent(agent_name: AgentName, agent_type: str):
    """
    创建简单的标准化agent
    
    Args:
        agent_name: agent名称
        agent_type: agent类型（用于获取配置）
        
    Returns:
        AgentTemplate实例
    """
    config = get_agent_config(agent_type)
    return AgentTemplate(
        agent_name=agent_name,
        required_fields=config.get("required_fields"),
        skip_conditions=config.get("skip_conditions")
    )


def create_llm_agent(agent_name: AgentName, agent_type: str, llm_timeout: int = 60):
    """
    创建LLM agent
    
    Args:
        agent_name: agent名称
        agent_type: agent类型
        llm_timeout: LLM超时时间
        
    Returns:
        LLMAgentTemplate实例
    """
    config = get_agent_config(agent_type)
    return LLMAgentTemplate(
        agent_name=agent_name,
        required_fields=config.get("required_fields"),
        skip_conditions=config.get("skip_conditions"),
        llm_timeout=llm_timeout
    )

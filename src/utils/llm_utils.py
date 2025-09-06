# src/utils/llm_utils.py
"""
统一的LLM调用工具
消除各个agent中的重复LLM调用代码
"""

import asyncio
import logging
from typing import Optional, Dict, Any, AsyncGenerator
from src.llm_adapter import llm_client

logger = logging.getLogger(__name__)


async def call_llm_async(
    prompt: str,
    agent_name: str,
    operation_name: str = "llm_call",
    timeout_seconds: int = 120,  # 增加到120秒，支持更长的报告生成
    max_tokens: int = 4000,  # 默认增加到4000以支持更长内容
    **llm_kwargs
) -> str:
    """
    统一的异步LLM调用函数
    
    Args:
        prompt: 发送给LLM的提示词
        agent_name: 调用的agent名称（用于进度事件）
        operation_name: 操作名称（用于进度事件）
        timeout_seconds: 超时时间（秒）
        **llm_kwargs: 传递给LLM的额外参数
        
    Returns:
        LLM生成的完整响应文本
        
    Raises:
        Exception: LLM调用失败时抛出异常
    """
    response_content = ""
    
    async def get_llm_response():
        nonlocal response_content
        # 合并max_tokens参数
        merged_kwargs = {"max_tokens": max_tokens, **llm_kwargs}
        async for chunk in llm_client.generate(prompt, **merged_kwargs):
            response_content += chunk
        return response_content
    
    try:
        
        # 调用LLM，传递max_tokens参数
        response = await asyncio.wait_for(
            get_llm_response(), 
            timeout=timeout_seconds
        )
        
        logger.info(f"LLM调用成功 - Agent: {agent_name}, 响应长度: {len(response)}")
        return response
        
    except asyncio.TimeoutError:
        error_msg = f"LLM调用超时 - Agent: {agent_name}, 超时时间: {timeout_seconds}秒"
        logger.error(error_msg)
        raise Exception(error_msg)
    except Exception as e:
        error_msg = f"LLM调用失败 - Agent: {agent_name}, 错误: {str(e)}"
        logger.error(error_msg)
        raise Exception(error_msg)


def call_llm_sync(
    prompt: str,
    agent_name: str,
    operation_name: str = "llm_call",
    timeout_seconds: int = 120,  # 增加到120秒，支持更长的报告生成
    max_tokens: int = 4000,  # 默认增加到4000以支持更长内容
    **llm_kwargs
) -> str:
    """
    统一的同步LLM调用函数（使用asyncio.run包装异步调用）
    
    Args:
        prompt: 发送给LLM的提示词
        agent_name: 调用的agent名称（用于进度事件）
        operation_name: 操作名称（用于进度事件）
        timeout_seconds: 超时时间（秒）
        **llm_kwargs: 传递给LLM的额外参数
        
    Returns:
        LLM生成的完整响应文本
        
    Raises:
        Exception: LLM调用失败时抛出异常
    """
    try:
        return asyncio.run(call_llm_async(
            prompt=prompt,
            agent_name=agent_name,
            operation_name=operation_name,
            timeout_seconds=timeout_seconds,
            max_tokens=max_tokens,
            **llm_kwargs
        ))
    except Exception as e:
        # 重新抛出异常，保持原有的错误处理逻辑
        raise e


async def call_llm_stream(
    prompt: str,
    agent_name: str,
    operation_name: str = "llm_stream",
    timeout_seconds: int = 60,
    **llm_kwargs
) -> AsyncGenerator[str, None]:
    """
    统一的流式LLM调用函数
    
    Args:
        prompt: 发送给LLM的提示词
        agent_name: 调用的agent名称（用于进度事件）
        operation_name: 操作名称（用于进度事件）
        timeout_seconds: 超时时间（秒）
        **llm_kwargs: 传递给LLM的额外参数
        
    Yields:
        LLM生成的文本块
        
    Raises:
        Exception: LLM调用失败时抛出异常
    """
    try:
        
        # 超时包装器
        async def _iterate_with_timeout(gen: AsyncGenerator[str, None], timeout: int):
            try:
                while True:
                    item = await asyncio.wait_for(gen.__anext__(), timeout)
                    yield item
            except StopAsyncIteration:
                return
        
        # 流式调用LLM
        gen = llm_client.generate(prompt, **llm_kwargs)
        async for chunk in _iterate_with_timeout(gen, timeout_seconds):
            if chunk:
                yield chunk
                
        logger.info(f"LLM流式调用完成 - Agent: {agent_name}")
        
    except asyncio.TimeoutError:
        error_msg = f"LLM流式调用超时 - Agent: {agent_name}, 超时时间: {timeout_seconds}秒"
        logger.error(error_msg)
        raise Exception(error_msg)
    except Exception as e:
        error_msg = f"LLM流式调用失败 - Agent: {agent_name}, 错误: {str(e)}"
        logger.error(error_msg)
        raise Exception(error_msg)


class LLMCallConfig:
    """LLM调用配置类"""
    
    def __init__(
        self,
        agent_name: str,
        operation_name: str = "llm_call",
        timeout_seconds: int = 60,
        **llm_kwargs
    ):
        self.agent_name = agent_name
        self.operation_name = operation_name
        self.timeout_seconds = timeout_seconds
        self.llm_kwargs = llm_kwargs
    
    async def call_async(self, prompt: str) -> str:
        """使用配置调用异步LLM"""
        return await call_llm_async(
            prompt=prompt,
            agent_name=self.agent_name,
            operation_name=self.operation_name,
            timeout_seconds=self.timeout_seconds,
            **self.llm_kwargs
        )
    
    def call_sync(self, prompt: str) -> str:
        """使用配置调用同步LLM"""
        return call_llm_sync(
            prompt=prompt,
            agent_name=self.agent_name,
            operation_name=self.operation_name,
            timeout_seconds=self.timeout_seconds,
            **self.llm_kwargs
        )
    
    async def call_stream(self, prompt: str) -> AsyncGenerator[str, None]:
        """使用配置调用流式LLM"""
        async for chunk in call_llm_stream(
            prompt=prompt,
            agent_name=self.agent_name,
            operation_name=self.operation_name,
            timeout_seconds=self.timeout_seconds,
            **self.llm_kwargs
        ):
            yield chunk


# 便捷函数，为各个agent创建预配置的LLM调用器
def create_agent_llm_caller(agent_name: str, **default_kwargs) -> LLMCallConfig:
    """
    为特定agent创建LLM调用配置
    
    Args:
        agent_name: agent名称
        **default_kwargs: 默认的LLM参数
        
    Returns:
        配置好的LLMCallConfig实例
    """
    return LLMCallConfig(agent_name=agent_name, **default_kwargs)

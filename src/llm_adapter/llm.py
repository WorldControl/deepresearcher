from typing import Any, Dict, AsyncGenerator

import os
import abc
from dotenv import load_dotenv

from langchain_openai import ChatOpenAI
import asyncio
import time
from langchain.callbacks import StreamingStdOutCallbackHandler

load_dotenv()


class BaseLLM(abc.ABC):
    @abc.abstractmethod
    async def generate(
            self,
            prompt: str,
            **kwargs: Any
    ):
        """异步流式生成文本"""
        pass

    def _merge_parameters(
            self,
            default_params: Dict[str, Any],
            override_params: Dict[str, Any]
    ) -> Dict[str, Any]:
        """合并默认参数和自定义参数"""
        params = default_params.copy()
        params.update(
            {k: v for k, v in override_params.items() if v is not None})
        return params


class OpenAIStyleLLM(BaseLLM):
    def __init__(self):
        super().__init__()
        self.llm = ChatOpenAI(
            base_url=os.getenv("OPENAI_BASE_URL"),
            api_key=os.getenv("OPENAI_API_KEY"),
            model=os.getenv("OPENAI_MODEL"),
            streaming=True,
            callbacks=[StreamingStdOutCallbackHandler()]
        )

    async def generate(self, prompt: str, **kwargs):
        """异步流式生成文本"""
        prompt = f"/nothink{prompt}"
        default_params = {
            "temperature": 0.7,
            "max_tokens": 4000,  # 增加到4000以支持更长的报告生成
            "top_p": 1.0,
            "stream": True
        }
        params = self._merge_parameters(default_params, kwargs)

        # 统一加限流/重试与超时
        max_retries = int(os.getenv("LLM_MAX_RETRIES", 2))
        initial_backoff = float(os.getenv("LLM_RETRY_BACKOFF", 1.0))
        timeout_seconds = int(os.getenv("LLM_TIMEOUT_SECONDS", 60))

        async def _astream() -> AsyncGenerator[str, None]:
            # 兼容 langchain_openai 的新版/旧版调用
            try:
                async for chunk in self.llm.astream(
                    [{"role": "user", "content": prompt}],
                    **params
                ):
                    if hasattr(chunk, 'content') and chunk.content:
                        yield chunk.content
            except AttributeError:
                async for chunk in self.llm.astream(prompt, **params):
                    if hasattr(chunk, 'content') and chunk.content:
                        yield chunk.content

        async def _iterate_with_timeout(gen: AsyncGenerator[str, None], timeout: int):
            try:
                while True:
                    item = await asyncio.wait_for(gen.__anext__(), timeout)
                    yield item
            except StopAsyncIteration:
                return

        attempt = 0
        while True:
            try:
                async for c in _iterate_with_timeout(_astream(), timeout_seconds):
                    yield c
                break
            except Exception as e:
                if attempt >= max_retries:
                    raise e
                await asyncio.sleep(initial_backoff * (2 ** attempt))
                attempt += 1

    async def generate_from_messages(self, messages: list, **kwargs):
        """异步流式生成文本（从消息列表）"""
        default_params = {
            "temperature": 0.7,
            "max_tokens": 4000,  # 增加到4000以支持更长的报告生成
            "top_p": 1.0,
            "stream": True
        }
        params = self._merge_parameters(default_params, kwargs)

        max_retries = int(os.getenv("LLM_MAX_RETRIES", 2))
        initial_backoff = float(os.getenv("LLM_RETRY_BACKOFF", 1.0))
        timeout_seconds = int(os.getenv("LLM_TIMEOUT_SECONDS", 60))

        async def _astream():
            async for chunk in self.llm.astream(messages, **params):
                if hasattr(chunk, 'content') and chunk.content:
                    yield chunk.content

        async def _iterate_with_timeout(gen: AsyncGenerator[str, None], timeout: int):
            try:
                while True:
                    item = await asyncio.wait_for(gen.__anext__(), timeout)
                    yield item
            except StopAsyncIteration:
                return

        attempt = 0
        while True:
            try:
                async for c in _iterate_with_timeout(_astream(), timeout_seconds):
                    yield c
                break
            except Exception as e:
                if attempt >= max_retries:
                    raise e
                await asyncio.sleep(initial_backoff * (2 ** attempt))
                attempt += 1


class LLMFactory:
    @staticmethod
    def create_llm():
        return OpenAIStyleLLM()


llm_client = LLMFactory.create_llm()

if __name__ == "__main__":
    try:
        res = llm_client.generate("1+1等于几")
        print(res)
    except Exception as e:  # noqa: BLE001
        print("LLM 调用失败:", e)
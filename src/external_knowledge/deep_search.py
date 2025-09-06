import asyncio
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
import time
from typing import List, Literal, Optional, AsyncGenerator, Tuple
import json
import logging

from pydantic import BaseModel, Field
import re

from src.external_knowledge.search_service import WebSearchClient
from src.core.state import Doc
from src.llm_adapter import llm_client
from src.utils.prompt import QUERY_DECOMPOSE_PROMPT, QUERY_DECOMPOSE_THINK_PROMPT, SEARCH_REASONING_PROMPT, ANSWER_PROMPT
from src.utils.cache import DiskCache
from src.utils.observability import measure

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class StreamMode(BaseModel):
    """流式模式
    args:
        mode: 流式模式 general 普通流式 token 按token流式 time 按时间流式
        token: 流式模式下，每多少个token输出一次
        time: 流式模式下，每多少秒输出一次
    """
    mode: Literal["general", "token", "time"] = Field(default="general")
    token: Optional[int] = Field(default=5, ge=1)
    time: Optional[int] = Field(default=5, ge=1)

async def query_decompose(
        query: str,
        **kwargs
):
    current_date = time.strftime("%Y-%m-%d", time.localtime())
    # think
    think_content = ""
    async def _iter_with_timeout(gen, timeout):
        try:
            while True:
                item = await asyncio.wait_for(gen.__anext__(), timeout)
                yield item
        except StopAsyncIteration:
            return

    try:
        gen = llm_client.generate(QUERY_DECOMPOSE_THINK_PROMPT.format(task=query, retrieval_str=""))
        async for chunk in _iter_with_timeout(gen, int(os.getenv("LLM_TIMEOUT_SECONDS", 60))):
            if chunk:
                think_content += chunk
    except Exception as e:
        logger.warning(f"query_decompose think 超时/错误: {e}")

    logger.info(f"query_decompose think: {think_content}")

    # decompose
    messages = [
        {
            "role": "system",
            "content": QUERY_DECOMPOSE_PROMPT.format(
                current_date=current_date, max_queries=os.getenv("QUERY_DECOMPOSE_MAX_SIZE", 5))},
        {"role": "user", "content": f"思考结果：{think_content}"},
    ]
    extend_queries = ""
    try:
        gen2 = llm_client.generate_from_messages(messages=messages)
        async for chunk in _iter_with_timeout(gen2, int(os.getenv("LLM_TIMEOUT_SECONDS", 60))):
            if chunk:
                extend_queries += chunk
    except Exception as e:
        logger.warning(f"query_decompose queries 超时/错误: {e}")

    logger.info(f"query_decompose queries: {extend_queries}")

    # 解析
    queries = re.findall(r"^- (.+)$", extend_queries, re.MULTILINE)
    parsed_queries = [match.strip() for match in queries]
    
    # 如果没有解析到查询，尝试其他格式
    if not parsed_queries:
        # 尝试匹配其他可能的格式
        alt_patterns = [
            r"^(\d+)[\.\s]+(.+)$",  # 1. 查询内容
            r"^[\*\-]\s*(.+)$",     # * 查询内容 或 - 查询内容
            r"^(.+)$",              # 任何非空行
        ]
        
        for pattern in alt_patterns:
            matches = re.findall(pattern, extend_queries, re.MULTILINE)
            if matches:
                if len(matches[0]) == 2:  # 对于带编号的格式
                    parsed_queries = [match[1].strip() for match in matches]
                else:
                    parsed_queries = [match.strip() for match in matches]
                break
    
    # 如果仍然没有解析到查询，使用原始查询作为回退
    if not parsed_queries:
        logger.warning("无法解析子查询，使用原始查询作为回退")
        parsed_queries = [query]
    
    logger.info(f"解析到的子查询: {parsed_queries}")
    return parsed_queries


async def search_reasoning(query: str, content: str, **kwargs):
    """搜索推理判断"""
    reasoning_prompt = f"""
你是一个专业的研究分析师，负责判断当前收集的信息是否足够回答用户的问题。

【用户问题】
{query}

【当前收集的信息】
{content}

请判断当前信息是否足够回答用户问题：
1. 如果信息足够，返回 "1"
2. 如果信息不足，返回 "0"

请严格按照以下JSON格式输出：
{{
    "is_verify": "1或0",
    "reason": "判断理由"
}}
"""
    
    result = ""
    try:
        async def _iter_with_timeout(gen, timeout):
            try:
                while True:
                    item = await asyncio.wait_for(gen.__anext__(), timeout)
                    yield item
            except StopAsyncIteration:
                return
        gen = llm_client.generate(reasoning_prompt)
        async for chunk in _iter_with_timeout(gen, int(os.getenv("LLM_TIMEOUT_SECONDS", 60))):
            if chunk:
                result += chunk
    except Exception as e:
        logger.warning(f"search_reasoning 超时/错误: {e}")
    
    try:
        # 尝试解析JSON
        import json
        return json.loads(result)
    except:
        # 如果解析失败，返回默认值
        return {"is_verify": "0", "reason": "解析失败"}


async def answer_question(query: str, search_content: str, **kwargs):
    """生成最终答案"""
    answer_prompt = f"""
你是一个专业的研究分析师，请基于收集到的信息为用户提供详细、准确的答案。

【用户问题】
{query}

【收集到的信息】
{search_content}

请基于以上信息，为用户提供一个全面、准确的答案。要求：
1. 答案要全面覆盖用户问题的各个方面
2. 基于收集到的信息，不要编造信息
3. 如果信息不足，请明确指出
4. 答案要结构清晰，逻辑性强
5. 使用中文回答

请直接输出答案，不要包含其他格式标记。
"""
    
    try:
        async def _iter_with_timeout(gen, timeout):
            try:
                while True:
                    item = await asyncio.wait_for(gen.__anext__(), timeout)
                    yield item
            except StopAsyncIteration:
                return
        gen = llm_client.generate(answer_prompt)
        async for chunk in _iter_with_timeout(gen, int(os.getenv("LLM_TIMEOUT_SECONDS", 60))):
            if chunk:
                yield chunk
    except Exception as e:
        logger.warning(f"answer_question 超时/错误: {e}")

class DeepSearch:
    """深度搜索工具"""

    def __init__(self):
        self._search_single_query = WebSearchClient()
        self.searched_queries = []
        self.current_docs = []
        self.cache = DiskCache(os.path.join(os.getcwd(), "research_result", "cache"))

    def search_docs_str(self, model: str = None) -> str:
        current_docs_str = ""
        max_tokens = 10000
        for i, doc in enumerate(self.current_docs, start=1):
            current_docs_str += f"文档编号〔{i}〕. \n{doc.to_html()}\n"
        return current_docs_str

    @measure("external.deep_search.run")
    async def run(
            self,
            query: str,
            request_id: str = None,
            max_loop: int = 1,
            stream: bool = False,
            stream_mode: StreamMode = StreamMode(),
            *args,
            **kwargs
    ) -> List[Doc]:
        """深度搜索回复（流式）"""

        current_loop = 1
        # 执行深度搜索循环
        while current_loop <= max_loop:
            logger.info(f"{request_id} 第 {current_loop} 轮深度搜索...")
            # 查询分解
            # 缓存：查询分解
            cache_key = f"decompose::{query}"
            cached_sub_queries = self.cache.get(cache_key)
            if cached_sub_queries is None:
                sub_queries = await query_decompose(query=query)
                self.cache.set(cache_key, sub_queries)
            else:
                sub_queries = cached_sub_queries
            print(f"子查询{sub_queries}")
            await asyncio.sleep(0.1)

            # 去除已经检索过的query
            sub_queries = [sub_query for sub_query in sub_queries
                           if sub_query not in self.searched_queries]
            
            # 如果子查询为空，使用原始查询
            if not sub_queries:
                logger.warning("子查询为空，使用原始查询")
                if query not in self.searched_queries:
                    sub_queries = [query]
                else:
                    logger.warning("原始查询已经搜索过，跳过本轮搜索")
                    break
            
            # 并行搜索并去重
            searched_docs, docs_list = await self._search_queries_and_dedup(
                queries=sub_queries,
                request_id=request_id,
            )

            # 更新上下文
            self.current_docs.extend(searched_docs)
            self.searched_queries.extend(sub_queries)

            # 如果是最后一轮，直接跳出
            if current_loop == max_loop:
                break

            # 推理验证是否需要继续搜索
            # 缓存：推理判断
            reasoning_key = f"reasoning::{query}::{len(self.current_docs)}"
            cached_reasoning = self.cache.get(reasoning_key)
            if cached_reasoning is None:
                reasoning_result = await search_reasoning(
                    query=query,
                    content=self.search_docs_str(os.getenv("SEARCH_REASONING_MODEL")),
                )
                self.cache.set(reasoning_key, reasoning_result)
            else:
                reasoning_result = cached_reasoning

            # 如果推理判断已经可以回答，跳出循环
            if reasoning_result.get("is_verify", "1") in ["1", 1]:
                logger.info(f"{request_id} reasoning 判断没有得到新的查询，流程结束")
                break

            current_loop += 1
        return self.current_docs

        # # 生成最终答案
        # answer = ""
        # acc_content = ""
        # acc_token = 0
        # async for chunk in answer_question(
        #         query=query, search_content=self.search_docs_str(os.getenv("SEARCH_ANSWER_MODEL"))
        # ):
        #     if stream:
        #         if acc_token >= stream_mode.token:
        #             yield json.dumps({
        #                 "requestId": request_id,
        #                 "query": query,
        #                 "searchResult": {
        #                     "query": [],
        #                     "docs": [],
        #                 },
        #                 "answer": acc_content,
        #                 "isFinal": False,
        #                 "messageType": "report"
        #             }, ensure_ascii=False)
        #             acc_content = ""
        #             acc_token = 0
        #         acc_content += chunk
        #         acc_token += 1
        #     answer += chunk
        # if stream and acc_content:
        #     yield json.dumps({
        #         "requestId": request_id,
        #         "query": query,
        #         "searchResult": {
        #             "query": [],
        #             "docs": [],
        #         },
        #         "answer": acc_content,
        #         "isFinal": False,
        #         "messageType": "report"
        #     }, ensure_ascii=False)
        # yield json.dumps({
        #         "requestId": request_id,
        #         "query": query,
        #         "searchResult": {
        #             "query": [],
        #             "docs": [],
        #         },
        #         "answer": "" if stream else answer,
        #         "isFinal": True,
        #         "messageType": "report"
        #     }, ensure_ascii=False)

    async def _search_queries_and_dedup(
            self,
            queries: List[str],
            request_id: str,
    ) -> Tuple[List[Doc], List[List[Doc]]]:
        """异步并行搜索多个查询并去重"""
        def _run_async(*args, **kwargs):
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            s_result = loop.run_until_complete(self._search_single_query.search_and_dedup(*args, **kwargs))
            loop.close()
            return s_result

        process_list = []
        with ThreadPoolExecutor(max_workers=int(os.getenv("SEARCH_THREAD_NUM", 5))) as executor:
            for query in queries:
                process = executor.submit(_run_async, query, request_id)
                process_list.append(process)
        results = [process.result() for process in as_completed(process_list)]
        all_docs = [doc for docs in results for doc in docs]
        # 去重
        seen_content = set()
        deduped_docs = []
        for doc in all_docs:
            if doc.content and doc.content not in seen_content:
                deduped_docs.append(doc)
                seen_content.add(doc.content)
        return deduped_docs, results


if __name__ == '__main__':
    async def test_deepsearch():
        searcher = DeepSearch()
        return await searcher.run("中国目前的经济形式如何", stream=True)

    asyncio.run(test_deepsearch())



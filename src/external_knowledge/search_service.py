"""
外部搜索工具
集成多种搜索API获取最新信息
"""
import asyncio
import logging

import aiohttp
import requests
import json
import os
from dotenv import load_dotenv
from bs4 import BeautifulSoup
from typing import List
from src.core.state import Doc
from sogou_search import sogou_search

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 加载环境变量
load_dotenv()


class WebSearchClient:
    """
    网络搜索客户端
    支持多种搜索API
    """

    def __init__(self):
        self.serper_api_key = os.getenv("SERPER_API_KEY")
        self.google_api_key = os.getenv("SERPAPI_API_KEY")
        logger.info(f"初始化搜索客户端 - Serper API: {'已配置' if self.serper_api_key else '未配置'}, Google API: {'已配置' if self.google_api_key else '未配置'}")

    def search_with_serper(self, query: str, num_results: int = 5) -> list:
        """
        使用Serper API进行搜索，返回包含[title, snippet, url]的字典列表
        """
        if not self.serper_api_key:
            logger.warning("Serper API密钥未配置")
            return []

        url = "https://google.serper.dev/search"
        payload = json.dumps({
            "q": query,
            "num": num_results
        })
        headers = {
            'X-API-KEY': self.serper_api_key,
            'Content-Type': 'application/json'
        }

        try:
            logger.info(f"使用Serper API搜索: {query}")
            response = requests.post(url, headers=headers, data=payload)
            response.raise_for_status()
            data = response.json()
            results = data.get("organic", [])

            # 构建包含title, snippet, url的字典列表
            formatted_results = []
            for r in results:
                formatted_results.append({
                    "title": r.get("title", ""),
                    "snippet": r.get("snippet", ""),
                    "url": r.get("link", "")  # Serper API中使用"link"字段表示URL
                })

            logger.info(f"Serper搜索成功，获得 {len(formatted_results)} 个结果")
            return formatted_results
        except Exception as e:
            logger.error(f"Serper搜索失败: {str(e)}")
            return []

    def search_serpapi(self, query: str, num_results: int = 5) -> list:
        """使用SerpAPI搜索，返回包含[title, snippet, url]的字典列表"""
        serpapi_key = os.getenv("SERPAPI_API_KEY")
        if not serpapi_key:
            logger.warning("SerpAPI密钥未配置")
            return []
            
        url = "https://serpapi.com/search"
        params = {
            "q": query,
            "api_key": serpapi_key,
            "num": num_results
        }
        try:
            logger.info(f"使用SerpAPI搜索: {query}")
            response = requests.get(url, params=params)
            response.raise_for_status()
            data = response.json()
            results = data.get("organic_results", [])

            # 构建包含title, snippet, url的字典列表
            formatted_results = []
            for r in results:
                formatted_results.append({
                    "title": r.get("title", ""),
                    "snippet": r.get("snippet", ""),
                    "url": r.get("link", "")  # SerpAPI中使用"link"字段表示URL
                })

            logger.info(f"SerpAPI搜索成功，获得 {len(formatted_results)} 个结果")
            return formatted_results
        except Exception as e:
            logger.error(f"SerpAPI搜索失败: {str(e)}")
            return []

    def search_sogou(self, query: str, num_results: int = 5) -> list:
        logger.info("通过Sogou api 搜索")
        results = sogou_search(query, num_results, delay=0.5)
        formatted_results = []
        for r in results:
            formatted_results.append({
                "title": r.get("title", ""),
                "snippet": r.get("description", ""),
                "url": r.get("url", "")
            })

        logger.info(f"SogouAPI搜索成功，获得 {len(formatted_results)} 个结果")
        return formatted_results

    async def search(self, query):
        logger.info(f"开始搜索: {query}")

        results = self.search_serpapi(query)
        if not results:
            logger.info("SerpAPI无结果，尝试使用Serper")
            results = self.search_with_serper(query)
        if not results:
            logger.info("Serper无结果，尝试使用Sogou")
            results = self.search_sogou(query)
        
        if not results:
            logger.warning("所有搜索API都未返回结果，可能是API密钥未配置")
            logger.info("建议配置以下环境变量之一：")
            logger.info("- SERPER_API_KEY: 用于Serper API搜索")
            logger.info("- SERPAPI_API_KEY: 用于Google SerpAPI搜索")

        docs = [
            Doc(
                doc_type="web_page",
                content=item.get("snippet", ""),
                title=item.get("title", ""),
                link=item.get("url", ""),
            ) for item in results
        ]
        logger.info(f"搜索完成，创建了 {len(docs)} 个文档对象")
        return docs

    async def parser(self, docs):
        """
        解析文档链接获取完整内容
        """
        logger.info(f"开始解析 {len(docs)} 个文档")
        
        async def _parse(doc):
            """解析单个文档"""
            if not doc.link:
                logger.warning(f"文档 {doc.title} 没有链接，跳过解析")
                return doc
                
            async with aiohttp.ClientSession() as session:
                try:
                    logger.info(f"正在解析: {doc.link}")
                    async with session.get(doc.link, timeout=10) as response:
                        if response.status != 200:
                            logger.warning(f"HTTP {response.status} for {doc.link}")
                            return doc
                            
                        content_type = response.content_type.lower()
                        if content_type in [
                                "text/html", "text/plain", "text/xml", 
                                "application/json", "application/xml", 
                                "application/octet-stream"]:
                            
                            try:
                                html_content = await response.text()
                                soup = BeautifulSoup(html_content, "html.parser")
                                text_content = soup.get_text()
                                
                                # 清理文本内容
                                text_content = text_content.strip()
                                if len(text_content) > 50:
                                    doc.content = text_content
                                    logger.info(f"成功解析 {doc.link}，内容长度: {len(text_content)}")
                                else:
                                    logger.warning(f"解析内容过短: {doc.link}")
                            except Exception as e:
                                logger.error(f"解析HTML失败 {doc.link}: {str(e)}")
                        else:
                            logger.warning(f"不支持的内容类型 {content_type} for {doc.link}")
                            
                except UnicodeDecodeError as ude:
                    logger.error(f"编码错误 {doc.link}: {str(ude)}")
                except asyncio.TimeoutError:
                    logger.error(f"请求超时 {doc.link}")
                except Exception as e:
                    logger.error(f"解析失败 {doc.link}: {str(e)}")
                    
            return doc

        # 并发解析所有文档
        tasks = [asyncio.create_task(_parse(doc)) for doc in docs]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 处理异常结果
        parsed_docs = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"文档 {i} 解析异常: {str(result)}")
                parsed_docs.append(docs[i])  # 保留原始文档
            else:
                parsed_docs.append(result)
        
        logger.info(f"解析完成，成功解析 {len([d for d in parsed_docs if len(d.content) > 50])} 个文档")
        return parsed_docs

    async def search_and_dedup(
            self, query: str, request_id: str = None, *args, **kwargs
    ) -> List[Doc]:
        """
        搜索并去重，同时删除没有内容的文档
        """
        logger.info(f"开始搜索和去重流程，查询: {query}")
        
        # 搜索文档
        docs = await self.search(query=query)
        if not docs:
            logger.warning("搜索未返回任何结果，可能是API密钥未配置")
            # 创建一些模拟文档作为回退
            fallback_docs = [
                Doc(
                    doc_type="fallback",
                    content=f"关于'{query}'的相关信息。由于搜索API未配置，这里提供一些基础信息。建议配置SERPER_API_KEY或SERPAPI_API_KEY环境变量以获得更好的搜索结果。",
                    title=f"{query} - 基础信息",
                    link="",
                )
            ]
            logger.info("使用回退文档")
            return fallback_docs
            
        # 解析文档内容
        docs = await self.parser(docs=docs)

        # 去重处理
        seen_contents = set()
        deduped_docs = []
        
        for doc in docs:
            # 检查文档是否有有效内容
            if doc.content and len(doc.content.strip()) > 50:
                # 使用内容的前100个字符作为去重标识
                content_key = doc.content[:100].strip()
                if content_key not in seen_contents:
                    deduped_docs.append(doc)
                    seen_contents.add(content_key)
                    logger.info(f"添加文档: {doc.title}")
                else:
                    logger.info(f"跳过重复文档: {doc.title}")
            else:
                logger.info(f"跳过内容过短的文档: {doc.title}")
                
        logger.info(f"去重完成，最终返回 {len(deduped_docs)} 个文档")
        return deduped_docs


# 测试代码 - 仅在直接运行时执行
if __name__ == "__main__":
    async def test_search():
        search_client = WebSearchClient()
        result = await search_client.search_and_dedup(
            "Agent开发范式"
        )
        print(f"搜索结果数量: {len(result)}")
        for i, doc in enumerate(result):
            print(f"\n文档 {i+1}:")
            print(f"标题: {doc.title}")
            print(f"链接: {doc.link}")
            print(f"内容长度: {len(doc.content)}")
            print(f"内容预览: {doc.content[:200]}...")
    
    asyncio.run(test_search())



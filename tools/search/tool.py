"""
文件名: tools/search/tool.py
功能: 联网搜索工具 - LLM优化关键词 + 百度搜索 + 真实URL解析 + 多引擎正文抓取 + LLM摘要
依赖: tools.base, httpx, scrapling, newspaper3k, baidusearch, beautifulsoup4
"""
import re
import socket
import asyncio
from datetime import datetime
import httpx
from bs4 import BeautifulSoup
from loguru import logger
from ..base import BaseTool

try:
    from scrapling import Fetcher
    HAS_SCRAPLING = True
except ImportError:
    HAS_SCRAPLING = False

try:
    import newspaper
    HAS_NEWSPAPER = True
except ImportError:
    HAS_NEWSPAPER = False

try:
    from baidusearch.baidusearch import search as baidu_search
    HAS_BAIDU = True
except ImportError:
    HAS_BAIDU = False


class SearchTool(BaseTool):
    name = "web_search"
    description = "搜索互联网获取最新信息"
    priority = 40
    parameters = {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "搜索关键词"}
        },
        "required": ["query"]
    }

    def __init__(self, config: dict = None):
        super().__init__(config)
        self._agent = None

    def on_mount(self, agent):
        self._agent = agent

    async def execute(self, message: str, ctx: dict = None) -> dict:
        query = ""
        if isinstance(ctx, dict):
            query = ctx.get("query") or ctx.get("search_query") or message
        elif isinstance(ctx, str) and ctx.strip():
            query = ctx.strip()
        else:
            query = message

        if not query:
            return {"result": "错误: 没有搜索关键词"}

        logger.info(f"[搜索] 原始查询: {query}")

        optimized_query = await self._optimize_query(query)

        urls = await self._search_urls(optimized_query)
        if not urls:
            logger.warning(f"[搜索] 未找到结果: {optimized_query}")
            return {"result": f"未找到关于 '{query}' 的搜索结果，请尝试更换关键词。如果持续失败，请检查网络连接。"}

        logger.info(f"[搜索] 获取到 {len(urls)} 个链接")

        resolved_urls = await self._resolve_urls(urls)
        logger.info(f"[搜索] 解析出 {len(resolved_urls)} 个真实链接")

        articles = await self._fetch_articles(resolved_urls[:5])
        if not articles:
            logger.warning(f"[搜索] 抓取正文失败")
            return {"result": f"搜索 '{query}' 找到 {len(resolved_urls)} 个链接，但无法抓取页面内容。请检查网络连接后重试。"}

        logger.info(f"[搜索] 成功抓取 {len(articles)} 篇文章")

        full_text = f"搜索词: {optimized_query}\n\n"
        for i, article in enumerate(articles, 1):
            full_text += f"[来源 {i}] {article['title']}\n"
            full_text += f"链接: {article['url']}\n"
            full_text += f"内容:\n{article['content']}\n\n"

        summary = await self._summarize_results(full_text, query)
        if summary:
            return {"result": summary}

        return {"result": full_text[:2000]}

    async def _optimize_query(self, query: str) -> str:
        if not self._agent:
            return query
        try:
            now = datetime.now()
            today_str = f"{now.year}年{now.month}月{now.day}日"

            prompt = f"""将用户的问题转换为百度搜索的最佳关键词。

当前时间：{today_str}

规则：
1. 时间类：如果用户问"最近""今天""本周""这个月"，加上具体年月或日期
2. 技术类：中英混合，保留术语
3. 长句拆成2-5个关键词，用空格分隔
4. 只输出关键词，不要任何解释、标点、引号
5. 绝对不要加"区别""对比""哪个好""推荐""上映""评分""教程""入门""详解"等词，除非用户明确问了这些

用户问题：{query}
关键词："""

            resp = await self._agent.llm.chat(
                messages=[{"role": "user", "content": prompt}],
                model="qwen2.5:0.5b",
                temperature=0.1,
            )
            optimized = resp.get("message", {}).get("content", "").strip()
            if optimized and len(optimized) > 2:
                logger.info(f"[优化] {query} -> {optimized}")
                return optimized
        except Exception as e:
            logger.warning(f"[优化] 失败: {e}")
        return query

    async def _summarize_results(self, full_text: str, query: str) -> str:
        if not self._agent:
            return ""
        try:
            prompt = f"""根据以下搜索结果，用中文回答用户问题。即使信息不完全匹配，也提取所有可能有用的事实。

用户问题：{query}

搜索结果：
{full_text}

要求：
- 提取所有可能相关的时间、地点、数据、事件
- 按重要性列出，3-6条
- 总字数控制在1500字以内
- 如果确实没有任何相关信息，说明"未找到"
- 不要编造信息，搜索结果没有的不要说"""

            resp = await self._agent.llm.chat(
                messages=[{"role": "user", "content": prompt}],
                model="qwen2.5:3b-instruct",
                temperature=0.3,
            )
            summary = resp.get("message", {}).get("content", "").strip()
            if summary:
                return summary
        except Exception as e:
            logger.warning(f"[摘要] 失败: {e}")
        return ""

    async def _search_urls(self, query: str) -> list:
        if HAS_BAIDU:
            try:
                results = await asyncio.to_thread(baidu_search, query, num_results=15)
                urls = []
                for r in results:
                    title = r.get('title', '').strip()
                    url = r.get('url', '').strip()
                    if not title or not url or not url.startswith("http"):
                        continue
                    if any(x in url for x in ['chat.baidu.com', 'baidu.com/search']):
                        continue
                    urls.append({"title": title, "url": url})

                if len(urls) >= 3:
                    logger.info(f"[搜索] 百度返回 {len(urls)} 个有效结果")
                    return urls[:8]
                logger.info(f"[搜索] 百度仅 {len(urls)} 个有效结果，降级必应补充")
            except Exception as e:
                logger.error(f"[搜索] 百度搜索失败: {e}")

        return await self._bing_fallback(query)

    async def _bing_fallback(self, query: str) -> list:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                          "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "Accept-Language": "zh-CN,zh;q=0.9",
        }
        try:
            resp = httpx.get(
                "https://cn.bing.com/search",
                headers=headers,
                params={"q": query, "count": 10, "setmkt": "zh-CN"},
                timeout=10,
                follow_redirects=True
            )
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, 'html.parser')
            urls = []
            for item in soup.select("li.b_algo"):
                title_tag = item.select_one("h2 a")
                if title_tag:
                    title = title_tag.get_text(strip=True)
                    url = title_tag.get("href", "")
                    if url and url.startswith("http"):
                        urls.append({"title": title, "url": url})
            logger.info(f"[搜索] 必应返回 {len(urls)} 个结果")
            return urls[:8]
        except Exception as e:
            logger.error(f"[搜索] 必应降级也失败了: {e}")
            return []

    async def _resolve_urls(self, urls: list) -> list:
        resolved = []
        async with httpx.AsyncClient(timeout=5, follow_redirects=False) as client:
            for item in urls:
                url = item["url"]
                if "baidu.com/link" not in url:
                    resolved.append(item)
                    continue
                try:
                    resp = await client.head(url)
                    real_url = resp.headers.get("Location", "")
                    if real_url:
                        logger.info(f"[解析] {real_url[:80]}")
                        resolved.append({"title": item["title"], "url": real_url})
                    else:
                        resolved.append(item)
                except Exception:
                    resolved.append(item)
        return resolved

    async def _fetch_articles(self, urls: list) -> list:
        articles = []
        for item in urls:
            text = None
            logger.info(f"[抓取] {item['url'][:100]}")
            results = await asyncio.gather(
                self._try_scrapling(item["url"]),
                self._try_newspaper(item["url"]),
                self._try_httpx(item["url"]),
                return_exceptions=True
            )
            engine_names = ["Scrapling", "newspaper3k", "httpx"]
            for i, result in enumerate(results):
                if isinstance(result, str) and len(result) > 80:
                    text = result
                    logger.info(f"[抓取] ✅ {engine_names[i]} {len(result)}字")
                    break
            if not text:
                logger.warning(f"[抓取] ❌ 全部失败")
                continue
            soup = BeautifulSoup(text, 'html.parser')
            for tag in soup(['script', 'style', 'nav', 'footer', 'header', 'aside']):
                tag.decompose()
            clean = re.sub(r'\n\s*\n', '\n', soup.get_text())[:5000]
            articles.append({"title": item["title"], "url": item["url"], "content": clean})
        return articles[:3]

    async def _try_scrapling(self, url: str) -> str:
        if not HAS_SCRAPLING:
            raise Exception("未安装")
        f = Fetcher(auto_proxies=False)
        resp = await asyncio.wait_for(
            asyncio.to_thread(f.get, url),
            timeout=10
        )
        return resp.text if hasattr(resp, 'text') else str(resp.body)

    async def _try_newspaper(self, url: str) -> str:
        if not HAS_NEWSPAPER:
            raise Exception("未安装")
        article = newspaper.Article(url, timeout=10)
        await asyncio.wait_for(
            asyncio.to_thread(article.download),
            timeout=10
        )
        await asyncio.wait_for(
            asyncio.to_thread(article.parse),
            timeout=10
        )
        return article.text or ""

    async def _try_httpx(self, url: str) -> str:
        async with httpx.AsyncClient(timeout=10, follow_redirects=True) as client:
            resp = await client.get(url, headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "zh-CN,zh;q=0.9",
            })
            if resp.status_code == 200:
                return resp.text
            raise Exception(f"HTTP {resp.status_code}")
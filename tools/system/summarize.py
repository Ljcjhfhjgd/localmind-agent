"""
文件名: tools/system/summarize.py
功能: 链接总结工具 - 抓取网页内容并总结
依赖: tools.base, httpx, beautifulsoup4
"""
import re
import httpx
from bs4 import BeautifulSoup
from ..base import BaseTool


class SummarizeTool(BaseTool):
    name = "summarize_url"
    description = "抓取指定URL的网页内容并进行总结"
    priority = 59
    parameters = {
        "type": "object",
        "properties": {
            "url": {"type": "string", "description": "要总结的网页URL"},
            "language": {"type": "string", "description": "总结语言，默认中文"}
        },
        "required": ["url"]
    }

    def on_mount(self, agent):
        self._agent = agent

    async def execute(self, message: str, ctx: dict = None) -> dict:
        url = ""
        language = "中文"
        if isinstance(ctx, dict):
            url = ctx.get("url", "")
            language = ctx.get("language", "中文")
        elif isinstance(ctx, str) and ctx.strip():
            url = ctx.strip()

        if not url:
            return {"result": "❌ 请提供要总结的URL"}

        # 1. 抓取网页内容
        try:
            resp = httpx.get(
                url,
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                                  "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
                },
                timeout=15,
                follow_redirects=True
            )
            resp.raise_for_status()
        except Exception as e:
            return {"result": f"❌ 无法访问该网页: {e}"}

        # 2. 提取正文
        soup = BeautifulSoup(resp.text, 'html.parser')
        for tag in soup(['script', 'style', 'nav', 'footer', 'header', 'aside', 'form']):
            tag.decompose()

        article = soup.select_one('article, .article, .content, .post-body, #content, .main-content')
        if article:
            text = article.get_text()
        else:
            text = soup.get_text()

        text = re.sub(r'\n\s*\n', '\n', text).strip()
        if len(text) < 200:
            return {"result": "❌ 网页内容太少，无法总结"}

        text = text[:5000]

        # 3. 用 LLM 总结
        prompt = f"请用{language}简要总结以下网页内容（控制在300字以内）：\n\n{text}"

        try:
            resp = await self._agent.llm.chat(
                messages=[{"role": "user", "content": prompt}],
                model="qwen2.5:3b-instruct",
                temperature=0.3,
            )
            summary = resp.get("message", {}).get("content", "").strip()
            return {"result": summary or "总结失败"}
        except Exception as e:
            return {"result": f"总结出错: {e}"}
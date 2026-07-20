"""
文件名: llm/stream.py
功能: Ollama 流式响应处理器 - thinking 分离
依赖: httpx
"""
import json
import re
import httpx
from typing import AsyncGenerator
from loguru import logger


class StreamHandler:
    """流式响应处理器"""

    def __init__(self, config: dict = None):
        cfg = config or {}
        ollama_cfg = cfg.get("ollama", {})
        self.host = ollama_cfg.get("host", "localhost")
        self.port = ollama_cfg.get("port", 11434)
        self.base_url = f"http://{self.host}:{self.port}"
        self.stream_timeout = ollama_cfg.get("stream_timeout", 120)
        self.stream_temperature = ollama_cfg.get("stream_temperature", 0.7)
        self.stream_num_predict = ollama_cfg.get("stream_num_predict", 1024)

    async def stream(
        self,
        messages: list,
        model: str,
    ) -> AsyncGenerator[dict, None]:
        """流式调用，yield 分离的 think 和 text 事件"""
        payload = {
            "model": model,
            "messages": messages,
            "stream": True,
            "options": {
                "temperature": self.stream_temperature,
                "num_predict": self.stream_num_predict,
            }
        }

        try:
            async with httpx.AsyncClient(timeout=self.stream_timeout) as c:
                async with c.stream("POST", f"{self.base_url}/api/chat", json=payload) as r:
                    async for line in r.aiter_lines():
                        if not line:
                            continue
                        try:
                            data = json.loads(line)
                        except json.JSONDecodeError:
                            continue

                        if "message" in data:
                            msg = data["message"]

                            # thinking 内容
                            if "thinking" in msg and msg["thinking"]:
                                cleaned = self._clean_thinking(msg["thinking"])
                                if cleaned:
                                    yield {"type": "think", "content": cleaned}

                            # 正文内容
                            if "content" in msg and msg["content"]:
                                clean = re.sub(r'</?think>', '', msg["content"])
                                if clean.strip():
                                    yield {"type": "text", "content": clean}

                        if data.get("done"):
                            break

        except Exception as e:
            logger.error(f"流式调用失败: {e}")
            raise

    def _clean_thinking(self, text: str) -> str:
        """清洗 thinking 内容"""
        if not text:
            return ""
        text = re.sub(r'</?think>', '', text)
        text = re.sub(r'\n{3,}', '\n\n', text)
        return text.strip()
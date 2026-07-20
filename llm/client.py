"""
文件名: llm/client.py
功能: Ollama LLM 客户端 - 非流式调用 + 硅基流动 API 客户端
依赖: httpx
"""
import re
import httpx
from typing import Optional
from loguru import logger


class LLMClient:
    """Ollama LLM 客户端"""

    def __init__(self, config: dict = None):
        cfg = config or {}
        ollama_cfg = cfg.get("ollama", {})
        self.host = ollama_cfg.get("host", "localhost")
        self.port = ollama_cfg.get("port", 11434)
        self.base_url = f"http://{self.host}:{self.port}"
        self.default_model = ollama_cfg.get("default_model", "qwen2.5:7b-instruct")
        self.timeout = ollama_cfg.get("timeout", 60)
        self.temperature = ollama_cfg.get("temperature", 0.3)
        self.num_predict = ollama_cfg.get("num_predict", 256)

    async def chat(
        self,
        messages: list,
        model: str = None,
        tools: list = None,
        temperature: float = None,
        **kwargs,
    ) -> dict:
        """非流式调用"""
        payload = {
            "model": model or self.default_model,
            "messages": messages,
            "stream": False,
            "options": {
                "temperature": temperature or self.temperature,
                "num_predict": self.num_predict,
            }
        }
        if tools:
            payload["tools"] = tools

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as c:
                resp = await c.post(f"{self.base_url}/api/chat", json=payload)
                resp.raise_for_status()
                result = resp.json()

            if "message" in result and "content" in result["message"]:
                content = result["message"]["content"]
                content = re.sub(r'<think>.*?</think>', '', content, flags=re.DOTALL)
                result["message"]["content"] = content.strip()

            return result

        except Exception as e:
            logger.error(f"LLM 调用失败: {e}")
            raise

    async def chat_with_tools(
        self,
        messages: list,
        tools: list,
        model: str = None,
    ) -> dict:
        """带工具的非流式调用"""
        return await self.chat(messages, model=model, tools=tools)


class SiliconFlowLLM:
    """硅基流动 API 客户端（OpenAI 兼容格式）"""

    def __init__(self, config: dict = None):
        cfg = config or {}
        sf_cfg = cfg.get("siliconflow", {})
        self.api_key = sf_cfg.get("api_key", "")
        self.default_model = sf_cfg.get("default_model", "deepseek-ai/DeepSeek-V3.2")
        self.base_url = sf_cfg.get("base_url", "https://api.siliconflow.cn/v1/chat/completions")
        self.timeout = sf_cfg.get("timeout", 120)
        self.temperature = sf_cfg.get("temperature", 0.3)

    async def chat(
        self,
        messages: list,
        model: str = None,
        tools: list = None,
        temperature: float = None,
        **kwargs,
    ) -> dict:
        """非流式调用（OpenAI 兼容格式）"""
        payload = {
            "model": model or self.default_model,
            "messages": messages,
            "temperature": temperature or self.temperature,
        }
        if tools:
            payload["tools"] = tools

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as c:
                resp = await c.post(
                    self.base_url,
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json"
                    },
                    json=payload
                )
                resp.raise_for_status()
                data = resp.json()
                return {
                    "message": {
                        "role": "assistant",
                        "content": data["choices"][0]["message"]["content"]
                    }
                }

        except Exception as e:
            logger.error(f"硅基流动 API 调用失败: {e}")
            raise

    async def chat_with_tools(
        self,
        messages: list,
        tools: list,
        model: str = None,
    ) -> dict:
        """带工具的非流式调用"""
        return await self.chat(messages, model=model, tools=tools)
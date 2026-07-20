"""
文件名: tools/vision/tool.py
功能: 图片理解工具 - 调用视觉模型描述图片内容
依赖: tools.base, httpx
"""
import httpx
from loguru import logger
from ..base import BaseTool


class VisionTool(BaseTool):
    name = "vision_describe"
    description = "用视觉模型描述图片内容"
    priority = 15
    parameters = {
        "type": "object",
        "properties": {
            "image_base64": {"type": "string", "description": "图片的base64编码"}
        },
        "required": ["image_base64"]
    }

    def __init__(self, config: dict = None):
        super().__init__(config)
        vision_cfg = self.config.get("ollama", {}).get("mode_models", {})
        self.vision_model = vision_cfg.get("vision", "minicpm-v:latest")

    def can_handle(self, message: str, ctx: dict = None) -> bool:
        if not self.enabled:
            return False
        if not ctx:
            return False
        return ctx.get("has_image", False)

    async def execute(self, message: str, ctx: dict = None) -> dict:
        try:
            image_base64 = ctx.get("image_base64", "")
            if not image_base64:
                return {"result": "错误: 没有图片数据"}

            ollama_url = "http://localhost:11434"
            if self.agent:
                ollama_url = self.agent.llm.base_url

            async with httpx.AsyncClient(timeout=60) as c:
                resp = await c.post(f"{ollama_url}/api/chat", json={
                    "model": self.vision_model,
                    "messages": [{
                        "role": "user",
                        "content": "请描述这张图片的内容。如果是胸片X光图像，请详细描述器官结构、拍摄角度、图像质量。200-300字。",
                        "images": [image_base64]
                    }],
                    "stream": False
                })
                resp.raise_for_status()
                content = resp.json().get("message", {}).get("content", "描述失败")
                return {"result": content}

        except Exception as e:
            logger.error(f"图片描述失败: {e}")
            return {"result": f"描述失败: {e}"}
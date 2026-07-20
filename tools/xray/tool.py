"""
文件名: tools/xray/tool.py
功能: 胸片诊断工具 - 实现 BaseTool 接口
依赖: tools.base, tools.xray.model
"""
import base64
from loguru import logger
from ..base import BaseTool
from .model import XRayModel


class XrayTool(BaseTool):
    name = "xray_diagnose"
    description = "对胸片X光图像进行AI辅助诊断，识别20种常见胸部疾病"
    priority = 20
    parameters = {
        "type": "object",
        "properties": {
            "image_base64": {"type": "string", "description": "图片的base64编码"}
        },
        "required": ["image_base64"]
    }

    def __init__(self, config: dict = None):
        super().__init__(config)
        xray_cfg = self.config.get("xray", {})
        model_path = xray_cfg.get("model_path", "tools/xray/xray_models/best_classifier.pth")
        self.model = XRayModel(model_path=model_path)

    def can_handle(self, message: str, ctx: dict = None) -> bool:
        if not self.enabled:
            return False
        if not ctx:
            return False
        return ctx.get("is_xray", False)

    async def execute(self, message: str, ctx: dict = None) -> dict:
        try:
            image_base64 = ctx.get("image_base64", "")
            if not image_base64:
                return {"result": "错误: 没有图片数据"}

            image_bytes = base64.b64decode(image_base64)
            result = self.model.predict(image_bytes)

            category_emoji = {"正常": "✅", "建议复查": "⚠️", "异常": "❌"}
            emoji = category_emoji.get(result["category"], "")

            top3_str = ", ".join([
                f"{d['disease_cn']}({d['probability']}%)"
                for d in result["top3"]
            ])

            output = (
                f"{emoji} 判定: {result['category']}\n"
                f"理由: {result['reason']}\n"
                f"未见异常概率: {result['no_finding_prob']}%\n"
                f"Top3可疑疾病: {top3_str}"
            )

            # 返回全部 20 类概率
            all_probs = self.model.predict_all(image_bytes)

            return {
                "result": output,
                "all_probs": all_probs
            }

        except Exception as e:
            logger.error(f"胸片诊断失败: {e}")
            return {"result": f"诊断失败: {e}"}
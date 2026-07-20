"""
文件名: tools/system/translate.py
功能: 翻译工具 - 多语言互译
依赖: tools.base
"""
from ..base import BaseTool


LANG_MAP = {
    # 中文
    "中文": "zh", "汉语": "zh", "简体中文": "zh", "繁体中文": "zh",
    # 英文
    "英文": "en", "英语": "en",
    # 日语
    "日语": "ja", "日文": "ja", "日本语": "ja",
    # 韩语
    "韩语": "ko", "韩文": "ko", "朝鲜语": "ko",
    # 法语
    "法语": "fr", "法文": "fr",
    # 德语
    "德语": "de", "德文": "de",
    # 西班牙语
    "西班牙语": "es", "西班牙文": "es", "西语": "es",
    # 俄语
    "俄语": "ru", "俄文": "ru",
    # 意大利语
    "意大利语": "it", "意大利文": "it",
    # 葡萄牙语
    "葡萄牙语": "pt", "葡萄牙文": "pt",
    # 阿拉伯语
    "阿拉伯语": "ar", "阿拉伯文": "ar",
}


class TranslateTool(BaseTool):
    name = "translate"
    description = "多语言翻译，支持中文、英文、日语、韩语、法语、德语、西班牙语、俄语等互译"
    priority = 58
    parameters = {
        "type": "object",
        "properties": {
            "text": {"type": "string", "description": "要翻译的文本"},
            "target": {"type": "string", "description": "目标语言，如 中文、英文、日语、韩语、法语"}
        },
        "required": ["text", "target"]
    }

    def on_mount(self, agent):
        self._agent = agent

    async def execute(self, message: str, ctx: dict = None) -> dict:
        text = ""
        target = "中文"
        if isinstance(ctx, dict):
            text = ctx.get("text", "")
            target = ctx.get("target", "中文")
        elif isinstance(ctx, str) and ctx.strip():
            text = ctx.strip()
        target_code = LANG_MAP.get(target, target)

        prompt = f"将以下文本翻译为{target}。只输出翻译结果，不要任何解释：\n\n{text}"

        try:
            resp = await self._agent.llm.chat(
                messages=[{"role": "user", "content": prompt}],
                model="qwen2.5:3b-instruct",
                temperature=0.1,
            )
            result = resp.get("message", {}).get("content", "").strip()
            return {"result": result or "翻译失败"}
        except Exception as e:
            return {"result": f"翻译出错: {e}"}
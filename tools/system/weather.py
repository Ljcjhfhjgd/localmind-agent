"""
文件名: tools/system/weather.py
功能: 天气查询工具 - wttr.in 免费API
依赖: tools.base, httpx
"""
import httpx
from ..base import BaseTool


class WeatherTool(BaseTool):
    name = "get_weather"
    description = "查询指定城市的实时天气"
    priority = 57
    parameters = {
        "type": "object",
        "properties": {
            "city": {"type": "string", "description": "城市名称，如 北京、上海、东京"}
        },
        "required": ["city"]
    }

    async def execute(self, message: str, ctx: dict = None) -> dict:
        city = "北京"
        if isinstance(ctx, dict):
            city = ctx.get("city", "北京")
        elif isinstance(ctx, str) and ctx.strip():
            city = ctx.strip()
        try:
            resp = httpx.get(
                f"https://wttr.in/{city}?format=%l:+%c+%t+%h+%w",
                timeout=5
            )
            return {"result": f"🌤 {city}天气: {resp.text.strip()}"}
        except:
            return {"result": f"❌ 无法获取 {city} 的天气"}
"""
文件名: tools/__init__.py
功能: 工具包入口
"""
from .base import BaseTool
from .registry import ToolRegistry

from .rag.tool import RAGTool
from .xray.tool import XrayTool
from .vision.tool import VisionTool
from .search.tool import SearchTool
from .code.tool import CodeTool, CalculateTool
from .system.tool import (
    GetTimeTool, RememberTool, RecallTool, SendEmailTool
)
from .system.weather import WeatherTool
from .system.translate import TranslateTool
from .system.summarize import SummarizeTool


def create_default_registry(config: dict = None):
    registry = ToolRegistry(config)
    registry.register(VisionTool(config))
    registry.register(XrayTool(config))
    registry.register(RAGTool(config))
    registry.register(SearchTool(config))
    registry.register(CodeTool(config))
    registry.register(CalculateTool(config))
    registry.register(GetTimeTool(config))
    registry.register(RememberTool(config))
    registry.register(RecallTool(config))
    registry.register(SendEmailTool(config))
    registry.register(WeatherTool(config))
    registry.register(TranslateTool(config))
    registry.register(SummarizeTool(config))
    return registry
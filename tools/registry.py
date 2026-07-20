"""
文件名: tools/registry.py
功能: 工具注册中心 - 管理所有工具的注册、查找、执行
依赖: tools.base
"""
from typing import Dict, List, Optional
from .base import BaseTool


class ToolRegistry:
    """工具注册中心"""

    def __init__(self, config: dict = None):
        self.config = config or {}
        self._tools: Dict[str, BaseTool] = {}

    def register(self, tool: BaseTool):
        """注册工具"""
        self._tools[tool.name] = tool

    def unregister(self, name: str):
        """移除工具"""
        self._tools.pop(name, None)

    def get(self, name: str) -> Optional[BaseTool]:
        """获取指定工具"""
        return self._tools.get(name)

    def get_all(self) -> List[BaseTool]:
        """获取所有工具（按优先级排序）"""
        return sorted(self._tools.values(), key=lambda t: t.priority)

    def get_enabled(self) -> List[BaseTool]:
        """获取已启用的工具"""
        return [t for t in self._tools.values() if t.enabled]

    def find_handlers(self, message: str, ctx: dict = None) -> List[BaseTool]:
        """找到能处理当前请求的工具"""
        return [t for t in self.get_enabled() if t.can_handle(message, ctx)]

    def get_ollama_schemas(self) -> list:
        """获取所有工具的 Ollama Function Calling 格式"""
        return [t.to_ollama_schema() for t in self.get_enabled()]

    def toggle(self, name: str) -> bool:
        """切换启用状态"""
        tool = self._tools.get(name)
        if tool:
            tool.enabled = not tool.enabled
            return True
        return False

    def status(self) -> list:
        """获取所有工具状态"""
        return [
            {"name": name, "enabled": tool.enabled, "priority": tool.priority}
            for name, tool in self._tools.items()
        ]

    def __contains__(self, name: str) -> bool:
        return name in self._tools

    def __len__(self) -> int:
        return len(self._tools)
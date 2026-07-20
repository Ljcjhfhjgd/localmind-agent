"""
文件名: tools/base.py
功能: 工具基类 - 定义统一接口，所有工具必须继承
依赖: 无
"""
from abc import ABC, abstractmethod
from typing import Any, Optional


class BaseTool(ABC):
    """工具基类
    
    每个工具需要实现：
    - name: 工具名称（唯一标识）
    - description: 工具描述（给 LLM 看）
    - parameters: 参数 schema（JSON Schema 格式）
    - execute(): 执行逻辑
    
    可选：
    - can_handle(): 条件判断，默认返回 enabled
    - priority: 优先级，数字越小越先执行
    - on_mount(): 挂载到 Agent 时的回调
    """

    name: str = ""
    description: str = ""
    parameters: dict = {}
    priority: int = 50
    enabled: bool = True

    def __init__(self, config: dict = None):
        self.config = config or {}
        self.agent = None
        
        # 从配置读取是否启用
        tool_cfg = self.config.get("tools", {}).get(self.name, {})
        if "enabled" in tool_cfg:
            self.enabled = tool_cfg["enabled"]

    def can_handle(self, message: str, ctx: dict = None) -> bool:
        """判断是否能处理当前请求，默认返回是否启用"""
        return self.enabled

    @abstractmethod
    async def execute(self, message: str, ctx: dict = None) -> dict:
        """执行工具逻辑
        
        Args:
            message: 用户消息
            ctx: 上下文字典，包含文件信息等
            
        Returns:
            {"result": "处理结果字符串"}
        """
        ...

    def to_ollama_schema(self) -> dict:
        """转为 Ollama Function Calling 格式"""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            }
        }

    def on_mount(self, agent):
        """挂载到 Agent 时调用"""
        self.agent = agent

    def __repr__(self):
        status = "✓" if self.enabled else "✗"
        return f"<{self.name} [{status}]>"
"""
文件名: mcp/client.py
功能: MCP 客户端 - 管理外部 MCP Server 连接和工具调用
依赖: 无
"""
import json
import asyncio
from typing import Optional
from loguru import logger


class MCPClient:
    """MCP 客户端
    
    管理外部 MCP Server 的连接和工具调用。
    目前支持本地模拟模式，后续可扩展 stdio 通信。
    """

    def __init__(self, config: dict = None):
        self.config = config or {}
        self.servers = {}
        self.tools = []
        self._connected = False

    async def connect(self):
        """连接所有已配置的 MCP Server"""
        server_configs = self.config.get("mcp", {}).get("servers", {})

        for name, cfg in server_configs.items():
            if cfg.get("enabled", True):
                await self._connect_server(name, cfg)

        self._connected = True
        logger.info(f"MCP 客户端就绪, {len(self.tools)} 个工具")

    async def _connect_server(self, name: str, cfg: dict):
        """连接单个 MCP Server"""
        try:
            # 本地模拟模式
            if cfg.get("type") == "local":
                tools = cfg.get("tools", [])
                for tool in tools:
                    tool["server"] = name
                self.tools.extend(tools)
                self.servers[name] = {"status": "connected", "tools": len(tools)}
                logger.info(f"MCP Server [{name}] 连接成功: {len(tools)} 个工具")
            else:
                logger.warning(f"MCP Server [{name}] 类型不支持: {cfg.get('type')}")
        except Exception as e:
            logger.error(f"MCP Server [{name}] 连接失败: {e}")
            self.servers[name] = {"status": "error", "error": str(e)}

    def get_tools(self) -> list:
        """获取所有 MCP 工具"""
        return self.tools if self._connected else []

    async def execute(self, tool_name: str, args: dict) -> str:
        """执行 MCP 工具调用"""
        logger.info(f"MCP 执行: {tool_name}")

        # 找到对应工具
        tool = None
        for t in self.tools:
            if t.get("name") == tool_name:
                tool = t
                break

        if not tool:
            return json.dumps({"error": f"未知工具: {tool_name}"}, ensure_ascii=False)

        # 根据 server 类型执行
        server = tool.get("server", "")
        server_cfg = self.config.get("mcp", {}).get("servers", {}).get(server, {})

        if server_cfg.get("type") == "local":
            return await self._execute_local(tool, args)
        else:
            return json.dumps({"error": "不支持的服务器类型"}, ensure_ascii=False)

    async def _execute_local(self, tool: dict, args: dict) -> str:
        """本地执行工具（模拟）"""
        # 这里可以扩展实际的工具执行逻辑
        return json.dumps({"result": f"工具 {tool['name']} 执行完成"}, ensure_ascii=False)
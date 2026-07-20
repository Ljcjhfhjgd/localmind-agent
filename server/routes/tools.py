"""
文件名: server/routes/tools.py
功能: 工具管理路由 - 查看工具状态、开关工具
依赖: fastapi, agent.core
"""
from fastapi import APIRouter

router = APIRouter(prefix="/tools", tags=["工具"])


def get_agent():
    """获取 Agent 实例"""
    from server.routes.chat import get_agent as chat_get_agent
    return chat_get_agent()


@router.get("/status")
def tools_status():
    """获取所有工具状态"""
    agent = get_agent()
    return {"tools": agent.tools.status()}


@router.post("/toggle/{tool_name}")
def toggle_tool(tool_name: str):
    """切换工具启用状态"""
    agent = get_agent()
    success = agent.tools.toggle(tool_name)
    if success:
        tool = agent.tools.get(tool_name)
        return {"status": "ok", "name": tool_name, "enabled": tool.enabled}
    return {"status": "error", "message": f"工具不存在: {tool_name}"}
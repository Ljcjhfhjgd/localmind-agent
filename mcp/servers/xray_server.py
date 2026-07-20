"""
文件名: mcp/servers/xray_server.py
功能: 胸片诊断 MCP Server - 可独立运行的 MCP 服务
依赖: tools.xray.model
运行: python -m mcp.servers.xray_server
"""
import json
import base64
import io
import sys
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from tools.xray.model import XRayModel


class XRayMCPServer:
    """胸片诊断 MCP Server"""

    def __init__(self):
        self.model = XRayModel()

    def handle_request(self, request: dict) -> dict:
        """处理 MCP 请求"""
        method = request.get("method", "")

        if method == "tools/list":
            return {
                "tools": [
                    {
                        "name": "xray_diagnose",
                        "description": "对胸片X光图像进行AI辅助诊断",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "image_base64": {
                                    "type": "string",
                                    "description": "图片的base64编码"
                                }
                            },
                            "required": ["image_base64"]
                        }
                    }
                ]
            }

        elif method == "tools/call":
            params = request.get("params", {})
            tool_name = params.get("name", "")
            args = params.get("arguments", {})

            if tool_name == "xray_diagnose":
                image_base64 = args.get("image_base64", "")
                if not image_base64:
                    return {"error": "缺少 image_base64 参数"}

                try:
                    image_bytes = base64.b64decode(image_base64)
                    result = self.model.predict(image_bytes)
                    return {"content": [{"type": "text", "text": json.dumps(result, ensure_ascii=False)}]}
                except Exception as e:
                    return {"error": str(e)}

        return {"error": f"未知方法: {method}"}

    def run(self):
        """运行 MCP Server（stdio 模式）"""
        print("XRay MCP Server 启动", flush=True)
        for line in sys.stdin:
            try:
                request = json.loads(line.strip())
                response = self.handle_request(request)
                print(json.dumps(response, ensure_ascii=False), flush=True)
            except json.JSONDecodeError:
                print(json.dumps({"error": "无效的 JSON"}), flush=True)
            except Exception as e:
                print(json.dumps({"error": str(e)}), flush=True)


if __name__ == "__main__":
    server = XRayMCPServer()
    server.run()
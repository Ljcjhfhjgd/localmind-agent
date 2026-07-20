"""
文件名: server/middleware/auth.py
功能: 鉴权中间件
依赖: fastapi, config.yaml
"""
from fastapi import HTTPException, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import yaml
from pathlib import Path

security = HTTPBearer(auto_error=False)


def load_api_key() -> str:
    """从配置文件加载 API Key"""
    config_path = Path("config.yaml")
    if config_path.exists():
        with open(config_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
        return config.get("server", {}).get("api_key", "")
    return ""


def verify_auth(credentials: HTTPAuthorizationCredentials = None):
    """验证 Bearer Token"""
    api_key = load_api_key()
    if not api_key:
        return None  # 未启用鉴权
    if not credentials or credentials.credentials != api_key:
        raise HTTPException(status_code=401, detail="未授权：Bearer Token 无效")
    return credentials
"""
文件名: server/middleware/rate_limit.py
功能: 请求频率限制中间件
依赖: fastapi, time
"""
import time
from fastapi import Request, HTTPException


class RateLimiter:
    """简单的内存频率限制器"""

    def __init__(self, per_minute: int = 60):
        self.per_minute = per_minute
        self._store = {}

    def check(self, client_ip: str) -> bool:
        """检查是否超过限制，返回 True 表示允许"""
        now = time.time()
        window_start = now - 60

        if client_ip not in self._store:
            self._store[client_ip] = []

        # 清理过期记录
        self._store[client_ip] = [
            t for t in self._store[client_ip] if t > window_start
        ]

        if len(self._store[client_ip]) >= self.per_minute:
            return False

        self._store[client_ip].append(now)
        return True


# 全局实例
_limiter = None


def get_limiter(per_minute: int = 60) -> RateLimiter:
    global _limiter
    if _limiter is None:
        _limiter = RateLimiter(per_minute)
    return _limiter
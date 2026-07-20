"""
文件名: server/app.py
功能: FastAPI 应用主入口 - 创建 app、注册中间件、挂载路由
"""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from loguru import logger

from server.routes.chat import router as chat_router
from server.routes.knowledge import router as knowledge_router
from server.routes.files import router as files_router
from server.routes.tools import router as tools_router
from server.routes.memory import router as memory_router


# 内置 API Key，用户需在设置面板输入此 Key 才能使用
API_KEY = "LM01-7Qk3-mP2x-9Nf5"

PUBLIC_PATHS = {"/", "/health", "/docs", "/openapi.json", "/ui", "/settings"}


def _is_public_path(path: str) -> bool:
    """判断路径是否跳过 API Key 验证（含静态文件）"""
    if path in PUBLIC_PATHS:
        return True
    if path.startswith("/docs") or path.startswith("/openapi"):
        return True
    if path.startswith("/files/uploads"):
        return True
    return False


def create_app() -> FastAPI:
    """创建并配置 FastAPI 应用"""
    app = FastAPI(
        title="LocalMind Agent",
        description="本地 AI 智能助手 API",
        version="1.0.0",
        docs_url="/docs",
        redoc_url=None,
    )

    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # API Key 鉴权中间件
    @app.middleware("http")
    async def check_api_key(request: Request, call_next):
        if request.method == "OPTIONS":
            return await call_next(request)
        if _is_public_path(request.url.path):
            return await call_next(request)
        user_key = request.headers.get("X-API-Key", "")
        if user_key == API_KEY:
            return await call_next(request)
        response = JSONResponse(status_code=403, content={"detail": "api_key_invalid", "message": "API Key 不正确"})
        response.headers["Access-Control-Allow-Origin"] = "*"
        return response

    # 请求日志中间件
    @app.middleware("http")
    async def log_requests(request: Request, call_next):
        start = time.time()
        response = await call_next(request)
        elapsed = time.time() - start
        logger.info(f"{request.method} {request.url.path} → {response.status_code} ({elapsed:.2f}s)")
        return response

    # 全局异常处理
    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        logger.error(f"未处理的异常: {exc}")
        return JSONResponse(
            status_code=500,
            content={"detail": "服务器内部错误"},
        )

    # 挂载路由
    app.include_router(chat_router)
    app.include_router(knowledge_router)
    app.include_router(files_router)
    app.include_router(tools_router)
    app.include_router(memory_router)

    from server.routes.email_data import router as email_data_router
    app.include_router(email_data_router)

    from server.routes.settings import router as settings_router
    app.include_router(settings_router)

    # 挂载上传文件静态目录，胸片刷新后可正常访问
    uploads_dir = Path("data/uploads")
    uploads_dir.mkdir(parents=True, exist_ok=True)
    app.mount("/files/uploads", StaticFiles(directory=str(uploads_dir)), name="uploads")

    # 根路由
    @app.get("/", tags=["系统"])
    def root():
        return {
            "name": "LocalMind Agent",
            "version": "1.0.0",
            "status": "running",
            "docs": "/docs",
        }

    # 健康检查
    @app.get("/health", tags=["系统"])
    def health():
        return {"status": "ok"}

    # 前端页面
    @app.get("/ui", tags=["系统"])
    def ui():
        for p in ["frontend/index.html", "web/index.html"]:
            path = Path(p)
            if path.exists():
                return FileResponse(str(path))
        return {"error": "前端页面未找到，请访问 /docs 查看 API 文档"}

    return app


app = create_app()
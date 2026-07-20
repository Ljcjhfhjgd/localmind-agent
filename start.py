"""
文件名: start.py
功能: LocalMind Agent 一键启动脚本 - 启动后端 + 前端
用法: python start.py
"""
import os
import sys
import signal
import subprocess
import shutil
import time
from pathlib import Path

import yaml
import httpx
from loguru import logger

ALL_MODES = ["normal", "agent", "rag", "xray", "email"]


def setup_logging() -> None:
    logs_dir = Path("logs")
    logs_dir.mkdir(exist_ok=True)
    logger.remove()
    logger.add(
        sys.stdout,
        level="INFO",
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <level>{message}</level>",
        colorize=True,
    )
    logger.add(
        str(logs_dir / "{time:YYYY-MM-DD}.log"),
        level="DEBUG",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} | {message}",
        rotation="00:00",
        retention=0,
        encoding="utf-8",
        enqueue=True,
    )
    logger.info("日志系统初始化完成")


def print_banner() -> None:
    print("""
╔══════════════════════════════════════════╗
║      🧠 LocalMind Agent v1.0             ║
║   本地 AI 智能助手 · 胸片诊断 · RAG     ║
╚══════════════════════════════════════════╝
    """)


def check_ollama() -> bool:
    print("[1/4] 检查 Ollama 服务...")
    if not shutil.which('ollama') and not shutil.which('ollama.exe'):
        print("❌ 未找到 Ollama，请先安装: https://ollama.com/download")
        logger.error("未找到 Ollama")
        return False
    try:
        r = httpx.get("http://localhost:11434/api/tags", timeout=5)
        if r.status_code == 200:
            models = [m["name"] for m in r.json().get("models", [])]
            print(f"✅ Ollama 运行中 ({len(models)} 个模型)")
            logger.info(f"Ollama 运行中，{len(models)} 个模型")
            for n in models:
                print(f"   📦 {n}")
            return True
    except Exception:
        pass
    print("⏳ 正在启动 Ollama...")
    logger.info("尝试启动 Ollama...")
    try:
        if sys.platform == 'win32':
            subprocess.Popen(['ollama', 'serve'], creationflags=subprocess.CREATE_NO_WINDOW)
        else:
            subprocess.Popen(['ollama', 'serve'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        for i in range(15):
            time.sleep(1)
            print(f"   等待... ({i+1}s)")
            try:
                r = httpx.get("http://localhost:11434/api/tags", timeout=2)
                if r.status_code == 200:
                    models = r.json().get("models", [])
                    print(f"✅ Ollama 已启动 ({len(models)} 个模型)")
                    logger.info(f"Ollama 已启动，{len(models)} 个模型")
                    return True
            except Exception:
                pass
        print("❌ Ollama 启动超时")
        logger.error("Ollama 启动超时")
        return False
    except Exception as e:
        print(f"❌ Ollama 启动失败: {e}")
        logger.error(f"Ollama 启动失败: {e}")
        return False


def init_data() -> None:
    print("\n[2/4] 初始化数据目录...")
    logger.info("初始化数据目录")
    dirs = ["data/uploads", "data/rag_db", "logs", "data/email/drafts", "data/email/sent"]
    for mode in ALL_MODES:
        dirs.append(f"data/conversations/{mode}")
    for d in dirs:
        Path(d).mkdir(parents=True, exist_ok=True)
    files = {
        "data/personal_memory.json": "[]",
        "data/settings.json": "{}",
    }
    for mode in ALL_MODES:
        files[f"data/conversations/{mode}/index.json"] = "[]"
    for f, content in files.items():
        p = Path(f)
        if not p.exists():
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(content, encoding='utf-8')
    print(f"✅ 数据目录就绪 (含 {len(ALL_MODES)} 个模式文件夹)")
    logger.info(f"数据目录就绪，{len(ALL_MODES)} 个模式")


def check_models() -> None:
    print("\n[3/4] 检查 AI 模型...")
    logger.info("检查 AI 模型")
    try:
        r = httpx.get("http://localhost:11434/api/tags", timeout=5)
        models = [m["name"] for m in r.json().get("models", [])]
        required = ["qwen2.5:3b-instruct", "qwen2.5:7b-instruct"]
        for name in required:
            if name in models:
                print(f"   ✅ Ollama 模型: {name}")
                logger.info(f"Ollama 模型就绪: {name}")
            else:
                print(f"   ⚠️  建议安装: ollama pull {name}")
                logger.warning(f"建议安装模型: {name}")
    except Exception as e:
        logger.warning(f"检查 Ollama 模型失败: {e}")
    cfg = load_config()
    xray_cfg = cfg.get('xray', {})
    model_path_str = xray_cfg.get('model_path', 'tools/xray/xray_models/best_classifier.pth')
    xray_path = Path(model_path_str)
    if xray_path.exists():
        size_mb = xray_path.stat().st_size / 1024 / 1024
        print(f"   ✅ 胸片模型 ({size_mb:.1f} MB)")
        logger.info(f"胸片模型就绪: {model_path_str} ({size_mb:.1f} MB)")
    else:
        print(f"   ⚠️  胸片模型未找到: {xray_path}")
        print(f"      胸片诊断功能不可用，其他功能正常")
        logger.warning(f"胸片模型未找到: {model_path_str}")


def load_config() -> dict:
    config_path = Path(__file__).resolve().parent / "config.yaml"
    if config_path.exists():
        with open(str(config_path), 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)
    logger.error("config.yaml 不存在")
    return {}


def start_services() -> None:
    print("\n[4/4] 启动 Web 服务...")
    cfg = load_config()
    server_cfg = cfg.get('server', {})
    host = server_cfg.get('host', '0.0.0.0')
    port = server_cfg.get('port', 8765)

    project_root = Path(__file__).resolve().parent

    # 启动后端
    print("   后端启动中...")
    backend = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "server.app:app", "--host", host, "--port", str(port)],
        cwd=str(project_root),
    )

    # 启动前端
    frontend_dir = project_root / "frontend"
    frontend = None
    if frontend_dir.exists() and (frontend_dir / "node_modules").exists():
        print("   前端启动中...")
        frontend = subprocess.Popen(
            ["npm", "run", "dev"],
            cwd=str(frontend_dir),
            shell=True,
        )

    print(f"""
  ┌──────────────────────────────────────────┐
  │  后端服务    http://localhost:{port}         │
  │  API 文档    http://localhost:{port}/docs    │""")
    if frontend:
        print(f"  │  前端页面    http://localhost:5173          │")
    print(f"""  │  模式数量    {len(ALL_MODES)} 个模式        │
  │  日志目录    logs/                        │
  └──────────────────────────────────────────┘

  按 Ctrl+C 停止所有服务
""")
    logger.info(f"启动服务: 后端 {host}:{port}" + (", 前端 5173" if frontend else ""))

    try:
        backend.wait()
    except KeyboardInterrupt:
        print("\n🛑 停止服务...")
        backend.terminate()
        if frontend:
            frontend.terminate()
        print("已停止")
        logger.info("服务已停止")


def main() -> None:
    setup_logging()
    print_banner()
    signal.signal(signal.SIGINT, lambda s, f: sys.exit(0))
    logger.info("LocalMind Agent 启动中...")
    if not check_ollama():
        print("\n❌ Ollama 未运行，请手动启动后再试")
        logger.error("启动失败: Ollama 未运行")
        sys.exit(1)
    init_data()
    check_models()
    try:
        start_services()
    except KeyboardInterrupt:
        print("\n🛑 服务已停止")
        logger.info("服务已停止")
    except Exception as e:
        print(f"\n❌ 服务异常: {e}")
        logger.exception(f"服务异常: {e}")


if __name__ == "__main__":
    main()
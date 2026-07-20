"""
文件名: server/routes/chat.py
功能: 对话相关路由 - 请求队列 + SSE + xray + multi_agent_step + selected_docs + 文档预览 + 邮件发送
依赖: fastapi, agent.core, asyncio
"""
import json
import asyncio
from fastapi import APIRouter, Form, UploadFile, File
from fastapi.responses import StreamingResponse
from agent.core import LocalMindAgent
from loguru import logger
import shutil
from pathlib import Path

router = APIRouter(prefix="/chat", tags=["对话"])

_agent: LocalMindAgent = None
_semaphore = asyncio.Semaphore(1)

VALID_MODES = {"normal", "agent", "rag", "xray", "email"}


def get_agent() -> LocalMindAgent:
    global _agent
    if _agent is None:
        _agent = LocalMindAgent("config.yaml")
    return _agent


@router.post("")
async def chat(
    message: str = Form(""),
    files: list[UploadFile] = File(None),
    search_on: str = Form("0"),
    conv_id: str = Form(""),
    model: str = Form(""),
    skip_user: str = Form("0"),
    selected_docs: str = Form(""),
):
    """对话接口（SSE 流式，信号量控制并发）"""
    agent = get_agent()

    logger.info(f"[队列] 收到请求: {message[:30]} (等待中: {1 if _semaphore.locked() else 0})")

    if conv_id and conv_id != agent.conversation.current_id:
        agent.switch_conversation(conv_id)

    if model and model in agent.mode_models:
        if model in VALID_MODES and model != agent.current_mode:
            agent.switch_mode(model)
        else:
            agent.model = agent.mode_models[model]
        logger.info(f"切换模型: {agent.model}, 模式: {agent.current_mode}")

    file_list = []
    if files:
        for f in files:
            if f.filename and f.filename.strip():
                file_list.append({
                    "name": f.filename,
                    "content": await f.read(),
                })

    search_enabled = (search_on == "1")
    skip_user_message = (skip_user == "1")

    docs_list = []
    if selected_docs:
        try:
            docs_list = json.loads(selected_docs)
        except:
            docs_list = [d.strip() for d in selected_docs.split(",") if d.strip()]

    async def event_stream():
        async with _semaphore:
            if docs_list:
                logger.info(f"[队列] 开始处理: {message[:30]}, 模式: {agent.current_mode}, 选中文档: {docs_list}")
            else:
                logger.info(f"[队列] 开始处理: {message[:30]}, 模式: {agent.current_mode}")
            finished_normally = False
            try:
                async for chunk in agent.chat(
                    message=message,
                    files=file_list if file_list else None,
                    search_on=search_enabled,
                    skip_user_message=skip_user_message,
                    selected_docs=docs_list,
                ):
                    event_type = chunk.get("type", "text")
                    if event_type == "done":
                        finished_normally = True
                        yield "data: [DONE]\n\n"
                    elif event_type == "text":
                        yield f"data: {json.dumps({'content': chunk['content']}, ensure_ascii=False)}\n\n"
                    elif event_type == "think":
                        yield f"data: {json.dumps({'think': chunk['content']}, ensure_ascii=False)}\n\n"
                    elif event_type == "search":
                        yield f"data: {json.dumps({'search': True, 'results': chunk.get('results', '')}, ensure_ascii=False)}\n\n"
                    elif event_type == "suggestions":
                        yield f"data: {json.dumps({'suggestions': chunk['content']}, ensure_ascii=False)}\n\n"
                    elif event_type == "cancelled":
                        yield f"data: {json.dumps({'cancelled': True, 'content': chunk['content']}, ensure_ascii=False)}\n\n"
                    elif event_type == "xray_diagnosis":
                        yield f"data: {json.dumps({'xray': chunk['content']}, ensure_ascii=False)}\n\n"
                    elif event_type == "xray_progress":
                        yield f"data: {json.dumps({'xray_progress': chunk['content']}, ensure_ascii=False)}\n\n"
                    elif event_type == "xray_results":
                        yield f"data: {json.dumps({'xray_results': chunk['content']}, ensure_ascii=False)}\n\n"
                    elif event_type == "xray_error":
                        yield f"data: {json.dumps({'xray_error': chunk['content']}, ensure_ascii=False)}\n\n"
                    elif event_type == "xray_rejected":
                        yield f"data: {json.dumps({'xray_rejected': chunk['content']}, ensure_ascii=False)}\n\n"
                    elif event_type == "refs":
                        yield f"data: {json.dumps({'refs': chunk['content']}, ensure_ascii=False)}\n\n"
                    elif event_type == "multi_agent_step":
                        yield f"data: {json.dumps({'type': 'multi_agent_step', 'content': chunk['content']}, ensure_ascii=False)}\n\n"
                    elif event_type == "title":
                        yield f"data: {json.dumps({'title': chunk['content']}, ensure_ascii=False)}\n\n"
                    elif event_type == "memory":
                        yield f"data: {json.dumps({'memory': chunk['content']}, ensure_ascii=False)}\n\n"
            except Exception as e:
                logger.error(f"SSE 异常: {e}")
                yield f"data: {json.dumps({'error': str(e)}, ensure_ascii=False)}\n\n"
                yield "data: [DONE]\n\n"
            finally:
                if not finished_normally:
                    try:
                        agent._save_partial("", stopped=True)
                    except:
                        pass
                logger.info(f"[队列] 完成: {message[:30]}")

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/xray/report")
async def generate_xray_report(conv_id: str = Form(...), file_name: str = Form(...)):
    agent = get_agent()

    async def event_stream():
        try:
            async for chunk in agent.generate_xray_report(conv_id, file_name):
                event_type = chunk.get("type", "text")
                if event_type == "done":
                    yield "data: [DONE]\n\n"
                elif event_type == "text":
                    yield f"data: {json.dumps({'content': chunk['content']}, ensure_ascii=False)}\n\n"
                elif event_type == "error":
                    yield f"data: {json.dumps({'error': chunk['content']}, ensure_ascii=False)}\n\n"
        except Exception as e:
            logger.error(f"报告生成异常: {e}")
            yield f"data: {json.dumps({'error': str(e)}, ensure_ascii=False)}\n\n"
            yield "data: [DONE]\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/xray/retry")
async def retry_single_xray(conv_id: str = Form(...), file_name: str = Form(...)):
    agent = get_agent()

    async def event_stream():
        try:
            async for chunk in agent.retry_single_xray(conv_id, file_name):
                event_type = chunk.get("type", "text")
                if event_type == "done":
                    yield "data: [DONE]\n\n"
                elif event_type == "think":
                    yield f"data: {json.dumps({'think': chunk['content']}, ensure_ascii=False)}\n\n"
                elif event_type == "xray_retry_result":
                    yield f"data: {json.dumps({'xray_retry_result': chunk['content']}, ensure_ascii=False)}\n\n"
                elif event_type == "error":
                    yield f"data: {json.dumps({'error': chunk['content']}, ensure_ascii=False)}\n\n"
        except Exception as e:
            logger.error(f"SSE 异常: {e}")
            yield f"data: {json.dumps({'error': str(e)}, ensure_ascii=False)}\n\n"
            yield "data: [DONE]\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/stop")
def stop_chat():
    agent = get_agent()
    agent.cancel()
    logger.info("[队列] 收到停止请求")
    return {"status": "stopped"}


@router.post("/save_partial")
def save_partial(content: str = Form(""), stopped: str = Form("0")):
    agent = get_agent()
    agent._save_partial(content, stopped=(stopped == "1"))
    return {"status": "saved"}


@router.get("/history")
def get_history(conv_id: str = None):
    agent = get_agent()
    if conv_id:
        agent.switch_conversation(conv_id)
    return {"history": agent.get_history()}


@router.delete("/history")
def clear_history():
    agent = get_agent()
    agent.clear_history()
    return {"status": "cleared"}


@router.get("/rag/collections/{name}")
async def get_collection_content(name: str):
    from pathlib import Path
    from urllib.parse import unquote
    name = unquote(name)
    data_path = Path("data/rag_db")
    for d in data_path.iterdir():
        if d.is_dir() and (d / "metadata.json").exists():
            try:
                meta = json.loads((d / "metadata.json").read_text(encoding='utf-8'))
                if meta.get("display_name") == name:
                    original = d / "original"
                    if original.exists():
                        ext = original.suffix.lower()
                        if ext == '.pdf':
                            from PyPDF2 import PdfReader
                            reader = PdfReader(str(original))
                            content = "\n".join(page.extract_text() or "" for page in reader.pages)
                        elif ext == '.docx':
                            from docx import Document
                            doc = Document(str(original))
                            content = "\n".join(p.text for p in doc.paragraphs)
                        else:
                            try:
                                content = original.read_text(encoding='utf-8')
                            except:
                                content = original.read_text(encoding='gbk')
                        return {"content": content, "name": name}
                    else:
                        chunks = meta.get("chunks", [])
                        content = "\n\n".join(c.get("content", "") for c in chunks)
                        return {"content": content, "name": name}
            except:
                pass
    return {"content": "文件不存在", "name": name}


@router.get("/conversations")
def list_conversations(mode: str = None):
    agent = get_agent()
    if mode:
        conversations = agent.list_conversations_by_mode(mode)
    else:
        conversations = agent.list_conversations()
    return {
        "conversations": conversations,
        "current": agent.conversation.current_id,
        "current_mode": agent.current_mode,
    }


@router.get("/conversations/all")
def list_all_conversations():
    agent = get_agent()
    return {
        "modes": agent.list_all_modes_conversations(),
        "current_mode": agent.current_mode,
    }


@router.post("/conversations/new")
def new_conversation(mode: str = Form("normal")):
    agent = get_agent()
    if mode != agent.current_mode:
        agent.switch_mode(mode)
    conv_id = agent.create_conversation()
    return {"conv_id": conv_id, "mode": mode}


@router.post("/conversations/switch")
def switch_conversation(conv_id: str = Form(...), mode: str = Form("")):
    agent = get_agent()
    if mode and mode != agent.current_mode:
        agent.switch_mode(mode)
    success = agent.switch_conversation(conv_id)
    return {"status": "ok" if success else "not_found"}


@router.delete("/conversations/{conv_id}")
def delete_conversation(conv_id: str):
    agent = get_agent()
    if agent.conversation.current_id == conv_id:
        agent.conversation.current_id = None
        agent.conversation.messages = []
    agent.delete_conversation(conv_id)
    return {"status": "deleted"}


@router.post("/conversations/save")
def save_conversation():
    agent = get_agent()
    import asyncio as aio
    aio.run(agent.conversation.save())
    return {"status": "saved"}


@router.post("/conversations/pop")
def pop_last_message():
    agent = get_agent()
    if agent.conversation.messages:
        agent.conversation.messages.pop()
        import asyncio as aio
        aio.run(agent.conversation.save())
        return {"status": "popped"}
    return {"status": "empty"}


@router.get("/mode")
def get_mode():
    agent = get_agent()
    return {
        "current_mode": agent.current_mode,
        "model": agent.model,
        "available": list(agent.mode_models.keys()),
    }

PROMPTS_DIR = Path("agent/prompts/templates")

@router.get("/prompts/{name}")
def get_prompt(name: str):
    path = PROMPTS_DIR / f"{name}.txt"
    if path.exists():
        return {"content": path.read_text(encoding='utf-8')}
    return {"content": ""}

@router.post("/mode/switch")
def switch_mode(mode: str = Form(...)):
    agent = get_agent()
    return agent.switch_mode(mode)


@router.get("/mode/info")
def get_mode_info():
    agent = get_agent()
    return {
        "mode": agent.current_mode,
        "model": agent.model,
        "tools": [t.name for t in agent.tools.get_enabled()],
        "knowledge_mode": agent.conversation.knowledge_mode,
    }


@router.post("/role/set")
def set_role_prompt(role_name: str = Form(...), role_prompt: str = Form(...)):
    agent = get_agent()
    agent.conversation.role_prompt = role_prompt
    agent.conversation.role_name = role_name
    return {"status": "ok", "role": role_name}


@router.get("/role/current")
def get_role():
    agent = get_agent()
    return {
        "role_name": getattr(agent.conversation, "role_name", None),
        "role_prompt": getattr(agent.conversation, "role_prompt", None),
    }


@router.post("/knowledge/toggle")
def toggle_knowledge():
    agent = get_agent()
    return agent.toggle_knowledge_mode()


@router.get("/knowledge/status")
def knowledge_status():
    agent = get_agent()
    return {"knowledge_mode": agent.conversation.knowledge_mode}


@router.get("/mode/config")
def get_mode_config():
    from pathlib import Path
    MODE_CONFIG_PATH = Path("data/mode_config.json")
    if MODE_CONFIG_PATH.exists():
        try:
            return json.loads(MODE_CONFIG_PATH.read_text(encoding="utf-8"))
        except:
            pass
    return {
        "mode_order": ["normal", "agent", "rag", "xray", "code", "data", "email"],
        "enabled_modes": ["normal", "agent", "rag", "xray", "code", "data", "email"],
    }


@router.post("/mode/config")
def save_mode_config(mode_order: str = Form(""), enabled_modes: str = Form("")):
    from pathlib import Path
    MODE_CONFIG_PATH = Path("data/mode_config.json")
    try:
        config = {
            "mode_order": json.loads(mode_order) if mode_order else [],
            "enabled_modes": json.loads(enabled_modes) if enabled_modes else [],
        }
        MODE_CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
        MODE_CONFIG_PATH.write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")
        return {"status": "ok"}
    except Exception as e:
        return {"status": "error", "message": str(e)}


@router.post("/email/send")
async def send_email(
    payload: str = Form(""),
    files: list[UploadFile] = File(None),
):
    try:
        data = json.loads(payload)
        to = data.get("to", [])
        subject = data.get("subject", "")
        body = data.get("body", "")
        cc = data.get("cc", [])
        bcc = data.get("bcc", [])
    except:
        return {"success": False, "error": "参数解析失败"}

    agent = get_agent()
    email_tool = agent.tools.get("send_email")
    if not email_tool or not email_tool.enabled:
        return {"success": False, "error": "邮件工具未启用"}

    import json as _json
    from pathlib import Path as _Path
    settings_path = _Path("data/settings.json")
    if settings_path.exists():
        try:
            settings = _json.loads(settings_path.read_text(encoding='utf-8'))
            sender_email = settings.get("email", {}).get("senderEmail", "")
            auth_code = settings.get("email", {}).get("authCode", "")
            if sender_email and auth_code:
                email_tool.sender.sender = sender_email
                email_tool.sender.auth = auth_code
                email_tool.sender._ready = True
        except:
            pass

    attachments = []
    if files:
        for f in files:
            if f.filename and f.filename.strip():
                attachments.append({
                    "name": f.filename,
                    "content": await f.read(),
                })

    result = await email_tool.execute("", {
        "to_email": ", ".join(to) if isinstance(to, list) else to,
        "subject": subject,
        "body": body,
        "cc": ", ".join(cc) if isinstance(cc, list) else cc,
        "bcc": ", ".join(bcc) if isinstance(bcc, list) else bcc,
        "attachments": attachments,
    })

    result_text = result.get("result", "")
    if result_text.startswith("❌"):
        return {"success": False, "error": result_text}

    return {"success": True, "result": result_text}
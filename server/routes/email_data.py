"""
文件名: server/routes/email_data.py
功能: 邮件草稿/已发送/附件 后端存储
"""
import json
import shutil
import uuid
from pathlib import Path
from datetime import datetime
from fastapi import APIRouter, Form, UploadFile, File
from fastapi.responses import FileResponse
from loguru import logger

router = APIRouter(prefix="/email", tags=["邮件数据"])

DATA_DIR = Path("data/email")
DRAFTS_DIR = DATA_DIR / "drafts"
SENT_DIR = DATA_DIR / "sent"


def _ensure_dirs():
    DRAFTS_DIR.mkdir(parents=True, exist_ok=True)
    SENT_DIR.mkdir(parents=True, exist_ok=True)


def _read_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except:
        return {}


def _write_json(path: Path, data: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')


# ========== 草稿 ==========

@router.get("/drafts")
def list_drafts():
    _ensure_dirs()
    drafts = []
    for d in DRAFTS_DIR.iterdir():
        if d.is_dir():
            mail = _read_json(d / "mail.json")
            if mail:
                drafts.append({
                    "id": d.name, "to": mail.get("to", ""), "cc": mail.get("cc", ""),
                    "subject": mail.get("subject", ""), "updatedAt": mail.get("updatedAt", ""),
                    "convId": mail.get("convId", ""),
                })
    drafts.sort(key=lambda x: x.get("updatedAt", ""), reverse=True)
    return {"drafts": drafts}


@router.get("/drafts/{draft_id}")
def get_draft(draft_id: str):
    mail = _read_json(DRAFTS_DIR / draft_id / "mail.json")
    if not mail:
        return {"error": "草稿不存在"}
    attachments = _read_json(DRAFTS_DIR / draft_id / "attachments.json")
    return {"mail": mail, "attachments": attachments}


@router.post("/drafts")
def save_draft(
    draft_id: str = Form(""), to: str = Form(""), cc: str = Form(""),
    bcc: str = Form(""), subject: str = Form(""), body: str = Form(""),
    conv_id: str = Form(""),
):
    _ensure_dirs()
    d_id = draft_id or f"draft_{int(datetime.now().timestamp() * 1000)}"
    mail = {
        "id": d_id, "to": to, "cc": cc, "bcc": bcc,
        "subject": subject, "body": body,
        "convId": conv_id, "updatedAt": datetime.now().isoformat(),
    }
    _write_json(DRAFTS_DIR / d_id / "mail.json", mail)
    return {"id": d_id, "status": "saved"}


@router.delete("/drafts/{draft_id}")
def delete_draft(draft_id: str):
    d = DRAFTS_DIR / draft_id
    if d.exists():
        shutil.rmtree(d)
        logger.info(f"删除草稿: {draft_id}")
    return {"status": "deleted"}


# ========== 已发送 ==========

@router.get("/sent")
def list_sent():
    _ensure_dirs()
    sent = []
    for d in SENT_DIR.iterdir():
        if d.is_dir():
            mail = _read_json(d / "mail.json")
            if mail:
                sent.append({
                    "id": d.name, "to": mail.get("to", ""), "cc": mail.get("cc", ""),
                    "subject": mail.get("subject", ""), "body": mail.get("body", ""),
                    "attachments": mail.get("attachments", []),
                    "sentAt": mail.get("sentAt", ""),
                })
    sent.sort(key=lambda x: x.get("sentAt", ""), reverse=True)
    return {"sent": sent}


@router.get("/sent/{sent_id}")
def get_sent(sent_id: str):
    mail = _read_json(SENT_DIR / sent_id / "mail.json")
    if not mail:
        return {"error": "已发送记录不存在"}
    return {"mail": mail}


@router.post("/sent")
async def save_sent(
    to: str = Form(""), cc: str = Form(""), bcc: str = Form(""),
    subject: str = Form(""), body: str = Form(""),
    attachments: str = Form("[]"),
    files: list[UploadFile] = File(None),
):
    _ensure_dirs()
    s_id = f"sent_{int(datetime.now().timestamp() * 1000)}"
    mail = {
        "id": s_id, "to": to, "cc": cc, "bcc": bcc,
        "subject": subject, "body": body,
        "attachments": json.loads(attachments) if attachments else [],
        "sentAt": datetime.now().isoformat(),
    }
    _write_json(SENT_DIR / s_id / "mail.json", mail)
    
    # 保存附件文件
    if files:
        files_dir = SENT_DIR / s_id / "files"
        files_dir.mkdir(parents=True, exist_ok=True)
        for f in files:
            if f.filename:
                file_path = files_dir / f.filename
                content = await f.read()
                file_path.write_bytes(content)
    
    return {"id": s_id, "status": "saved"}


@router.get("/sent/{sent_id}/files/{filename}")
def get_sent_attachment(sent_id: str, filename: str):
    """获取已发送邮件的附件"""
    file_path = SENT_DIR / sent_id / "files" / filename
    if file_path.exists():
        return FileResponse(str(file_path), filename=filename)
    return {"error": "文件不存在"}


@router.delete("/sent/{sent_id}")
def delete_sent(sent_id: str):
    d = SENT_DIR / sent_id
    if d.exists():
        shutil.rmtree(d)
    return {"status": "deleted"}


# ========== 附件 ==========

@router.post("/attachments/{draft_id}")
async def upload_attachment(draft_id: str, file: UploadFile = File(...)):
    d = DRAFTS_DIR / draft_id
    files_dir = d / "files"
    files_dir.mkdir(parents=True, exist_ok=True)
    safe_name = f"{uuid.uuid4().hex[:8]}_{file.filename}"
    file_path = files_dir / safe_name
    file_path.write_bytes(await file.read())
    attachments = _read_json(d / "attachments.json")
    files_list = attachments.get("files", [])
    files_list.append({"name": file.filename, "size": file.size, "filename": safe_name})
    _write_json(d / "attachments.json", {"files": files_list})
    return {"status": "ok", "filename": safe_name}


@router.delete("/attachments/{draft_id}/{filename}")
def delete_attachment(draft_id: str, filename: str):
    file_path = DRAFTS_DIR / draft_id / "files" / filename
    if file_path.exists():
        file_path.unlink()
    attachments = _read_json(DRAFTS_DIR / draft_id / "attachments.json")
    files_list = [f for f in attachments.get("files", []) if f["filename"] != filename]
    _write_json(DRAFTS_DIR / draft_id / "attachments.json", {"files": files_list})
    return {"status": "deleted"}


@router.get("/attachments/{draft_id}/{filename}")
def download_attachment(draft_id: str, filename: str):
    file_path = DRAFTS_DIR / draft_id / "files" / filename
    if file_path.exists():
        return FileResponse(str(file_path), filename=filename)
    return {"error": "文件不存在"}
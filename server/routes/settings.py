"""
文件名: server/routes/settings.py
功能: 设置路由 - 全局配置 + SMTP 测试 + API Key 管理
"""
import json
import smtplib
from email.mime.text import MIMEText
from pathlib import Path
from fastapi import APIRouter, Form
from loguru import logger

router = APIRouter(prefix="/settings", tags=["设置"])

SETTINGS_PATH = Path("data/settings.json")

DEFAULT_SETTINGS = {
    "general": {"restoreLast": True, "autoTitle": True, "timestampFormat": "relative"},
    "memory": {"enabled": True},
    "email": {"smtpHost": "smtp.qq.com", "smtpPort": 465, "senderEmail": "", "authCode": ""},
    "tools": {
        "webSearch": True, "executeCode": True, "calculate": True,
        "readFile": True, "writeFile": True, "listFiles": True, "getCurrentTime": True
    }
}


def _read_settings() -> dict:
    if SETTINGS_PATH.exists():
        try:
            return json.loads(SETTINGS_PATH.read_text(encoding='utf-8'))
        except:
            pass
    return DEFAULT_SETTINGS.copy()


def _write_settings(data: dict):
    SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
    SETTINGS_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')


@router.get("")
def get_settings():
    return _read_settings()


@router.post("")
def save_settings(payload: str = Form("")):
    try:
        data = json.loads(payload)
        _write_settings(data)
        return {"status": "ok"}
    except Exception as e:
        return {"status": "error", "message": str(e)}


@router.post("/test-email")
def test_email(
    smtp_host: str = Form("smtp.qq.com"),
    smtp_port: int = Form(465),
    sender_email: str = Form(""),
    auth_code: str = Form(""),
    test_recipient: str = Form(""),
):
    try:
        msg = MIMEText("这是 LocalMind Agent 发送的测试邮件。\n配置验证成功！", "plain", "utf-8")
        msg["Subject"] = "LocalMind Agent - SMTP 测试邮件"
        msg["From"] = sender_email
        msg["To"] = test_recipient

        with smtplib.SMTP_SSL(smtp_host, smtp_port) as server:
            server.login(sender_email, auth_code)
            server.sendmail(sender_email, [test_recipient], msg.as_string())

        logger.info(f"测试邮件发送成功: {sender_email} → {test_recipient}")
        return {"status": "ok", "message": "测试邮件发送成功"}
    except smtplib.SMTPAuthenticationError:
        logger.warning(f"邮件授权码错误: {sender_email}")
        return {"status": "error", "detail": "email_auth_failed", "message": "邮件授权码错误"}
    except Exception as e:
        logger.warning(f"测试邮件发送失败: {e}")
        return {"status": "error", "message": str(e)}
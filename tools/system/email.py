"""
文件名: tools/system/email.py
功能: 邮件发送器 - QQ邮箱，支持附件
依赖: smtplib
"""
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email.mime.image import MIMEImage
from email import encoders
from email.utils import formataddr
from loguru import logger


class EmailSender:
    """邮件发送器"""

    def __init__(self, config: dict):
        self.host = config.get("smtp_host", "smtp.qq.com")
        self.port = config.get("smtp_port", 465)
        self.sender = config.get("sender_email", "")
        self.auth = config.get("auth_code", "")
        self._ready = bool(self.sender and self.auth)

    def send(self, to: str, subject: str, body: str, cc: str = "", bcc: str = "", attachments: list = None) -> str:
        if not self._ready:
            return "❌ 邮件未配置，请在设置中填写邮箱和授权码"

        try:
            msg = MIMEMultipart()
            msg["From"] = formataddr(("", self.sender))
            msg["To"] = to
            msg["Subject"] = subject

            if cc:
                msg["Cc"] = cc
            if bcc:
                msg["Bcc"] = bcc

            msg.attach(MIMEText(body, "plain", "utf-8"))

            if attachments:
                for att in attachments:
                    name = att.get("name", "attachment")
                    content = att.get("content", b"")
                    main_type = "image" if name.lower().split(".")[-1] in ("jpg", "jpeg", "png", "gif", "bmp", "webp") else "application"
                    try:
                        if main_type == "image":
                            img = MIMEImage(content, _subtype=name.split(".")[-1])
                            img.add_header("Content-Disposition", "attachment", filename=name)
                            msg.attach(img)
                        else:
                            part = MIMEBase("application", "octet-stream")
                            part.set_payload(content)
                            encoders.encode_base64(part)
                            part.add_header("Content-Disposition", "attachment", filename=name)
                            msg.attach(part)
                    except Exception as e:
                        logger.warning(f"附件 {name} 添加失败: {e}")

            all_recipients = [addr.strip() for addr in to.split(",") if addr.strip()]
            if cc:
                all_recipients += [addr.strip() for addr in cc.split(",") if addr.strip()]
            if bcc:
                all_recipients += [addr.strip() for addr in bcc.split(",") if addr.strip()]

            with smtplib.SMTP_SSL(self.host, self.port) as server:
                server.login(self.sender, self.auth)
                server.sendmail(self.sender, all_recipients, msg.as_string())

            att_count = len(attachments) if attachments else 0
            logger.info(f"邮件已发送: {to}" + (f", 抄送: {cc}" if cc else "") + (f", 密送: {bcc}" if bcc else "") + (f", 附件: {att_count}个" if att_count else ""))
            return f"✅ 邮件已发送: {to}"
        except smtplib.SMTPServerDisconnected:
            return "❌ 发送失败：连接被服务器关闭，请稍后重试"
        except smtplib.SMTPAuthenticationError:
            return "❌ 发送失败：授权码错误，请去 QQ 邮箱重新生成授权码"
        except smtplib.SMTPConnectError:
            return "❌ 发送失败：无法连接 QQ 邮箱，请检查网络或关闭代理"
        except smtplib.SMTPException as e:
            return f"❌ 发送失败：{e}"
        except Exception as e:
            return f"❌ 发送失败：{e}"
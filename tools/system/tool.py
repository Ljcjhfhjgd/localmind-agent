"""
文件名: tools/system/tool.py
功能: 系统工具集 - 时间、记忆、邮件
依赖: tools.base
"""
import json
import uuid
from pathlib import Path
from datetime import datetime
from loguru import logger
from ..base import BaseTool
from .email import EmailSender


class GetTimeTool(BaseTool):
    name = "get_current_time"
    description = "获取当前日期和时间"
    priority = 53
    parameters = {"type": "object", "properties": {}}

    async def execute(self, message: str, ctx: dict = None) -> dict:
        now = datetime.now()
        w = ['一', '二', '三', '四', '五', '六', '日'][now.weekday()]
        return {"result": f"当前时间: {now.strftime('%Y年%m月%d日 %H:%M:%S')} 星期{w}"}


class RememberTool(BaseTool):
    name = "remember"
    description = "当用户告诉你个人信息、偏好、计划、事实等值得记住的内容时调用。只需要传 content 参数"
    priority = 54
    parameters = {
        "type": "object",
        "properties": {
            "content": {"type": "string", "description": "要记住的内容，用自然语言描述"}
        },
        "required": ["content"]
    }

    def __init__(self, config: dict = None):
        super().__init__(config)
        memory_path = config.get("data", {}).get("personal_memory", "data/personal_memory.json") if config else "data/personal_memory.json"
        self.memory_file = Path(memory_path)
        self._agent = None

    def on_mount(self, agent):
        self._agent = agent
        logger.info("RememberTool 已挂载 agent")

    async def execute(self, message: str, ctx: dict = None) -> dict:
        content = (ctx.get("content", "") if ctx else "").strip()
        if not content:
            return {"result": "没有可记忆的内容"}

        summary = content
        if self._agent:
            try:
                prompt_template = self._agent.prompts.get("memory_summary")
                if prompt_template:
                    prompt = prompt_template.format(content=content)
                    resp = await self._agent.llm.chat(
                        messages=[{"role": "user", "content": prompt}],
                        model="qwen2.5:3b-instruct",
                        temperature=0.1,
                    )
                    s = resp.get("message", {}).get("content", "").strip()
                    if s:
                        summary = s
                        logger.info(f"LLM 总结结果: {summary}")
            except Exception as e:
                logger.error(f"LLM 总结失败: {e}")

        try:
            memories = json.loads(self.memory_file.read_text(encoding='utf-8')) if self.memory_file.exists() else []
        except:
            memories = []

        memories.append({
            "id": str(uuid.uuid4())[:8],
            "content": summary,
            "original": content,
            "time": datetime.now().strftime("%Y-%m-%d %H:%M")
        })

        self.memory_file.parent.mkdir(parents=True, exist_ok=True)
        self.memory_file.write_text(json.dumps(memories, ensure_ascii=False, indent=2), encoding='utf-8')
        logger.info(f"记忆已存储: {summary}")
        return {"result": f"已记住: {summary}"}


class RecallTool(BaseTool):
    name = "recall"
    description = "回忆之前记住的关于用户的个人信息。可以不传 query 获取全部记忆，也可以传 query 关键词搜索特定内容"
    priority = 55
    parameters = {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "搜索关键词，留空则返回全部记忆"}
        },
        "required": []
    }

    def __init__(self, config: dict = None):
        super().__init__(config)
        memory_path = config.get("data", {}).get("personal_memory", "data/personal_memory.json") if config else "data/personal_memory.json"
        self.memory_file = Path(memory_path)

    async def execute(self, message: str, ctx: dict = None) -> dict:
        query = (ctx.get("query", "") if ctx else "").strip()
        try:
            memories = json.loads(self.memory_file.read_text(encoding='utf-8')) if self.memory_file.exists() else []
        except:
            return {"result": "暂无记忆"}

        if not memories:
            return {"result": "暂无记忆"}

        if query:
            results = [m["content"] for m in memories if query.lower() in m.get("content", "").lower()]
        else:
            results = [m["content"] for m in memories]

        if results:
            return {"result": "用户记忆:\n" + "\n".join(f"- {r}" for r in results)}
        return {"result": f"没有关于 '{query}' 的记忆"}


class SendEmailTool(BaseTool):
    name = "send_email"
    description = "发送邮件"
    priority = 56
    parameters = {
        "type": "object",
        "properties": {
            "to_email": {"type": "string"},
            "subject": {"type": "string"},
            "body": {"type": "string"},
            "cc": {"type": "string"},
            "bcc": {"type": "string"}
        },
        "required": ["to_email"]
    }

    def __init__(self, config: dict = None):
        super().__init__(config)
        email_cfg = config.get("email", {}) if config else {}
        self.sender = EmailSender(email_cfg)

    async def execute(self, message: str, ctx: dict = None) -> dict:
        to_email = ctx.get("to_email", "") if ctx else ""
        subject = ctx.get("subject", "") if ctx else ""
        body = ctx.get("body", "") if ctx else ""
        cc = ctx.get("cc", "") if ctx else ""
        bcc = ctx.get("bcc", "") if ctx else ""
        attachments = ctx.get("attachments", []) if ctx else []
        result = self.sender.send(to_email, subject, body, cc, bcc, attachments)
        return {"result": result}
"""
文件名: agent/conversation.py
功能: 对话管理器 - 创建/切换/历史/记忆（按模式隔离存储）+ 角色支持
"""
import json
import uuid
import time
from pathlib import Path
from datetime import datetime
from typing import Optional
from loguru import logger


class Conversation:
    """对话管理器 - 按模式隔离存储"""

    def __init__(self, storage_dir: str = "data/conversations"):
        self.base_storage = Path(storage_dir)
        self.base_storage.mkdir(parents=True, exist_ok=True)
        self.current_id: Optional[str] = None
        self.messages: list = []
        self.last_file_summary: str = ""
        self.last_df = None
        self.knowledge_mode: bool = False
        self.current_mode: str = "normal"
        self.role_prompt: str = ""
        self.role_name: str = ""

    @property
    def storage(self) -> Path:
        mode_dir = self.base_storage / self.current_mode
        mode_dir.mkdir(parents=True, exist_ok=True)
        return mode_dir

    def create(self, mode: str = "normal") -> str:
        self.current_id = str(uuid.uuid4())
        self.messages = []
        self.last_file_summary = ""
        self.last_df = None
        self.current_mode = mode
        self._save()
        self._update_index()
        return self.current_id

    def switch(self, conv_id: str, mode: str = None) -> bool:
        if mode:
            self.current_mode = mode
        data = self._load(conv_id)
        if data is None:
            return False
        self.current_id = conv_id
        self.messages = data.get("messages", [])
        self.last_file_summary = data.get("file_summary", "")
        self.last_df = None
        self.knowledge_mode = data.get("knowledge_mode", False)
        self.current_mode = data.get("mode", self.current_mode)
        return True

    def add_message(self, role: str, content: str, **extra):
        self.messages.append({
            "role": role,
            "content": content,
            "timestamp": datetime.now().isoformat(),
            "mode": self.current_mode,
            **extra,
        })
        if len(self.messages) > 50:
            self.messages = self.messages[-50:]

    def get_recent_messages(self, count: int = 6) -> list:
        return self.messages[-count:]

    def get_history_text(self, count: int = 8, max_len: int = 300) -> str:
        parts = []
        for m in self.messages[-count:]:
            c = str(m.get("content", ""))
            if c.startswith("[工具"):
                continue
            if len(c) > max_len:
                c = c[:max_len] + "..."
            role = "用户" if m["role"] == "user" else "助手"
            parts.append(f"{role}: {c}")
        return "\n".join(parts) if parts else "（新对话）"

    async def save(self):
        if not self.current_id:
            return
        self._save()

    def _save(self):
        if not self.current_id:
            return
        existing = self._load(self.current_id)
        title = existing.get("title", "新对话") if existing else "新对话"
        data = {
            "id": self.current_id,
            "title": title,
            "mode": self.current_mode,
            "created_at": existing.get("created_at", datetime.now().isoformat()) if existing else datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
            "messages": self.messages[-50:],
            "file_summary": self.last_file_summary,
            "knowledge_mode": self.knowledge_mode,
        }
        path = self.storage / f"{self.current_id}.json"
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')

    def _load(self, conv_id: str) -> Optional[dict]:
        path = self.storage / f"{conv_id}.json"
        if path.exists():
            try:
                return json.loads(path.read_text(encoding='utf-8'))
            except:
                pass
        return None

    def _update_index(self):
        index_path = self.storage / "index.json"
        index = []
        if index_path.exists():
            try:
                index = json.loads(index_path.read_text(encoding='utf-8'))
            except:
                pass
        now = datetime.now().isoformat()
        found = False
        for item in index:
            if item["id"] == self.current_id:
                item["updated_at"] = now
                item["mode"] = self.current_mode
                found = True
                break
        if not found:
            index.insert(0, {
                "id": self.current_id,
                "title": "新对话",
                "mode": self.current_mode,
                "updated_at": now,
            })
        index_path.write_text(json.dumps(index, ensure_ascii=False, indent=2), encoding='utf-8')

    def list_all(self) -> list:
        index_path = self.storage / "index.json"
        if index_path.exists():
            try:
                return json.loads(index_path.read_text(encoding='utf-8'))
            except:
                pass
        return []

    def list_by_mode(self, mode: str) -> list:
        mode_dir = self.base_storage / mode
        index_path = mode_dir / "index.json"
        if index_path.exists():
            try:
                convs = json.loads(index_path.read_text(encoding='utf-8'))
                for conv in convs:
                    conv["mode"] = mode
                return convs
            except:
                pass
        return []

    def list_all_modes(self) -> dict:
        result = {}
        for mode_dir in self.base_storage.iterdir():
            if mode_dir.is_dir():
                mode = mode_dir.name
                index_path = mode_dir / "index.json"
                if index_path.exists():
                    try:
                        result[mode] = json.loads(index_path.read_text(encoding='utf-8'))
                    except:
                        result[mode] = []
        return result

    def delete(self, conv_id: str) -> bool:
        found = False
        for mode_dir in self.base_storage.iterdir():
            if not mode_dir.is_dir():
                continue
            conv_path = mode_dir / f"{conv_id}.json"
            if conv_path.exists():
                # 重试最多 3 次，解决 Windows 文件占用问题
                for attempt in range(3):
                    try:
                        conv_path.unlink()
                        found = True
                        break
                    except PermissionError:
                        if attempt < 2:
                            time.sleep(0.05)
                if found:
                    index_path = mode_dir / "index.json"
                    if index_path.exists():
                        try:
                            index = json.loads(index_path.read_text(encoding='utf-8'))
                            index = [i for i in index if i["id"] != conv_id]
                            index_path.write_text(json.dumps(index, ensure_ascii=False, indent=2), encoding='utf-8')
                        except Exception:
                            pass
                break
        if self.current_id == conv_id:
            self.current_id = None
            self.messages = []
            self.last_df = None
        return found

    def clear(self):
        self.messages = []
        self.last_file_summary = ""
        self.last_df = None
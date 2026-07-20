"""
文件名: server/routes/memory.py
功能: 记忆管理路由 - 列表、删除、清空、设置
依赖: fastapi
"""
import json
from pathlib import Path

from fastapi import APIRouter, Form

router = APIRouter(prefix="/memory", tags=["记忆"])

MEMORY_FILE = Path("data/personal_memory.json")
SETTINGS_FILE = Path("data/memory_settings.json")


def _load_memories() -> list:
    """加载记忆列表"""
    if MEMORY_FILE.exists():
        try:
            return json.loads(MEMORY_FILE.read_text(encoding='utf-8'))
        except:
            pass
    return []


def _save_memories(memories: list):
    """保存记忆列表"""
    MEMORY_FILE.parent.mkdir(parents=True, exist_ok=True)
    MEMORY_FILE.write_text(json.dumps(memories, ensure_ascii=False, indent=2), encoding='utf-8')


@router.get("/list")
def list_memories():
    """获取所有记忆"""
    memories = _load_memories()
    return {"memories": memories, "total": len(memories)}


@router.delete("/{memory_id}")
def delete_memory(memory_id: str):
    """删除单条记忆"""
    memories = _load_memories()
    before = len(memories)
    memories = [m for m in memories if m["id"] != memory_id]
    if len(memories) < before:
        _save_memories(memories)
        return {"status": "deleted"}
    return {"status": "not_found"}


@router.delete("")
def clear_all_memories():
    """清空所有记忆"""
    MEMORY_FILE.write_text("[]", encoding='utf-8')
    return {"status": "cleared"}


@router.get("/settings")
def get_memory_settings():
    """获取记忆功能设置"""
    if SETTINGS_FILE.exists():
        try:
            return json.loads(SETTINGS_FILE.read_text(encoding='utf-8'))
        except:
            pass
    return {"enabled": True}


@router.post("/settings")
def save_memory_settings(enabled: str = Form("true")):
    """保存记忆功能设置"""
    SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
    settings = {"enabled": enabled.lower() == "true"}
    SETTINGS_FILE.write_text(json.dumps(settings, ensure_ascii=False, indent=2), encoding='utf-8')
    return settings
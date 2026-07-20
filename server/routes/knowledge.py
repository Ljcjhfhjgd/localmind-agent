"""
文件名: server/routes/knowledge.py
功能: 知识库相关路由 - 上传、查询、管理、预览、删除
依赖: fastapi, tools.rag.engine
"""
import uuid
from pathlib import Path

from fastapi import APIRouter, Form, UploadFile, File
from loguru import logger

router = APIRouter(prefix="/rag", tags=["知识库"])

# 全局 RAG 引擎
_rag_engine = None


def get_rag_engine():
    """获取或创建 RAG 引擎"""
    global _rag_engine
    if _rag_engine is None:
        import yaml
        with open("config.yaml", 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
        from tools.rag.engine import RAGEngine
        _rag_engine = RAGEngine(config=config)
    return _rag_engine


@router.post("/upload")
async def upload_document(
    file: UploadFile = File(...),
    rename: str = Form(None),
):
    """上传文档到知识库"""
    temp_dir = Path("data/uploads")
    temp_dir.mkdir(parents=True, exist_ok=True)

    safe_name = f"{uuid.uuid4().hex[:8]}_{file.filename}"
    temp_path = temp_dir / safe_name
    temp_path.write_bytes(await file.read())

    try:
        rag = get_rag_engine()
        doc_name = rename if rename else file.filename
        result = await rag.index_document(str(temp_path), doc_name)
        return result
    except Exception as e:
        return {"success": False, "error": str(e)}


@router.post("/query")
async def query_knowledge(
    query: str = Form(...),
    doc_name: str = Form(None),
):
    """查询知识库"""
    try:
        rag = get_rag_engine()
        context = await rag.get_context(query, top_k=5)
        return {"success": True, "context": context}
    except Exception as e:
        return {"success": False, "error": str(e)}


@router.get("/collections")
def list_collections():
    """列出所有知识库文档"""
    rag = get_rag_engine()
    return {"collections": rag.list_collections()}


@router.get("/collections/{name}")
async def get_collection(name: str):
    """获取文档原始内容"""
    import json
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
                        if ext in ('.txt', '.md', '.py', '.js', '.json', '.csv', '.yaml', '.yml', '.html', '.css', '.xml'):
                            try:
                                content = original.read_text(encoding='utf-8')
                            except:
                                try:
                                    content = original.read_text(encoding='gbk')
                                except:
                                    content = "无法读取文件内容"
                            return {"content": content, "name": name}
                    chunks = meta.get("chunks", [])
                    content = "\n\n".join(c.get("content", "") for c in chunks)
                    return {"content": content, "name": name}
            except Exception as e:
                logger.error(f"读取metadata失败: {e}")
    return {"content": "文件不存在", "name": name}


@router.delete("/collections/{doc_name}")
def delete_collection(doc_name: str):
    """删除知识库文档"""
    from urllib.parse import unquote
    doc_name = unquote(doc_name)
    rag = get_rag_engine()
    rag.delete_collection(doc_name)
    return {"status": "deleted"}


@router.get("/stats")
def rag_stats():
    """获取 RAG 检索质量统计"""
    rag = get_rag_engine()
    return rag.evaluator.get_stats()
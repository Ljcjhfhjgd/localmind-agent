"""
文件名: server/routes/files.py
功能: 文件相关路由 - 上传、下载、列表、图片访问
依赖: fastapi
"""
from pathlib import Path
from datetime import datetime

from fastapi import APIRouter, UploadFile, File
from fastapi.responses import FileResponse

router = APIRouter(prefix="/files", tags=["文件"])


@router.get("/uploads/{filename}")
def serve_upload(filename: str):
    """访问上传的图片"""
    filepath = Path("data/uploads") / filename
    if filepath.exists():
        return FileResponse(str(filepath))
    return {"error": "文件不存在"}


@router.get("/download/{filename}")
def download_file(filename: str):
    """下载 output/ 目录下的文件"""
    filepath = Path("output") / filename
    if filepath.exists():
        return FileResponse(str(filepath), filename=filename)
    return {"error": "文件不存在"}


@router.get("/list")
def list_output_files():
    """列出 output/ 目录下所有文件"""
    output_dir = Path("output")
    output_dir.mkdir(exist_ok=True)

    files = []
    for f in output_dir.iterdir():
        if f.is_file():
            stat = f.stat()
            size_kb = stat.st_size / 1024
            size_str = f"{size_kb:.1f} KB" if size_kb < 1024 else f"{size_kb/1024:.1f} MB"
            files.append({
                "name": f.name,
                "size": size_str,
                "modified": datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M"),
            })

    files.sort(key=lambda x: x["modified"], reverse=True)
    return {"files": files}


@router.get("/preview/{filename}")
def preview_file(filename: str):
    """预览文件内容（仅文本）"""
    filepath = Path("output") / filename
    if not filepath.exists():
        return {"error": "文件不存在"}
    try:
        content = filepath.read_text(encoding='utf-8')
        return {"filename": filename, "content": content[:5000]}
    except:
        return {"error": "无法预览，可能是二进制文件"}


@router.delete("/delete/{filename}")
def delete_output_file(filename: str):
    """删除 output/ 目录下的文件"""
    filepath = Path("output") / filename
    if filepath.exists():
        filepath.unlink()
        return {"status": "deleted"}
    return {"error": "文件不存在"}


@router.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    """上传文件到 output/ 目录"""
    output_dir = Path("output")
    output_dir.mkdir(exist_ok=True)

    filepath = output_dir / file.filename
    content = await file.read()
    filepath.write_bytes(content)

    return {
        "status": "uploaded",
        "filename": file.filename,
        "size": len(content),
    }
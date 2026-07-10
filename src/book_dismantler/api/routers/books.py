"""书籍上传与管理路由。"""

from __future__ import annotations

import shutil
import uuid
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, UploadFile

from book_dismantler.api.deps import get_upload_dir
from book_dismantler.api.schemas import BookUploadResponse
from book_dismantler.parsing.registry import detect_format

router = APIRouter()

# 允许的文件类型
ALLOWED_EXTENSIONS = {".pdf", ".epub"}
MAX_FILE_SIZE = 100 * 1024 * 1024  # 100MB


def _get_sample_books_dir() -> Path:
    """获取内置示例书籍目录。

    查找顺序：项目根目录的 sample_books / 包内 sample_books。
    """
    # books.py -> routers -> api -> book_dismantler -> src -> project_root
    api_routers = Path(__file__).resolve().parent  # routers/
    api_dir = api_routers.parent                    # api/
    pkg_dir = api_dir.parent                        # book_dismantler/
    src_dir = pkg_dir.parent                        # src/
    project_root = src_dir.parent                   # project root

    for base in [project_root, pkg_dir]:
        candidate = base / "sample_books"
        if candidate.exists() and candidate.is_dir():
            return candidate

    return project_root / "sample_books"


def _ensure_sample_books_loaded() -> None:
    """首次启动时将示例书籍复制到上传目录。

    通过标记文件避免重复复制。
    """
    sample_dir = _get_sample_books_dir()
    if not sample_dir.exists():
        return

    upload_dir = get_upload_dir()
    marker = upload_dir / ".samples_loaded"

    # 如果标记文件存在且示例书籍都在，跳过
    if marker.exists():
        return

    for f in sample_dir.iterdir():
        if f.is_file() and f.suffix.lower() in ALLOWED_EXTENSIONS:
            dest = upload_dir / f.name
            if not dest.exists():
                shutil.copy2(f, dest)

    marker.touch()


@router.get("/samples")
async def list_sample_books() -> dict[str, Any]:
    """列出可用的示例书籍。

    如果示例书籍尚未加载到上传目录，会自动加载。
    """
    _ensure_sample_books_loaded()

    sample_dir = _get_sample_books_dir()
    samples = []
    if sample_dir.exists():
        for f in sorted(sample_dir.iterdir()):
            if f.is_file() and f.suffix.lower() in ALLOWED_EXTENSIONS:
                samples.append({
                    "filename": f.name,
                    "size": f.stat().st_size,
                    "format": detect_format(f.name).value,
                })
    return {"samples": samples}


@router.post("/samples/load")
async def load_sample_books() -> dict[str, Any]:
    """手动触发加载示例书籍到上传目录。"""
    _ensure_sample_books_loaded()
    upload_dir = get_upload_dir()
    sample_dir = _get_sample_books_dir()

    loaded = []
    if sample_dir.exists():
        for f in sorted(sample_dir.iterdir()):
            if f.is_file() and f.suffix.lower() in ALLOWED_EXTENSIONS:
                dest = upload_dir / f.name
                if not dest.exists():
                    shutil.copy2(f, dest)
                    loaded.append(f.name)

    return {
        "message": f"已加载 {len(loaded)} 本示例书籍",
        "loaded": loaded,
    }


@router.post("/upload", response_model=BookUploadResponse)
async def upload_book(file: UploadFile) -> BookUploadResponse:
    """上传电子书文件。"""
    if not file.filename:
        raise HTTPException(status_code=400, detail="文件名为空")

    ext = Path(file.filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"不支持的文件格式 '{ext}'，支持: {', '.join(ALLOWED_EXTENSIONS)}",
        )

    # 流式读取，边读边检查大小，避免大文件占满内存
    chunk_size = 1024 * 1024  # 1MB
    chunks: list[bytes] = []
    total_size = 0
    while True:
        chunk = await file.read(chunk_size)
        if not chunk:
            break
        total_size += len(chunk)
        if total_size > MAX_FILE_SIZE:
            raise HTTPException(status_code=413, detail="文件过大（最大 100MB）")
        chunks.append(chunk)
    content = b"".join(chunks)

    book_id = uuid.uuid4().hex[:12]
    upload_dir = get_upload_dir()
    file_path = upload_dir / f"{book_id}{ext}"
    file_path.write_bytes(content)

    return BookUploadResponse(
        book_id=book_id,
        filename=file.filename,
        size=total_size,
    )


@router.get("/list")
async def list_books() -> dict[str, Any]:
    """列出已上传的书籍。

    自动加载示例书籍（首次调用时）。
    """
    _ensure_sample_books_loaded()

    upload_dir = get_upload_dir()
    books = []
    for f in upload_dir.iterdir():
        if f.is_file() and f.suffix.lower() in ALLOWED_EXTENSIONS:
            books.append({
                "book_id": f.stem,
                "filename": f.name,
                "size": f.stat().st_size,
                "format": detect_format(f.name).value,
            })
    return {"books": books}


@router.get("/{book_id}/info")
async def book_info(book_id: str) -> dict[str, Any]:
    """获取书籍信息。

    book_id 可以是 hex ID 或文件名（不含扩展名）。
    """
    upload_dir = get_upload_dir()

    # 先按 hex_id 格式查找
    for ext in ALLOWED_EXTENSIONS:
        path = upload_dir / f"{book_id}{ext}"
        if path.exists():
            return {
                "book_id": book_id,
                "filename": path.name,
                "size": path.stat().st_size,
                "format": detect_format(path.name).value,
                "path": str(path),
            }

    # 再按文件名查找（支持中文文件名）
    for f in upload_dir.iterdir():
        if f.is_file() and f.stem == book_id and f.suffix.lower() in ALLOWED_EXTENSIONS:
            return {
                "book_id": book_id,
                "filename": f.name,
                "size": f.stat().st_size,
                "format": detect_format(f.name).value,
                "path": str(f),
            }

    raise HTTPException(status_code=404, detail="书籍不存在")


@router.delete("/{book_id}")
async def delete_book(book_id: str) -> dict[str, Any]:
    """删除已上传的书籍。"""
    upload_dir = get_upload_dir()

    # 先按 hex_id 格式查找
    for ext in ALLOWED_EXTENSIONS:
        path = upload_dir / f"{book_id}{ext}"
        if path.exists():
            path.unlink()
            return {"message": "已删除", "book_id": book_id}

    # 再按文件名查找
    for f in upload_dir.iterdir():
        if f.is_file() and f.stem == book_id and f.suffix.lower() in ALLOWED_EXTENSIONS:
            f.unlink()
            return {"message": "已删除", "book_id": book_id}

    raise HTTPException(status_code=404, detail="书籍不存在")

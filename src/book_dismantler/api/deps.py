"""API 依赖注入。"""

from __future__ import annotations

from pathlib import Path

from book_dismantler.core.config import Settings, get_settings


def get_app_settings() -> Settings:
    """获取应用配置。"""
    return get_settings()


def get_upload_dir(settings: Settings | None = None) -> Path:
    """获取上传文件目录。"""
    settings = settings or get_settings()
    upload_dir = settings.output_dir / "uploads"
    upload_dir.mkdir(parents=True, exist_ok=True)
    return upload_dir


def get_output_base_dir(settings: Settings | None = None) -> Path:
    """获取产物输出基目录。"""
    settings = settings or get_settings()
    return settings.output_dir

"""任务状态机：管理拆书任务的生命周期。

支持进度跟踪、取消请求、持久化到磁盘。
所有公共方法均线程安全。
"""

from __future__ import annotations

import contextlib
import hashlib
import json
import os
import threading
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field, PrivateAttr

from book_dismantler.core.logging import get_logger

logger = get_logger("application.jobs")


class JobStatus(str, Enum):
    """任务状态。"""

    PENDING = "pending"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"
    CANCELLED = "cancelled"


class JobResult(BaseModel):
    """任务执行结果。

    所有状态变更方法均线程安全。
    """

    job_id: str = Field(..., description="任务 ID")
    status: JobStatus = Field(default=JobStatus.PENDING)
    book_title: str = Field(default="")
    book_filename: str = Field(default="")
    provider: str = Field(default="")
    model: str = Field(default="")
    started_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    finished_at: datetime | None = None
    output_dir: str = Field(default="")
    artifact_paths: list[str] = Field(default_factory=list)
    error: str = Field(default="")
    stats: dict[str, Any] = Field(default_factory=dict)

    # 进度跟踪
    progress: int = Field(default=0, description="进度 0-100")
    current_step: str = Field(default="", description="当前步骤描述")

    # 取消控制
    cancel_requested: bool = Field(default=False)

    # 线程安全锁（不序列化）
    _lock: threading.Lock = PrivateAttr(default_factory=threading.Lock)

    @property
    def duration_seconds(self) -> float | None:
        """执行时长（秒）。"""
        if self.finished_at is None:
            return None
        return (self.finished_at - self.started_at).total_seconds()

    @property
    def is_success(self) -> bool:
        return self.status == JobStatus.DONE

    @property
    def is_cancelled(self) -> bool:
        return self.cancel_requested or self.status == JobStatus.CANCELLED

    def mark_running(self) -> None:
        with self._lock:
            self.status = JobStatus.RUNNING
            self.progress = 5
            self.current_step = "初始化中..."

    def update_progress(self, progress: int, step: str = "") -> None:
        """更新进度（线程安全）。"""
        with self._lock:
            self.progress = max(0, min(100, progress))
            if step:
                self.current_step = step

    def mark_done(self, output_dir: str | Path, artifacts: list[str]) -> None:
        with self._lock:
            self.status = JobStatus.DONE
            self.finished_at = datetime.now(timezone.utc)
            self.output_dir = str(output_dir)
            self.artifact_paths = artifacts
            self.progress = 100
            self.current_step = "完成"

    def mark_failed(self, error: str) -> None:
        with self._lock:
            self.status = JobStatus.FAILED
            self.finished_at = datetime.now(timezone.utc)
            self.error = error
            self.current_step = f"失败: {error[:50]}"

    def mark_cancelled(self) -> None:
        with self._lock:
            self.status = JobStatus.CANCELLED
            self.finished_at = datetime.now(timezone.utc)
            self.current_step = "已取消"

    def request_cancel(self) -> None:
        """请求取消（实际取消由执行器检查）。"""
        with self._lock:
            self.cancel_requested = True

    def snapshot(self) -> JobResult:
        """返回当前状态的线程安全副本。

        使用 model_dump + model_validate 重建实例，避免 model_copy(deep=True)
        尝试深拷贝 _lock（threading.Lock 不可 pickle）。
        """
        with self._lock:
            return JobResult.model_validate(self.model_dump(mode="python"))


class JobStore:
    """任务存储：内存 + JSON 文件持久化。所有方法均线程安全。"""

    def __init__(self, persist_path: Path | None = None) -> None:
        self._jobs: dict[str, JobResult] = {}
        self._persist_path = persist_path
        self._lock = threading.RLock()

    def add(self, job: JobResult) -> None:
        with self._lock:
            self._jobs[job.job_id] = job
            self._save()

    def get(self, job_id: str) -> JobResult | None:
        with self._lock:
            return self._jobs.get(job_id)

    def remove(self, job_id: str) -> bool:
        with self._lock:
            if job_id in self._jobs:
                del self._jobs[job_id]
                self._save()
                return True
            return False

    def list_all(self) -> list[JobResult]:
        with self._lock:
            return sorted(
                self._jobs.values(),
                key=lambda j: j.started_at,
                reverse=True,
            )

    def save(self) -> None:
        with self._lock:
            self._save()

    def clear(self) -> None:
        """清空所有任务（主要用于测试）。"""
        with self._lock:
            self._jobs.clear()

    def _save(self) -> None:
        """将任务列表持久化到磁盘（调用方需持有锁）。"""
        if self._persist_path is None:
            return
        try:
            data = {
                "jobs": [j.model_dump(mode="json") for j in self._jobs.values()]
            }
            self._persist_path.write_text(
                json.dumps(data, ensure_ascii=False, indent=2, default=str),
                encoding="utf-8",
            )
        except Exception as e:
            logger.warning("任务持久化失败: %s", e, exc_info=True)

    def load(self) -> None:
        with self._lock:
            if self._persist_path is None or not self._persist_path.exists():
                return
            try:
                data = json.loads(self._persist_path.read_text(encoding="utf-8"))
                for job_data in data.get("jobs", []):
                    job = JobResult.model_validate(job_data)
                    # 重置运行中任务为失败（服务重启）
                    if job.status == JobStatus.RUNNING:
                        job.status = JobStatus.FAILED
                        job.error = "服务重启，任务中断"
                        job.current_step = "中断"
                    self._jobs[job.job_id] = job
            except Exception as e:
                logger.warning("任务持久化文件加载失败: %s", e, exc_info=True)

    def reconcile(self, output_base_dir: Path) -> int:
        """扫描输出目录，自动发现未注册的已完成任务。

        遍历 output_base_dir 下的子目录，查找包含 manifest.json 的目录。
        如果该目录未被任何已注册任务的 output_dir 引用，则根据 manifest
        创建合成任务记录并注册。确保磁盘上的已完成工作永远不会丢失。

        Returns:
            新发现的任务数量。
        """
        with self._lock:
            # 构建已注册的 output_dir 集合（归一化路径）
            known_dirs: set[str] = set()
            for job in self._jobs.values():
                if job.output_dir:
                    with contextlib.suppress(Exception):
                        known_dirs.add(str(Path(job.output_dir).resolve()))

            discovered = 0
            if not output_base_dir.exists():
                return 0

            for d in output_base_dir.iterdir():
                if not d.is_dir():
                    continue
                # 跳过 uploads 子目录
                if d.name == "uploads":
                    continue
                manifest_path = d / "manifest.json"
                if not manifest_path.exists():
                    continue

                try:
                    dir_resolved = str(d.resolve())
                except Exception:
                    continue
                if dir_resolved in known_dirs:
                    continue  # 已注册

                try:
                    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
                except Exception:
                    logger.warning("跳过无法解析的 manifest: %s", manifest_path)
                    continue

                # 生成稳定的 job_id（基于目录名的短哈希）
                job_id = hashlib.sha256(d.name.encode("utf-8")).hexdigest()[:12]

                # 如果该 job_id 已存在，跳过
                if job_id in self._jobs:
                    continue

                # 从 manifest 提取统计信息
                stats_raw = manifest.get("stats", {})
                artifacts = manifest.get("artifacts", [])

                # 从目录修改时间推断时间戳
                try:
                    mtime = os.path.getmtime(d)
                    started_at = datetime.fromtimestamp(mtime, tz=timezone.utc)
                    finished_at = started_at
                except Exception:
                    started_at = datetime.now(timezone.utc)
                    finished_at = started_at

                job = JobResult(
                    job_id=job_id,
                    status=JobStatus.DONE,
                    book_title=manifest.get("book_title", d.name),
                    book_filename=d.name,
                    provider="reconciled",
                    model="reconciled",
                    started_at=started_at,
                    finished_at=finished_at,
                    output_dir=str(d.resolve()),
                    artifact_paths=[a.get("type", "") for a in artifacts],
                    error="",
                    stats={
                        "concept_count": stats_raw.get("concepts", 0),
                        "relationship_count": stats_raw.get("relationships", 0),
                        "artifact_count": manifest.get("artifact_count", len(artifacts)),
                    },
                    progress=100,
                    current_step="完成",
                    cancel_requested=False,
                )

                self._jobs[job_id] = job
                discovered += 1
                logger.info("自动发现任务: %s -> %s", d.name, job_id)

            if discovered > 0:
                self._save()

            return discovered

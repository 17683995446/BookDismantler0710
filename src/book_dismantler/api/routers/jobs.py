"""拆书任务路由：创建/查询/取消/删除，支持进度跟踪与持久化。"""

from __future__ import annotations

import threading
import uuid
from pathlib import Path
from typing import Any

from fastapi import APIRouter, BackgroundTasks, HTTPException

from book_dismantler.api.deps import get_output_base_dir, get_upload_dir
from book_dismantler.api.schemas import JobCreateRequest, JobStatusResponse
from book_dismantler.application.jobs import JobResult, JobStatus, JobStore
from book_dismantler.application.runner import DismantleRunner
from book_dismantler.core.config import get_settings
from book_dismantler.core.exceptions import BookDismantlerError, JobCancelledError
from book_dismantler.core.logging import get_logger

router = APIRouter()
logger = get_logger("api.jobs")

# 全局任务存储（持久化到磁盘）
_store: JobStore | None = None
_store_lock = threading.Lock()


def get_job_store() -> JobStore:
    """获取全局任务存储（懒初始化 + 持久化）。"""
    global _store
    if _store is None:
        with _store_lock:
            if _store is None:
                output_dir = get_output_base_dir()
                persist_path = output_dir / ".jobs.json"
                store = JobStore(persist_path=persist_path)
                store.load()
                # 自动发现未注册的已完成任务（确保磁盘上的工作不会因持久化文件丢失而消失）
                discovered = store.reconcile(output_dir)
                if discovered:
                    logger.info("自动发现 %d 个未注册的已完成任务", discovered)
                _store = store
    return _store


# 兼容旧代码：通过函数访问任务存储
def _get_jobs_dict() -> dict[str, Any]:
    """获取任务字典（兼容旧接口）。"""
    return {j.job_id: j for j in get_job_store().list_all()}


@router.post("/create", response_model=JobStatusResponse)
async def create_job(
    request: JobCreateRequest,
    background_tasks: BackgroundTasks,
) -> JobStatusResponse:
    """创建拆书任务。"""
    # 查找书籍文件
    upload_dir = get_upload_dir()
    book_path: Path | None = None

    for ext in (".pdf", ".epub"):
        candidate = upload_dir / f"{request.book_id}{ext}"
        if candidate.exists():
            book_path = candidate
            break

    if book_path is None:
        for f in upload_dir.iterdir():
            if f.is_file() and f.stem == request.book_id and f.suffix.lower() in {".pdf", ".epub"}:
                book_path = f
                break

    if book_path is None:
        raise HTTPException(status_code=404, detail="书籍不存在")

    job_id = uuid.uuid4().hex[:12]
    settings = get_settings()
    provider = request.provider or settings.default_provider
    model = request.model or settings.default_model

    job = JobResult(
        job_id=job_id,
        book_title=book_path.stem,
        book_filename=book_path.name,
        provider=provider,
        model=model,
    )

    store = get_job_store()
    store.add(job)

    background_tasks.add_task(_run_job, job_id, book_path, provider, model)

    return _to_response(job)


@router.get("/{job_id}", response_model=JobStatusResponse)
async def get_job_status(job_id: str) -> JobStatusResponse:
    """查询任务状态（含实时进度）。"""
    job = get_job_store().get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="任务不存在")
    return _to_response(job)


@router.get("/")
async def list_jobs() -> dict[str, Any]:
    """列出所有任务（按时间倒序）。"""
    store = get_job_store()
    return {
        "jobs": [_to_response(job).model_dump(mode="json") for job in store.list_all()]
    }


@router.post("/{job_id}/cancel")
async def cancel_job(job_id: str) -> dict[str, Any]:
    """请求取消任务。"""
    job = get_job_store().get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="任务不存在")

    if job.status not in (JobStatus.PENDING, JobStatus.RUNNING):
        raise HTTPException(status_code=400, detail=f"任务状态为 {job.status}，无法取消")

    job.request_cancel()
    get_job_store().save()
    return {"message": "取消请求已发送", "job_id": job_id}


@router.delete("/{job_id}")
async def delete_job(job_id: str) -> dict[str, Any]:
    """删除任务记录。"""
    if not get_job_store().remove(job_id):
        raise HTTPException(status_code=404, detail="任务不存在")
    return {"message": "已删除", "job_id": job_id}


def _to_response(job: JobResult) -> JobStatusResponse:
    """转换为 API 响应。"""
    return JobStatusResponse(
        job_id=job.job_id,
        status=job.status.value,
        book_title=job.book_title,
        book_filename=job.book_filename,
        provider=job.provider,
        model=job.model,
        output_dir=job.output_dir,
        artifact_count=len(job.artifact_paths),
        error=job.error,
        progress=job.progress,
        current_step=job.current_step,
        started_at=job.started_at,
        finished_at=job.finished_at,
        duration_seconds=job.duration_seconds,
        stats=job.stats,
    )


def _run_job(
    job_id: str,
    book_path: Path,
    provider: str | None,
    model: str | None,
) -> None:
    """后台执行拆书任务。"""
    store = get_job_store()
    job = store.get(job_id)
    if job is None:
        return

    job.mark_running()
    store.save()

    try:
        settings = get_settings()
        if provider:
            settings.default_provider = provider
        if model:
            settings.default_model = model

        runner = DismantleRunner(settings=settings)

        def on_progress(progress: int, step: str = "") -> None:
            job.update_progress(progress, step)
            store.save()

        def cancel_check() -> bool:
            return job.cancel_requested

        result = runner.run(
            book_path,
            output_dir=get_output_base_dir(settings),
            on_progress=on_progress,
            cancel_check=cancel_check,
        )

        if job.cancel_requested:
            job.mark_cancelled()
        else:
            job.mark_done(
                output_dir=result.output_dir,
                artifacts=[a.artifact_type.value for a in result.artifacts],
            )
            job.book_title = result.book_title
            km = result.knowledge_model
            job.stats = {
                "concept_count": km.concept_count if km else 0,
                "relationship_count": km.relationship_count if km else 0,
                "artifact_count": len(result.artifacts),
            }
        store.save()
        logger.info("任务 %s 完成: %s", job_id, job.status.value)

    except JobCancelledError:
        job.mark_cancelled()
        store.save()

    except BookDismantlerError as e:
        logger.error("任务 %s 失败: %s", job_id, e)
        job.mark_failed(str(e))
        store.save()

    except Exception as e:
        logger.error("任务 %s 异常: %s", job_id, e, exc_info=True)
        job.mark_failed(str(e))
        store.save()

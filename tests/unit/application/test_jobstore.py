"""JobStore 持久化与并发安全测试。

测试范围：save/load 往返、重启恢复（RUNNING→FAILED）、多线程并发安全。
"""

from __future__ import annotations

import threading
from pathlib import Path

import pytest

from book_dismantler.application.jobs import JobResult, JobStatus, JobStore


@pytest.fixture()
def store(tmp_path: Path) -> JobStore:
    """创建带临时持久化路径的 JobStore。"""
    persist = tmp_path / ".jobs.json"
    return JobStore(persist_path=persist)


def _make_job(job_id: str = "job-1", status: JobStatus = JobStatus.DONE) -> JobResult:
    """创建测试用 JobResult。"""
    return JobResult(
        job_id=job_id,
        status=status,
        book_title="测试书",
        book_filename="test.pdf",
        provider="openai",
        model="gpt-4",
        progress=100 if status == JobStatus.DONE else 50,
    )


class TestJobStorePersistence:
    """持久化 save/load 测试。"""

    def test_save_and_load_roundtrip(self, store: JobStore) -> None:
        """保存后重新加载，数据应一致。"""
        job = _make_job("job-persist-1", JobStatus.DONE)
        store.add(job)

        # 新建 store 从同一文件加载
        store2 = JobStore(persist_path=store._persist_path)
        store2.load()

        loaded = store2.get("job-persist-1")
        assert loaded is not None
        assert loaded.job_id == "job-persist-1"
        assert loaded.status == JobStatus.DONE
        assert loaded.book_title == "测试书"

    def test_load_nonexistent_file(self, tmp_path: Path) -> None:
        """加载不存在的文件不应抛异常。"""
        store = JobStore(persist_path=tmp_path / "nonexistent.json")
        store.load()
        assert store.list_all() == []

    def test_load_corrupted_file(self, tmp_path: Path) -> None:
        """加载损坏的 JSON 文件不应抛异常，但应有日志。"""
        corrupt = tmp_path / ".jobs.json"
        corrupt.write_text("{ invalid json !!!", encoding="utf-8")

        store = JobStore(persist_path=corrupt)
        store.load()
        assert store.list_all() == []

    def test_running_job_reset_to_failed_on_load(self, store: JobStore) -> None:
        """重启后 RUNNING 任务应重置为 FAILED。"""
        job = _make_job("job-running-1", JobStatus.RUNNING)
        store.add(job)

        # 模拟重启：新 store 从文件加载
        store2 = JobStore(persist_path=store._persist_path)
        store2.load()

        loaded = store2.get("job-running-1")
        assert loaded is not None
        assert loaded.status == JobStatus.FAILED
        assert "服务重启" in loaded.error

    def test_remove_persists(self, store: JobStore) -> None:
        """删除任务后应持久化。"""
        job = _make_job("job-remove-1")
        store.add(job)
        assert store.get("job-remove-1") is not None

        store.remove("job-remove-1")
        assert store.get("job-remove-1") is None

        # 重新加载确认已删除
        store2 = JobStore(persist_path=store._persist_path)
        store2.load()
        assert store2.get("job-remove-1") is None

    def test_no_persist_path(self) -> None:
        """无持久化路径时不应抛异常。"""
        store = JobStore(persist_path=None)
        store.add(_make_job("job-nopath"))
        store.save()  # 不应抛异常
        assert store.get("job-nopath") is not None


class TestJobStoreConcurrency:
    """并发安全测试。"""

    def test_concurrent_add_and_list(self, store: JobStore) -> None:
        """多线程同时添加和列表查询不应崩溃。"""
        errors: list[Exception] = []

        def adder(start: int, count: int) -> None:
            try:
                for i in range(start, start + count):
                    store.add(_make_job(f"job-conc-{i}", JobStatus.DONE))
            except Exception as e:
                errors.append(e)

        def lister() -> None:
            try:
                for _ in range(50):
                    store.list_all()
            except Exception as e:
                errors.append(e)

        threads = [
            threading.Thread(target=adder, args=(0, 20)),
            threading.Thread(target=adder, args=(20, 20)),
            threading.Thread(target=lister),
            threading.Thread(target=lister),
        ]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert errors == [], f"并发错误: {errors}"
        assert len(store.list_all()) == 40

    def test_concurrent_update_progress(self, store: JobStore) -> None:
        """多线程同时更新同一任务进度不应崩溃。"""
        job = _make_job("job-concurrent-progress", JobStatus.RUNNING)
        store.add(job)

        errors: list[Exception] = []

        def updater() -> None:
            try:
                for i in range(100):
                    job.update_progress(i, f"step-{i}")
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=updater) for _ in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert errors == [], f"并发错误: {errors}"
        assert 0 <= job.progress <= 100

    def test_snapshot_is_thread_safe(self, store: JobStore) -> None:
        """snapshot() 返回的副本与原对象独立。"""
        job = _make_job("job-snapshot", JobStatus.RUNNING)
        store.add(job)

        snap = job.snapshot()
        job.update_progress(80, "updated")
        job.mark_done("/output", ["artifact.html"])

        # snapshot 应保持旧状态
        assert snap.progress == 50
        assert snap.status == JobStatus.RUNNING
        # 原对象已更新
        assert job.progress == 100
        assert job.status == JobStatus.DONE


class TestJobResultStateTransitions:
    """JobResult 状态机测试。"""

    def test_full_lifecycle(self) -> None:
        """完整生命周期：pending → running → done。"""
        job = JobResult(job_id="lifecycle-1")
        assert job.status == JobStatus.PENDING
        assert job.progress == 0

        job.mark_running()
        assert job.status == JobStatus.RUNNING
        assert job.progress == 5

        job.update_progress(50, "分析中")
        assert job.progress == 50
        assert job.current_step == "分析中"

        job.update_progress(80, "渲染中")
        assert job.progress == 80

        job.mark_done("/output", ["artifact1.html", "artifact2.html"])
        assert job.status == JobStatus.DONE
        assert job.progress == 100
        assert len(job.artifact_paths) == 2
        assert job.finished_at is not None

    def test_cancel_lifecycle(self) -> None:
        """取消生命周期：pending → running → cancelled。"""
        job = JobResult(job_id="cancel-1")
        job.mark_running()
        assert job.status == JobStatus.RUNNING

        job.request_cancel()
        assert job.cancel_requested is True

        job.mark_cancelled()
        assert job.status == JobStatus.CANCELLED
        assert job.finished_at is not None

    def test_fail_lifecycle(self) -> None:
        """失败生命周期：pending → running → failed。"""
        job = JobResult(job_id="fail-1")
        job.mark_running()
        job.mark_failed("LLM 超时")
        assert job.status == JobStatus.FAILED
        assert "LLM 超时" in job.error
        assert job.finished_at is not None

    def test_progress_clamped(self) -> None:
        """进度值应被钳制在 0-100 范围。"""
        job = JobResult(job_id="clamp-1")
        job.update_progress(-10, "负值")
        assert job.progress == 0
        job.update_progress(150, "超值")
        assert job.progress == 100

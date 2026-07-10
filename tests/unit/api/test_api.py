"""API 层单元测试。

使用 FastAPI TestClient 进行端到端 API 测试。
测试范围：书籍上传/列表/信息/删除、任务创建/查询/列表、产物列表/下载/预览。
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from book_dismantler.api.app import create_app
from book_dismantler.core.logging import setup_logging


@pytest.fixture()
def client(tmp_path: Path):
    """创建带临时输出目录的 TestClient。"""
    # 重置任务存储
    from book_dismantler.api.routers.jobs import get_job_store
    get_job_store().clear()

    # 重置日志单例
    import book_dismantler.core.logging as logging_mod
    logging_mod._CONFIGURED = False

    setup_logging("WARNING")

    # Mock settings to use tmp_path
    with patch("book_dismantler.api.deps.get_settings") as mock_settings, \
         patch("book_dismantler.api.routers.jobs.get_settings") as mock_job_settings, \
         patch("book_dismantler.core.config.get_settings") as mock_core_settings:

        from book_dismantler.core.config import Settings
        settings = Settings(output_dir=tmp_path)
        mock_settings.return_value = settings
        mock_job_settings.return_value = settings
        mock_core_settings.return_value = settings

        app = create_app()
        yield TestClient(app)

    # 清理
    from book_dismantler.api.routers.jobs import get_job_store
    get_job_store().clear()


@pytest.fixture()
def uploaded_book(client: TestClient) -> dict:
    """上传一本测试书籍，返回响应。"""
    # 使用 conftest 中的 PDF 生成逻辑
    import io
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.pdfgen import canvas
        buf = io.BytesIO()
        c = canvas.Canvas(buf, pagesize=A4)
        c.drawString(100, 750, "Test Book Title")
        c.drawString(100, 700, "Chapter 1: Introduction")
        c.drawString(100, 650, "This is a test book for API testing.")
        c.save()
        buf.seek(0)
    except ImportError:
        from fpdf import FPDF
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Helvetica", size=12)
        pdf.cell(0, 10, "Test Book Title", ln=True)
        pdf.cell(0, 10, "Chapter 1: Introduction", ln=True)
        pdf.cell(0, 10, "This is a test book for API testing.", ln=True)
        buf = io.BytesIO(pdf.output())

    response = client.post(
        "/api/books/upload",
        files={"file": ("test_book.pdf", buf, "application/pdf")},
    )
    assert response.status_code == 200
    return response.json()


class TestHealthAndIndex:
    """健康检查与首页测试。"""

    def test_health_check(self, client: TestClient):
        """测试健康检查端点。"""
        response = client.get("/health")
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "ok"
        assert "version" in body

    def test_index_page(self, client: TestClient):
        """测试首页返回 HTML。"""
        response = client.get("/")
        assert response.status_code == 200
        assert "text/html" in response.headers.get("content-type", "")

    def test_api_docs_available(self, client: TestClient):
        """测试 OpenAPI 文档可用。"""
        response = client.get("/docs")
        assert response.status_code == 200

    def test_health_check_includes_disk_and_jobs(self, client: TestClient):
        """健康检查返回磁盘空间和 jobs 统计。"""
        response = client.get("/health")
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "ok"
        assert "version" in body
        assert "disk_free_gb" in body
        assert "jobs_total" in body
        assert "jobs_active" in body

    def test_trace_id_header_echoed(self, client: TestClient):
        """请求 X-Trace-Id 头会回显到响应。"""
        response = client.get("/health", headers={"X-Trace-Id": "test1234"})
        assert response.headers.get("X-Trace-Id") == "test1234"

    def test_trace_id_auto_generated(self, client: TestClient):
        """无 X-Trace-Id 时自动生成 8 字符 ID。"""
        response = client.get("/health")
        tid = response.headers.get("X-Trace-Id")
        assert tid is not None
        assert len(tid) == 8


class TestErrorResponses:
    """统一错误响应格式。"""

    def test_404_returns_json(self, client: TestClient):
        """不存在的端点返回 JSON 错误。"""
        response = client.get("/api/nonexistent-endpoint-12345")
        assert response.status_code == 404

    def test_error_response_domain_exception(self):
        """领域异常序列化为结构化响应。"""
        from book_dismantler.api.app import _error_response
        from book_dismantler.core.exceptions import JobNotFoundError

        exc = JobNotFoundError(job_id="j999")
        response = _error_response(exc, "trace-abc")
        assert response.status_code == 404
        body = response.body.decode("utf-8")
        assert "JOB_NOT_FOUND" in body
        assert "trace-abc" in body

    def test_error_response_generic_exception(self):
        """非领域异常归一为 INTERNAL_ERROR。"""
        from book_dismantler.api.app import _error_response

        exc = RuntimeError("boom")
        response = _error_response(exc, "trace-xyz")
        assert response.status_code == 500
        assert "INTERNAL_ERROR" in response.body.decode("utf-8")
        assert "boom" in response.body.decode("utf-8")


class TestBookUpload:
    """书籍上传测试。"""

    def test_upload_pdf(self, uploaded_book: dict):
        """测试上传 PDF。"""
        assert "book_id" in uploaded_book
        assert uploaded_book["filename"] == "test_book.pdf"
        assert uploaded_book["size"] > 0

    def test_upload_invalid_extension(self, client: TestClient):
        """测试上传不支持的文件格式。"""
        response = client.post(
            "/api/books/upload",
            files={"file": ("test.txt", b"hello", "text/plain")},
        )
        assert response.status_code == 400
        assert "不支持" in response.json()["detail"]

    def test_upload_no_filename(self, client: TestClient):
        """测试上传空文件名。"""
        response = client.post(
            "/api/books/upload",
            files={"file": ("", b"hello", "application/pdf")},
        )
        # FastAPI 验证层返回 422 或应用层返回 400
        assert response.status_code in (400, 422)


class TestBookManagement:
    """书籍管理测试。"""

    def test_list_books(self, client: TestClient, uploaded_book: dict):
        """测试列出书籍。"""
        response = client.get("/api/books/list")
        assert response.status_code == 200
        books = response.json()["books"]
        assert len(books) >= 1
        assert any(b["book_id"] == uploaded_book["book_id"] for b in books)

    def test_list_books_returns_list(self, client: TestClient):
        """测试列表返回有效结构。"""
        response = client.get("/api/books/list")
        assert response.status_code == 200
        data = response.json()
        assert "books" in data
        assert isinstance(data["books"], list)

    def test_book_info(self, client: TestClient, uploaded_book: dict):
        """测试获取书籍信息。"""
        response = client.get(f"/api/books/{uploaded_book['book_id']}/info")
        assert response.status_code == 200
        info = response.json()
        assert info["book_id"] == uploaded_book["book_id"]
        assert info["filename"].endswith(".pdf")
        assert info["format"] == "pdf"

    def test_book_info_not_found(self, client: TestClient):
        """测试获取不存在书籍的信息。"""
        response = client.get("/api/books/nonexistent123/info")
        assert response.status_code == 404

    def test_delete_book(self, client: TestClient, uploaded_book: dict):
        """测试删除书籍。"""
        response = client.delete(f"/api/books/{uploaded_book['book_id']}")
        assert response.status_code == 200
        # 确认已删除
        response = client.get(f"/api/books/{uploaded_book['book_id']}/info")
        assert response.status_code == 404

    def test_delete_book_not_found(self, client: TestClient):
        """测试删除不存在的书籍。"""
        response = client.delete("/api/books/nonexistent123")
        assert response.status_code == 404


class TestJobManagement:
    """任务管理测试。"""

    def test_create_job(self, client: TestClient, uploaded_book: dict):
        """测试创建任务（不实际执行 LLM）。"""
        # Mock runner to avoid actual LLM calls
        with patch("book_dismantler.api.routers.jobs.DismantleRunner") as mock_runner_cls:
            mock_instance = mock_runner_cls.return_value
            mock_result = MagicMock()
            mock_result.book_title = "Test Book"
            mock_result.output_dir = "/tmp/test_output"
            mock_result.artifacts = []
            mock_result.knowledge_model = None
            mock_instance.run.return_value = mock_result

            response = client.post(
                "/api/jobs/create",
                json={"book_id": uploaded_book["book_id"]},
            )
            assert response.status_code == 200
            data = response.json()
            assert "job_id" in data
            assert data["status"] in ("pending", "running", "done")

    def test_create_job_book_not_found(self, client: TestClient):
        """测试为不存在的书籍创建任务。"""
        response = client.post(
            "/api/jobs/create",
            json={"book_id": "nonexistent123"},
        )
        assert response.status_code == 404

    def test_get_job_status_not_found(self, client: TestClient):
        """测试查询不存在的任务。"""
        response = client.get("/api/jobs/nonexistent123")
        assert response.status_code == 404

    def test_list_jobs_empty(self, client: TestClient):
        """测试空任务列表。"""
        response = client.get("/api/jobs/")
        assert response.status_code == 200
        assert response.json()["jobs"] == []

    def test_create_job_with_provider(self, client: TestClient, uploaded_book: dict):
        """测试指定 provider 创建任务。"""
        with patch("book_dismantler.api.routers.jobs.DismantleRunner") as mock_runner_cls:
            mock_instance = mock_runner_cls.return_value
            mock_result = MagicMock()
            mock_result.book_title = "Test Book"
            mock_result.output_dir = "/tmp/test_output"
            mock_result.artifacts = []
            mock_result.knowledge_model = None
            mock_instance.run.return_value = mock_result

            response = client.post(
                "/api/jobs/create",
                json={
                    "book_id": uploaded_book["book_id"],
                    "provider": "deepseek",
                    "model": "deepseek-chat",
                },
            )
            assert response.status_code == 200

    def test_cancel_completed_job_rejected(self, client: TestClient, uploaded_book: dict):
        """已完成的任务不能被取消。"""
        from book_dismantler.api.routers.jobs import get_job_store
        from book_dismantler.application.jobs import JobResult, JobStatus

        store = get_job_store()
        fake_id = "test-cancel-completed"
        job = JobResult(
            job_id=fake_id,
            book_title="Test",
            status=JobStatus.DONE,
            output_dir="/tmp/x",
        )
        store.add(job)
        try:
            response = client.post(f"/api/jobs/{fake_id}/cancel")
            assert response.status_code == 400
        finally:
            store.remove(fake_id)

    def test_cancel_nonexistent_job(self, client: TestClient):
        """取消不存在的任务返回 404。"""
        response = client.post("/api/jobs/nonexistent-cancel-123/cancel")
        assert response.status_code == 404


class TestArtifacts:
    """产物管理测试。"""

    def test_list_artifacts_not_found(self, client: TestClient):
        """测试列出不存在的产物。"""
        response = client.get("/api/artifacts/nonexistent123/list")
        assert response.status_code == 404

    def test_download_artifact_path_traversal(self, client: TestClient):
        """测试路径穿越攻击防护。"""
        # 先创建一个假的 job_dir
        response = client.get("/api/artifacts/fakejob/../../../etc/passwd")
        # FastAPI 会路由到 download_artifact，filename 包含 /
        assert response.status_code in (400, 404)

    def test_preview_artifact_path_traversal(self, client: TestClient):
        """测试预览路径穿越攻击防护。"""
        response = client.get("/api/artifacts/fakejob/preview/..%2F..%2Fetc%2Fpasswd")
        assert response.status_code in (400, 404)

    def test_list_artifacts_with_manifest(self, client: TestClient, tmp_path: Path):
        """测试带 manifest 的产物列表。"""
        # 直接在文件系统创建测试数据
        from book_dismantler.api.deps import get_output_base_dir
        output_dir = get_output_base_dir()

        job_dir = output_dir / "test_job_123"
        job_dir.mkdir(parents=True, exist_ok=True)

        # 创建 manifest
        manifest = {
            "job_id": "test_job_123",
            "artifacts": [
                {"filename": "notes.md", "artifact_type": "markdown", "size": 1024},
                {"filename": "mindmap.html", "artifact_type": "mindmap", "size": 2048},
            ],
        }
        (job_dir / "manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False), encoding="utf-8"
        )
        # 创建产物文件
        (job_dir / "notes.md").write_text("# Test Notes", encoding="utf-8")
        (job_dir / "mindmap.html").write_text("<html>test</html>", encoding="utf-8")

        response = client.get("/api/artifacts/test_job_123/list")
        assert response.status_code == 200
        data = response.json()
        assert "artifacts" in data
        assert len(data["artifacts"]) == 2

    def test_download_artifact(self, client: TestClient, tmp_path: Path):
        """测试下载产物文件。"""
        from book_dismantler.api.deps import get_output_base_dir
        output_dir = get_output_base_dir()

        job_dir = output_dir / "download_test_job"
        job_dir.mkdir(parents=True, exist_ok=True)
        (job_dir / "notes.md").write_text("# Test", encoding="utf-8")

        response = client.get("/api/artifacts/download_test_job/notes.md")
        assert response.status_code == 200

    def test_preview_artifact_html(self, client: TestClient):
        """测试预览 HTML 产物。"""
        from book_dismantler.api.deps import get_output_base_dir
        output_dir = get_output_base_dir()

        job_dir = output_dir / "preview_test_job"
        job_dir.mkdir(parents=True, exist_ok=True)
        (job_dir / "mindmap.html").write_text(
            "<html><body><h1>Mindmap</h1></body></html>", encoding="utf-8"
        )

        response = client.get("/api/artifacts/preview_test_job/preview/mindmap.html")
        assert response.status_code == 200
        assert "text/html" in response.headers.get("content-type", "")

    def test_preview_artifact_markdown(self, client: TestClient):
        """测试预览 Markdown 产物。"""
        from book_dismantler.api.deps import get_output_base_dir
        output_dir = get_output_base_dir()

        job_dir = output_dir / "preview_md_job"
        job_dir.mkdir(parents=True, exist_ok=True)
        (job_dir / "notes.md").write_text("# Markdown Notes", encoding="utf-8")

        response = client.get("/api/artifacts/preview_md_job/preview/notes.md")
        assert response.status_code == 200

    def test_download_nonexistent_file(self, client: TestClient):
        """测试下载不存在的文件。"""
        from book_dismantler.api.deps import get_output_base_dir
        output_dir = get_output_base_dir()

        job_dir = output_dir / "missing_file_job"
        job_dir.mkdir(parents=True, exist_ok=True)

        response = client.get("/api/artifacts/missing_file_job/nonexistent.md")
        assert response.status_code == 404

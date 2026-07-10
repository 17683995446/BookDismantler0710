"""应用层测试：Runner、Jobs、CLI。"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest
from typer.testing import CliRunner

from book_dismantler.application.jobs import JobResult, JobStatus
from book_dismantler.application.runner import DismantleResult, DismantleRunner
from book_dismantler.cli.main import app
from book_dismantler.core.config import Settings, get_settings
from book_dismantler.domain.document import (
    Chapter,
    Metadata,
    Paragraph,
    ParsedDocument,
    Section,
)
from book_dismantler.domain.knowledge import (
    Concept,
    KnowledgeModel,
)
from book_dismantler.llm.base import LLMClient, StructuredResponse, Usage

# ---------------------------------------------------------------------------
# Jobs
# ---------------------------------------------------------------------------

class TestJobResult:
    def test_default_pending(self) -> None:
        job = JobResult(job_id="test-1")
        assert job.status == JobStatus.PENDING
        assert not job.is_success

    def test_mark_running(self) -> None:
        job = JobResult(job_id="test-1")
        job.mark_running()
        assert job.status == JobStatus.RUNNING

    def test_mark_done(self) -> None:
        job = JobResult(job_id="test-1")
        job.mark_running()
        job.mark_done("/tmp/output", ["notes.md", "mindmap.html"])
        assert job.status == JobStatus.DONE
        assert job.is_success
        assert len(job.artifact_paths) == 2
        assert job.duration_seconds is not None

    def test_mark_failed(self) -> None:
        job = JobResult(job_id="test-1")
        job.mark_running()
        job.mark_failed("LLM 超时")
        assert job.status == JobStatus.FAILED
        assert job.error == "LLM 超时"
        assert not job.is_success


# ---------------------------------------------------------------------------
# DismantleRunner
# ---------------------------------------------------------------------------

class TestDismantleRunner:
    """Runner 测试（使用 mock LLM）。"""

    def _make_settings(self, tmp_path: Path) -> Settings:
        return Settings(
            output_dir=tmp_path,
            default_provider="deepseek",
            deepseek_api_key="sk-test",
        )

    def _make_mock_client(self) -> MagicMock:
        """返回固定 KnowledgeModel 的 mock client。"""
        client = MagicMock(spec=LLMClient)
        response = StructuredResponse(
            raw_content='{"concepts": [{"name": "测试概念"}]}',
            parsed={
                "nodes": [{"title": "第一章", "summary": "概述", "level": 1}],
                "concepts": [{"name": "测试概念", "definition": "测试定义", "importance": "high"}],
                "relationships": [
                    {"source": "A", "target": "B", "type": "supports"}
                ],
                "concept": "测试概念",
                "definition": "测试定义",
                "characteristics": ["特征1"],
                "applications": ["应用1"],
                "insight": "洞察",
            },
            usage=Usage(prompt_tokens=10, completion_tokens=5, total_tokens=15),
            model="mock",
        )
        client.complete.return_value = response
        return client

    def test_parse_only(self, sample_pdf_path: Path, tmp_path: Path) -> None:
        settings = self._make_settings(tmp_path)
        runner = DismantleRunner(settings=settings)
        doc = runner.parse_only(sample_pdf_path)
        assert doc.chapter_count >= 1

    def test_run_full_pipeline_mock(
        self, sample_pdf_path: Path, tmp_path: Path
    ) -> None:
        """完整流水线（mock LLM）。"""
        settings = self._make_settings(tmp_path)
        client = self._make_mock_client()
        runner = DismantleRunner(client=client, settings=settings)

        result = runner.run(sample_pdf_path, output_dir=tmp_path / "output")

        assert isinstance(result, DismantleResult)
        assert result.book_title != ""
        assert len(result.artifacts) >= 5  # 6种产物，至少5种成功
        assert Path(result.output_dir).exists()
        # manifest 存在
        assert (Path(result.output_dir) / "manifest.json").exists()

    def test_run_progress_callback(
        self, sample_pdf_path: Path, tmp_path: Path
    ) -> None:
        """进度回调被调用。"""
        settings = self._make_settings(tmp_path)
        client = self._make_mock_client()
        runner = DismantleRunner(client=client, settings=settings)

        progress_calls: list = []
        result = runner.run(
            sample_pdf_path,
            output_dir=tmp_path / "out",
            on_progress=lambda p, s="": progress_calls.append((p, s)),
        )
        assert len(progress_calls) >= 1
        assert result.knowledge_model is not None

    def test_run_nonexistent_file_raises(self, tmp_path: Path) -> None:
        settings = self._make_settings(tmp_path)
        runner = DismantleRunner(settings=settings)
        with pytest.raises(Exception, match="文件不存在"):
            runner.run("/nonexistent/file.pdf")

    def test_render_only(self, tmp_path: Path) -> None:
        settings = self._make_settings(tmp_path)
        runner = DismantleRunner(settings=settings)
        model = KnowledgeModel(
            book_title="测试",
            concepts=[Concept(name="概念A")],
        )
        artifacts = runner.render_only(model)
        assert len(artifacts) >= 5

    def test_analyze_only_with_mock(self, tmp_path: Path) -> None:
        settings = self._make_settings(tmp_path)
        client = self._make_mock_client()
        runner = DismantleRunner(client=client, settings=settings)

        doc = ParsedDocument(
            metadata=Metadata(title="测试书"),
            chapters=[
                Chapter(
                    title="第一章",
                    sections=[
                        Section(paragraphs=[
                            Paragraph(text="知识管理很重要。", index=0),
                        ])
                    ],
                    index=0,
                )
            ],
        )
        model = runner.analyze_only(doc)
        assert model.concept_count >= 0  # mock 可能返回数据


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

class TestCLI:
    """CLI 命令测试。"""

    def setup_method(self) -> None:
        self.runner = CliRunner()

    def test_version(self) -> None:
        result = self.runner.invoke(app, ["--version"])
        assert result.exit_code == 0
        assert "book-dismantler" in result.output

    def test_help(self) -> None:
        result = self.runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        assert "dismantle" in result.output

    def test_providers_list(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("BOOK_DISMANTLER_OUTPUT_DIR", str(tmp_path))
        get_settings.cache_clear()
        result = self.runner.invoke(app, ["providers", "list"])
        assert result.exit_code == 0
        assert "deepseek" in result.output or "openai" in result.output

    def test_parse_command(self, sample_pdf_path: Path, tmp_path: Path) -> None:
        output_file = tmp_path / "parsed.json"
        result = self.runner.invoke(
            app,
            ["parse", str(sample_pdf_path), "--output", str(output_file)],
        )
        assert result.exit_code == 0
        assert output_file.exists()
        # 验证可反序列化
        doc = ParsedDocument.model_validate_json(output_file.read_text(encoding="utf-8"))
        assert doc.chapter_count >= 1

    def test_parse_nonexistent(self) -> None:
        result = self.runner.invoke(app, ["parse", "/nonexistent.pdf"])
        assert result.exit_code == 1

    def test_render_command(self, tmp_path: Path) -> None:
        """render 子命令测试。"""
        model = KnowledgeModel(
            book_title="CLI测试",
            concepts=[Concept(name="概念")],
        )
        model_file = tmp_path / "model.json"
        model_file.write_text(model.model_dump_json(), encoding="utf-8")

        out_dir = tmp_path / "rendered"
        result = self.runner.invoke(
            app,
            ["render", str(model_file), "--output", str(out_dir)],
        )
        assert result.exit_code == 0
        assert out_dir.exists()
        # 至少有一个产物
        assert len(list(out_dir.iterdir())) >= 1

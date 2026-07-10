"""导出层测试：HTML 导出、打包器。"""

from __future__ import annotations

import json
from pathlib import Path

from book_dismantler.domain.knowledge import (
    Concept,
    KnowledgeModel,
)
from book_dismantler.export.bundler import ArtifactBundler
from book_dismantler.export.html_exporter import HtmlExporter
from book_dismantler.rendering.base import ArtifactType, RenderedArtifact


class TestHtmlExporter:
    def test_export(self, tmp_path: Path) -> None:
        artifact = RenderedArtifact(
            artifact_type=ArtifactType.MINDMAP_HTML,
            content="<html><body>测试</body></html>",
            title="测试页面",
        )
        exporter = HtmlExporter()
        path = exporter.export(artifact, tmp_path)

        assert path.exists()
        assert path.suffix == ".html"
        assert "测试" in path.read_text(encoding="utf-8")

    def test_export_custom_filename(self, tmp_path: Path) -> None:
        artifact = RenderedArtifact(
            artifact_type=ArtifactType.CONCEPT_CARD,
            content="<html>内容</html>",
            title="标题",
        )
        exporter = HtmlExporter()
        path = exporter.export(artifact, tmp_path, filename="custom.html")
        assert path.name == "custom.html"

    def test_export_inline_adds_notice(self, tmp_path: Path) -> None:
        artifact = RenderedArtifact(
            artifact_type=ArtifactType.MINDMAP_HTML,
            content="<html><head></head><body>内容</body></html>",
            title="测试",
        )
        exporter = HtmlExporter()
        path = exporter.export_inline(artifact, tmp_path)
        content = path.read_text(encoding="utf-8")
        assert "CDN" in content  # 离线说明


class TestArtifactBundler:
    def test_bundle_creates_directory(self, tmp_path: Path) -> None:
        model = KnowledgeModel(
            book_title="测试书",
            concepts=[Concept(name="概念A")],
        )
        artifacts = [
            RenderedArtifact(
                artifact_type=ArtifactType.MARKDOWN_NOTES,
                content="# 笔记\n内容",
                title="测试书",
            ),
            RenderedArtifact(
                artifact_type=ArtifactType.MINDMAP_HTML,
                content="<html>导图</html>",
                title="测试书",
            ),
        ]
        bundler = ArtifactBundler()
        result = bundler.bundle(artifacts, model, tmp_path / "output")

        assert result.exists()
        assert (result / "manifest.json").exists()
        assert (result / "knowledge_model.json").exists()

    def test_bundle_manifest_content(self, tmp_path: Path) -> None:
        model = KnowledgeModel(
            book_title="书名",
            book_author="作者",
            concepts=[Concept(name="A"), Concept(name="B")],
        )
        artifacts = [
            RenderedArtifact(
                artifact_type=ArtifactType.MARKDOWN_NOTES,
                content="# 内容",
                title="书名",
            ),
        ]
        bundler = ArtifactBundler()
        result = bundler.bundle(artifacts, model, tmp_path / "out")

        manifest = json.loads((result / "manifest.json").read_text(encoding="utf-8"))
        assert manifest["book_title"] == "书名"
        assert manifest["artifact_count"] == 2  # 1 artifact + knowledge_model
        assert manifest["stats"]["concepts"] == 2

    def test_bundle_creates_zip(self, tmp_path: Path) -> None:
        model = KnowledgeModel(book_title="书")
        artifacts = [
            RenderedArtifact(
                artifact_type=ArtifactType.MARKDOWN_NOTES,
                content="# 内容",
                title="书",
            ),
        ]
        bundler = ArtifactBundler()
        result = bundler.bundle(artifacts, model, tmp_path / "out", create_zip=True)

        assert result.suffix == ".zip"
        assert result.exists()

    def test_bundle_knowledge_model_json(self, tmp_path: Path) -> None:
        model = KnowledgeModel(
            book_title="测试",
            concepts=[Concept(name="概念", definition="定义")],
        )
        bundler = ArtifactBundler()
        result = bundler.bundle([], model, tmp_path / "out")

        model_file = result / "knowledge_model.json"
        assert model_file.exists()
        loaded = KnowledgeModel.model_validate_json(model_file.read_text(encoding="utf-8"))
        assert loaded.book_title == "测试"
        assert loaded.concept_count == 1

"""端到端系统测试。

验证完整的拆书流程：解析 → 分析 → 渲染 → 导出。
使用 Mock LLM 客户端，不依赖真实 API。
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from book_dismantler.domain.knowledge import (
    Concept,
    ConceptImportance,
    KnowledgeModel,
    OutlineNode,
    Relationship,
    RelationshipType,
)
from book_dismantler.export.bundler import ArtifactBundler
from book_dismantler.rendering.anatomy.anatomy_renderer import AnatomyChartRenderer
from book_dismantler.rendering.cards.card_renderer import ConceptCardRenderer
from book_dismantler.rendering.infographic.poster import InfographicRenderer
from book_dismantler.rendering.mindmap.markmap import MarkmapRenderer
from book_dismantler.rendering.notes.markdown import MarkdownRenderer
from book_dismantler.rendering.notes.orgmode import OrgModeRenderer


@pytest.fixture()
def sample_knowledge_model() -> KnowledgeModel:
    """创建一个包含完整知识结构的测试模型。"""
    outline = OutlineNode(
        title="深度工作",
        children=[
            OutlineNode(title="第一部分：理念", children=[
                OutlineNode(title="深度工作的价值"),
                OutlineNode(title="深度工作的稀缺性"),
            ]),
            OutlineNode(title="第二部分：规则", children=[
                OutlineNode(title="工作要深入"),
                OutlineNode(title="拥抱无聊"),
            ]),
        ],
    )

    concepts = [
        Concept(
            name="深度工作",
            definition="在无干扰状态下专注进行职业活动，使个人认知能力达到极限。",
            importance=ConceptImportance.HIGH,
            source_chunk=0,
        ),
        Concept(
            name="浮浅工作",
            definition="在容易被干扰的状态下进行的事务性任务，往往不会创造太多新价值。",
            importance=ConceptImportance.HIGH,
            source_chunk=0,
        ),
        Concept(
            name="注意力残留",
            definition="从任务 A 切换到任务 B 时，注意力仍部分停留在 A 上的现象。",
            importance=ConceptImportance.MEDIUM,
            source_chunk=1,
        ),
    ]

    relationships = [
        Relationship(
            source="深度工作",
            target="浮浅工作",
            type=RelationshipType.CONTRADICTS,
            description="深度工作与浮浅工作是对立的工作模式",
        ),
        Relationship(
            source="注意力残留",
            target="深度工作",
            type=RelationshipType.DEPENDS_ON,
            description="注意力残留会影响深度工作的质量",
        ),
    ]

    return KnowledgeModel(
        book_title="深度工作",
        book_author="Cal Newport",
        outline=[outline],
        concepts=concepts,
        relationships=relationships,
    )


class TestEndToEndRendering:
    """端到端渲染测试：KnowledgeModel → 全部6种产物。"""

    def test_all_renderers_produce_valid_output(
        self, sample_knowledge_model: KnowledgeModel
    ):
        """测试所有渲染器都能从同一个 KnowledgeModel 生成有效产物。"""
        renderers = [
            MarkdownRenderer(),
            OrgModeRenderer(),
            MarkmapRenderer(),
            ConceptCardRenderer(),
            InfographicRenderer(),
            AnatomyChartRenderer(),
        ]

        artifacts = []
        for renderer in renderers:
            artifact = renderer.render(sample_knowledge_model)
            assert artifact is not None
            assert artifact.content
            assert len(artifact.content) > 50
            assert artifact.artifact_type is not None
            artifacts.append(artifact)

        assert len(artifacts) == 6

    def test_markdown_contains_all_concepts(
        self, sample_knowledge_model: KnowledgeModel
    ):
        """测试 Markdown 产物包含所有概念。"""
        renderer = MarkdownRenderer()
        artifact = renderer.render(sample_knowledge_model)
        for concept in sample_knowledge_model.concepts:
            assert concept.name in artifact.content

    def test_markmap_contains_outline(
        self, sample_knowledge_model: KnowledgeModel
    ):
        """测试思维导图包含大纲结构。"""
        renderer = MarkmapRenderer()
        artifact = renderer.render(sample_knowledge_model)
        assert "深度工作" in artifact.content
        assert "理念" in artifact.content or "规则" in artifact.content

    def test_cards_contain_concepts(
        self, sample_knowledge_model: KnowledgeModel
    ):
        """测试知识卡片包含概念信息。"""
        renderer = ConceptCardRenderer()
        artifact = renderer.render(sample_knowledge_model)
        assert "深度工作" in artifact.content

    def test_infographic_contains_stats(
        self, sample_knowledge_model: KnowledgeModel
    ):
        """测试信息图包含统计信息。"""
        renderer = InfographicRenderer()
        artifact = renderer.render(sample_knowledge_model)
        assert "概念" in artifact.content or "concept" in artifact.content.lower()

    def test_anatomy_chart_renders(
        self, sample_knowledge_model: KnowledgeModel
    ):
        """测试概念剖析图能正常渲染。"""
        renderer = AnatomyChartRenderer()
        artifact = renderer.render(sample_knowledge_model)
        assert artifact.content


class TestEndToEndBundling:
    """端到端打包测试：产物 → manifest → 文件系统。"""

    def test_bundle_creates_complete_output(
        self, sample_knowledge_model: KnowledgeModel, tmp_path: Path
    ):
        """测试打包流程生成完整输出目录。"""
        renderers = [
            MarkdownRenderer(),
            OrgModeRenderer(),
            MarkmapRenderer(),
            ConceptCardRenderer(),
            InfographicRenderer(),
            AnatomyChartRenderer(),
        ]

        artifacts = [r.render(sample_knowledge_model) for r in renderers]

        bundler = ArtifactBundler()
        output_dir = tmp_path / "test_book"
        bundle_path = bundler.bundle(artifacts, sample_knowledge_model, output_dir)

        # 验证目录存在
        assert bundle_path.exists()
        assert bundle_path.is_dir()

        # 验证 manifest 存在且有效
        manifest_path = bundle_path / "manifest.json"
        assert manifest_path.exists()
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        assert "artifacts" in manifest
        assert len(manifest["artifacts"]) >= 6

        # 验证 knowledge_model.json 存在
        km_path = bundle_path / "knowledge_model.json"
        assert km_path.exists()
        km_data = json.loads(km_path.read_text(encoding="utf-8"))
        assert km_data["book_title"] == "深度工作"

        # 验证产物文件存在
        saved_files = list(bundle_path.iterdir())
        file_names = [f.name for f in saved_files if f.is_file()]
        assert "manifest.json" in file_names
        assert "knowledge_model.json" in file_names
        assert len(file_names) >= 5  # artifacts + manifest + knowledge_model


class TestEndToEndSerialization:
    """端到端序列化测试：KnowledgeModel 序列化/反序列化往返。"""

    def test_knowledge_model_roundtrip(
        self, sample_knowledge_model: KnowledgeModel
    ):
        """测试 KnowledgeModel JSON 序列化往返。"""
        json_str = sample_knowledge_model.model_dump_json(indent=2)
        restored = KnowledgeModel.model_validate_json(json_str)

        assert restored.book_title == sample_knowledge_model.book_title
        assert restored.book_author == sample_knowledge_model.book_author
        assert restored.concept_count == sample_knowledge_model.concept_count
        assert restored.relationship_count == sample_knowledge_model.relationship_count

        # 验证概念保留
        for original, restored_c in zip(
            sample_knowledge_model.concepts, restored.concepts, strict=False
        ):
            assert original.name == restored_c.name
            assert original.definition == restored_c.definition

    def test_rendered_from_restored_model(
        self, sample_knowledge_model: KnowledgeModel
    ):
        """测试从反序列化的模型渲染产物。"""
        json_str = sample_knowledge_model.model_dump_json()
        restored = KnowledgeModel.model_validate_json(json_str)

        renderer = MarkdownRenderer()
        artifact = renderer.render(restored)
        assert "深度工作" in artifact.content
        assert "浮浅工作" in artifact.content


class TestSystemIntegration:
    """系统集成测试：跨层协作验证。"""

    def test_full_pipeline_with_mock_llm(self, tmp_path: Path):
        """使用 Mock LLM 验证完整管道流程。"""
        from book_dismantler.analysis.pipeline import AnalysisPipeline
        from book_dismantler.analysis.strategies.concepts import ConceptStrategy
        from book_dismantler.analysis.strategies.outline import OutlineStrategy
        from book_dismantler.domain.document import (
            Chapter,
            Metadata,
            Paragraph,
            ParsedDocument,
            Section,
        )
        from book_dismantler.llm.base import LLMClient, StructuredResponse, Usage

        # 创建 Mock LLM 客户端
        mock_client = MagicMock(spec=LLMClient)

        def mock_complete(messages, **kwargs):
            content = messages[-1].content
            if "大纲" in content or "outline" in content.lower():
                return StructuredResponse(
                    raw_content='{"nodes": [{"title": "测试章节", "children": []}]}',
                    parsed={"nodes": [{"title": "测试章节", "children": []}]},
                    model="mock-model",
                    usage=Usage(prompt_tokens=10, completion_tokens=20),
                )
            elif "概念" in content or "concept" in content.lower():
                return StructuredResponse(
                    raw_content='{"concepts": [{"name": "测试概念", '
                    '"definition": "测试定义", "importance": "high", '
                    '"source_chunk": 0}]}',
                    parsed={"concepts": [{"name": "测试概念",
                    "definition": "测试定义", "importance": "high",
                    "source_chunk": 0}]},
                    model="mock-model",
                    usage=Usage(prompt_tokens=10, completion_tokens=20),
                )
            return StructuredResponse(
                raw_content="{}",
                parsed={},
                model="mock-model",
                usage=Usage(prompt_tokens=5, completion_tokens=5),
            )

        mock_client.complete = mock_complete

        # 创建测试文档
        doc = ParsedDocument(
            metadata=Metadata(title="测试书", author="测试作者"),
            chapters=[
                Chapter(
                    index=0,
                    title="第一章",
                    sections=[
                        Section(
                            title="第一节",
                            paragraphs=[
                                Paragraph(
                                    text="这是一段测试文本，用于验证完整的拆书管道流程。",
                                    index=0,
                                ),
                            ],
                        ),
                    ],
                ),
            ],
        )

        # 运行管道
        pipeline = AnalysisPipeline(
            client=mock_client,
            strategies=[
                OutlineStrategy(mock_client, book_title="测试书"),
                ConceptStrategy(mock_client, book_title="测试书"),
            ],
            chunk_size=2000,
            chunk_overlap=200,
        )

        model = pipeline.run(doc)

        # 验证结果 —— 必须有实际内容，而非空模型
        assert model is not None
        assert model.book_title == "测试书"
        assert model.outline_node_count >= 1, "大纲节点应来自 mock LLM 响应"
        assert model.concept_count >= 1, "概念数应来自 mock LLM 响应"
        assert any(c.name == "测试概念" for c in model.concepts), "应包含 mock 返回的概念"

"""渲染层单元测试：Markdown/org 笔记 + 思维导图 HTML。"""

from __future__ import annotations

import pytest

from book_dismantler.domain.knowledge import (
    Concept,
    ConceptAnatomy,
    ConceptComparison,
    ConceptImportance,
    KnowledgeModel,
    OutlineNode,
    Relationship,
    RelationshipType,
)
from book_dismantler.rendering.base import ArtifactType
from book_dismantler.rendering.mindmap.markmap import MarkmapRenderer
from book_dismantler.rendering.notes.markdown import MarkdownRenderer
from book_dismantler.rendering.notes.orgmode import OrgModeRenderer


@pytest.fixture
def sample_knowledge_model() -> KnowledgeModel:
    """完整测试知识模型。"""
    return KnowledgeModel(
        book_title="测试之书",
        book_author="测试作者",
        summary="这是一本关于知识管理的测试书籍。",
        outline=[
            OutlineNode(
                title="第一章 基础",
                summary="介绍基础知识",
                level=1,
                children=[
                    OutlineNode(title="1.1 概念", summary="核心概念", level=2),
                ],
            ),
        ],
        concepts=[
            Concept(
                name="知识管理",
                definition="系统管理知识的方法论",
                type="方法论",
                examples=["知识库", "SECI模型"],
                importance=ConceptImportance.HIGH,
                source_chapter="第一章",
            ),
            Concept(
                name="SECI模型",
                definition="知识转化模型",
                importance=ConceptImportance.MEDIUM,
            ),
        ],
        relationships=[
            Relationship(
                source="知识管理",
                target="SECI模型",
                type=RelationshipType.PART_OF,
                description="SECI是KM的核心模型",
            ),
        ],
        anatomies=[
            ConceptAnatomy(
                concept="知识管理",
                definition="系统管理知识的方法论",
                characteristics=["系统性", "持续性"],
                comparisons=[
                    ConceptComparison(
                        concept="信息管理",
                        similarity="都处理信息",
                        difference="KM更重应用",
                    )
                ],
                applications=["企业知识库"],
                counterexamples=["单纯文件存储"],
                insight="知识不在多，在用。",
            ),
        ],
    )


@pytest.fixture
def empty_knowledge_model() -> KnowledgeModel:
    """空知识模型。"""
    return KnowledgeModel()


# ---------------------------------------------------------------------------
# MarkdownRenderer
# ---------------------------------------------------------------------------

class TestMarkdownRenderer:
    def test_artifact_type(self) -> None:
        r = MarkdownRenderer()
        assert r.artifact_type == ArtifactType.MARKDOWN_NOTES

    def test_render_full(self, sample_knowledge_model: KnowledgeModel) -> None:
        r = MarkdownRenderer()
        artifact = r.render(sample_knowledge_model)

        assert artifact.artifact_type == ArtifactType.MARKDOWN_NOTES
        assert "# 测试之书" in artifact.content
        assert "测试作者" in artifact.content
        assert "全书总结" in artifact.content
        assert "结构大纲" in artifact.content
        assert "核心概念" in artifact.content
        assert "知识管理" in artifact.content
        assert "概念关系" in artifact.content
        assert "概念深度解剖" in artifact.content

    def test_render_markdown_structure(self, sample_knowledge_model: KnowledgeModel) -> None:
        """Markdown 标题层级正确。"""
        r = MarkdownRenderer()
        artifact = r.render(sample_knowledge_model)
        # H1 标题
        assert "# 测试之书" in artifact.content
        # H2 标题
        assert "## 全书总结" in artifact.content
        # 表格
        assert "| 源概念 |" in artifact.content

    def test_render_concept_with_importance_icon(
        self, sample_knowledge_model: KnowledgeModel
    ) -> None:
        r = MarkdownRenderer()
        artifact = r.render(sample_knowledge_model)
        # HIGH importance should have red circle
        assert "🔴" in artifact.content

    def test_render_empty_model(self, empty_knowledge_model: KnowledgeModel) -> None:
        r = MarkdownRenderer()
        artifact = r.render(empty_knowledge_model)
        assert "# 拆书笔记" in artifact.content
        assert "共 0 个概念" in artifact.content

    def test_save(self, sample_knowledge_model: KnowledgeModel, tmp_path) -> None:
        r = MarkdownRenderer()
        artifact = r.render(sample_knowledge_model)
        path = r.save(artifact, tmp_path)
        assert path.exists()
        assert path.suffix == ".md"
        content = path.read_text(encoding="utf-8")
        assert "测试之书" in content

    def test_render_outline_with_children(self, sample_knowledge_model: KnowledgeModel) -> None:
        """大纲节点递归渲染（### 标题 + 子节点 #### 标题）。"""
        r = MarkdownRenderer()
        artifact = r.render(sample_knowledge_model)
        # sample_knowledge_model 已有 outline，包含嵌套
        assert "### " in artifact.content
        # 嵌套节点的深度
        assert "#### " in artifact.content or "##### " in artifact.content

    def test_render_concept_with_examples(self, sample_knowledge_model: KnowledgeModel) -> None:
        """概念包含 examples 时应在 Markdown 中以列表渲染。"""
        r = MarkdownRenderer()
        artifact = r.render(sample_knowledge_model)
        assert "**示例**" in artifact.content

    def test_render_anatomy_full(self, sample_knowledge_model: KnowledgeModel) -> None:
        """解剖图应包含：定义/特征/对比/应用/反例/洞察。"""
        r = MarkdownRenderer()
        artifact = r.render(sample_knowledge_model)
        assert "🔬" in artifact.content  # 解剖标题
        assert "**核心特征**" in artifact.content
        assert "**概念对比**" in artifact.content
        assert "**应用场景**" in artifact.content
        assert "**反例**" in artifact.content
        assert "💡" in artifact.content  # 洞察图标

    def test_render_relationships_table(self, sample_knowledge_model: KnowledgeModel) -> None:
        """关系应渲染为 Markdown 表格。"""
        r = MarkdownRenderer()
        artifact = r.render(sample_knowledge_model)
        assert "| 源概念 | 关系 | 目标概念 | 说明 |" in artifact.content
        assert "|--------|------|----------|------|" in artifact.content

    def test_render_summary_section(self) -> None:
        """summary 字段存在时应输出"## 全书总结"。"""
        from book_dismantler.domain.knowledge import KnowledgeModel
        model = KnowledgeModel(
            book_title="总结测试",
            summary="这是一段测试总结。",
        )
        r = MarkdownRenderer()
        artifact = r.render(model)
        assert "## 全书总结" in artifact.content
        assert "这是一段测试总结。" in artifact.content

    def test_render_author_quote(self) -> None:
        """作者存在时应在标题下显示引用块。"""
        from book_dismantler.domain.knowledge import KnowledgeModel
        model = KnowledgeModel(book_title="无作者", book_author="小明")
        r = MarkdownRenderer()
        artifact = r.render(model)
        assert "> 作者：小明" in artifact.content


# ---------------------------------------------------------------------------
# OrgModeRenderer
# ---------------------------------------------------------------------------

class TestOrgModeRenderer:
    def test_artifact_type(self) -> None:
        r = OrgModeRenderer()
        assert r.artifact_type == ArtifactType.ORG_NOTES

    def test_render_full(self, sample_knowledge_model: KnowledgeModel) -> None:
        r = OrgModeRenderer()
        artifact = r.render(sample_knowledge_model)

        assert artifact.artifact_type == ArtifactType.ORG_NOTES
        assert "#+TITLE: 测试之书" in artifact.content
        assert "#+AUTHOR: 测试作者" in artifact.content
        assert "* 全书总结" in artifact.content
        assert "* 结构大纲" in artifact.content
        assert "* 核心概念" in artifact.content
        assert "** 知识管理" in artifact.content
        assert ":PROPERTIES:" in artifact.content
        assert ":END:" in artifact.content

    def test_render_concept_properties(self, sample_knowledge_model: KnowledgeModel) -> None:
        r = OrgModeRenderer()
        artifact = r.render(sample_knowledge_model)
        assert ":IMPORTANCE: high" in artifact.content
        assert ":TYPE: 方法论" in artifact.content

    def test_render_anatomy(self, sample_knowledge_model: KnowledgeModel) -> None:
        r = OrgModeRenderer()
        artifact = r.render(sample_knowledge_model)
        assert "* 概念深度解剖" in artifact.content
        assert "#+BEGIN_QUOTE" in artifact.content
        assert "#+END_QUOTE" in artifact.content

    def test_render_empty(self, empty_knowledge_model: KnowledgeModel) -> None:
        r = OrgModeRenderer()
        artifact = r.render(empty_knowledge_model)
        assert "#+TITLE:" in artifact.content

    def test_save(self, sample_knowledge_model: KnowledgeModel, tmp_path) -> None:
        r = OrgModeRenderer()
        artifact = r.render(sample_knowledge_model)
        path = r.save(artifact, tmp_path)
        assert path.exists()
        assert path.suffix == ".org"


# ---------------------------------------------------------------------------
# MarkmapRenderer
# ---------------------------------------------------------------------------

class TestMarkmapRenderer:
    def test_artifact_type(self) -> None:
        r = MarkmapRenderer()
        assert r.artifact_type == ArtifactType.MINDMAP_HTML

    def test_render_full(self, sample_knowledge_model: KnowledgeModel) -> None:
        r = MarkmapRenderer()
        artifact = r.render(sample_knowledge_model)

        assert artifact.artifact_type == ArtifactType.MINDMAP_HTML
        assert "<!DOCTYPE html>" in artifact.content
        assert "测试之书" in artifact.content
        assert "<svg id=\"mindmap\">" in artifact.content
        assert "markmap-view" in artifact.content

    def test_html_contains_markdown_data(self, sample_knowledge_model: KnowledgeModel) -> None:
        """HTML 中嵌入了 Markdown 大纲数据。"""
        r = MarkmapRenderer()
        artifact = r.render(sample_knowledge_model)
        # 嵌入的 JSON 数据
        assert "const markdown" in artifact.content
        assert "知识管理" in artifact.content
        assert "核心概念" in artifact.content

    def test_html_has_download_button(self, sample_knowledge_model: KnowledgeModel) -> None:
        r = MarkmapRenderer()
        artifact = r.render(sample_knowledge_model)
        assert "downloadSvg" in artifact.content
        assert "下载" in artifact.content

    def test_render_empty(self, empty_knowledge_model: KnowledgeModel) -> None:
        r = MarkmapRenderer()
        artifact = r.render(empty_knowledge_model)
        assert "<!DOCTYPE html>" in artifact.content
        assert "思维导图" in artifact.content

    def test_save(self, sample_knowledge_model: KnowledgeModel, tmp_path) -> None:
        r = MarkmapRenderer()
        artifact = r.render(sample_knowledge_model)
        path = r.save(artifact, tmp_path)
        assert path.exists()
        assert path.suffix == ".html"

    def test_outline_rendered_as_nested_list(
        self, sample_knowledge_model: KnowledgeModel
    ) -> None:
        r = MarkmapRenderer()
        artifact = r.render(sample_knowledge_model)
        # 嵌套列表
        assert "- 第一章 基础" in artifact.content
        assert "- 1.1 概念" in artifact.content

    def test_concepts_with_icons(self, sample_knowledge_model: KnowledgeModel) -> None:
        r = MarkmapRenderer()
        artifact = r.render(sample_knowledge_model)
        assert "🔴" in artifact.content  # HIGH importance

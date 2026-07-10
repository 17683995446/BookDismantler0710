"""渲染层 II 测试：概念卡片、信息图、解剖图。"""

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
from book_dismantler.rendering.anatomy.anatomy_renderer import AnatomyChartRenderer
from book_dismantler.rendering.cards.card_renderer import ConceptCardRenderer
from book_dismantler.rendering.cards.deck import CardDeckRenderer
from book_dismantler.rendering.infographic.poster import InfographicRenderer


@pytest.fixture
def rich_knowledge_model() -> KnowledgeModel:
    """富含各种数据的测试知识模型。"""
    return KnowledgeModel(
        book_title="知识管理入门",
        book_author="测试作者",
        summary="知识管理的入门指南。",
        outline=[
            OutlineNode(title="第一章", summary="基础", children=[
                OutlineNode(title="1.1", summary="子节")
            ]),
        ],
        concepts=[
            Concept(name="知识管理", definition="系统管理知识的方法论", type="方法论",
                    examples=["知识库", "SECI模型"], importance=ConceptImportance.HIGH,
                    source_chapter="第一章"),
            Concept(name="SECI模型", definition="知识转化模型", type="模型",
                    importance=ConceptImportance.MEDIUM),
            Concept(name="隐性知识", definition="难以表达的知识", type="术语",
                    importance=ConceptImportance.LOW),
        ],
        relationships=[
            Relationship(source="知识管理", target="SECI模型", type=RelationshipType.PART_OF,
                         description="SECI是KM的核心"),
            Relationship(source="隐性知识", target="显性知识", type=RelationshipType.CONTRADICTS),
        ],
        anatomies=[
            ConceptAnatomy(
                concept="知识管理",
                definition="系统管理知识的方法论",
                characteristics=["系统性", "持续性", "目标导向"],
                comparisons=[
                    ConceptComparison(concept="信息管理", similarity="都处理信息",
                                      difference="KM更重应用")
                ],
                applications=["企业知识库", "学习型组织"],
                counterexamples=["单纯文件存储"],
                insight="知识不在多，在用。",
            ),
        ],
    )


# ---------------------------------------------------------------------------
# ConceptCardRenderer
# ---------------------------------------------------------------------------

class TestConceptCardRenderer:
    def test_render_full(self, rich_knowledge_model: KnowledgeModel) -> None:
        r = ConceptCardRenderer()
        artifact = r.render(rich_knowledge_model)

        assert "<!DOCTYPE html>" in artifact.content
        assert "知识管理" in artifact.content
        assert "SECI模型" in artifact.content
        assert "concept-card" in artifact.content
        assert artifact.metadata["card_count"] == 3

    def test_card_has_importance_colors(self, rich_knowledge_model: KnowledgeModel) -> None:
        r = ConceptCardRenderer()
        artifact = r.render(rich_knowledge_model)
        # HIGH importance should use red theme
        assert "#e11d48" in artifact.content or "#E11D48" in artifact.content

    def test_card_has_type_icon(self, rich_knowledge_model: KnowledgeModel) -> None:
        r = ConceptCardRenderer()
        artifact = r.render(rich_knowledge_model)
        assert "svg" in artifact.content  # SVG icon (replaced emoji)
        assert "方法论" in artifact.content  # methodology type present

    def test_render_empty(self) -> None:
        r = ConceptCardRenderer()
        artifact = r.render(KnowledgeModel())
        assert "<!DOCTYPE html>" in artifact.content
        assert "共 <strong>0</strong> 个概念" in artifact.content

    def test_render_single(self, rich_knowledge_model: KnowledgeModel) -> None:
        r = ConceptCardRenderer()
        html = r.render_single(rich_knowledge_model.concepts[0])
        assert "知识管理" in html
        assert "concept-card" in html


# ---------------------------------------------------------------------------
# CardDeckRenderer
# ---------------------------------------------------------------------------

class TestCardDeckRenderer:
    def test_render_deck(self, rich_knowledge_model: KnowledgeModel) -> None:
        r = CardDeckRenderer()
        artifact = r.render(rich_knowledge_model)

        assert "<!DOCTYPE html>" in artifact.content
        assert "sidebar" in artifact.content
        assert "知识管理" in artifact.content
        assert "card-0" in artifact.content  # 锚点
        assert "index-item" in artifact.content

    def test_deck_has_navigation(self, rich_knowledge_model: KnowledgeModel) -> None:
        r = CardDeckRenderer()
        artifact = r.render(rich_knowledge_model)
        assert "📚 目录" in artifact.content
        assert 'href="#card-' in artifact.content

    def test_deck_with_theme(self, rich_knowledge_model: KnowledgeModel) -> None:
        """自定义主题应被接受。"""
        r = CardDeckRenderer(theme="navy")
        artifact = r.render(rich_knowledge_model)
        assert "card-0" in artifact.content

    def test_deck_empty_model(self) -> None:
        """空模型也能渲染（不报错，目录为空）。"""
        model = KnowledgeModel(book_title="空书")
        r = CardDeckRenderer()
        artifact = r.render(model)
        assert "<!DOCTYPE html>" in artifact.content
        assert "空书" in artifact.content
        # 没有概念就没有目录项（用 href 判定，避免 CSS 选择器 .index-item 误命中）
        assert 'href="#card-' not in artifact.content

    def test_deck_metadata(self, rich_knowledge_model: KnowledgeModel) -> None:
        """metadata 包含 card_count。"""
        r = CardDeckRenderer()
        artifact = r.render(rich_knowledge_model)
        assert artifact.metadata["card_count"] == rich_knowledge_model.concept_count


# ---------------------------------------------------------------------------
# InfographicRenderer
# ---------------------------------------------------------------------------

class TestInfographicRenderer:
    def test_render_full(self, rich_knowledge_model: KnowledgeModel) -> None:
        r = InfographicRenderer()
        artifact = r.render(rich_knowledge_model)

        assert "<!DOCTYPE html>" in artifact.content
        assert "知识管理入门" in artifact.content
        assert "poster" in artifact.content
        assert "concept-box" in artifact.content

    def test_has_stats_bar(self, rich_knowledge_model: KnowledgeModel) -> None:
        r = InfographicRenderer()
        artifact = r.render(rich_knowledge_model)
        assert "stats-bar" in artifact.content
        assert "stat-num" in artifact.content
        assert "3" in artifact.content  # 3 concepts

    def test_has_relationships(self, rich_knowledge_model: KnowledgeModel) -> None:
        r = InfographicRenderer()
        artifact = r.render(rich_knowledge_model)
        assert "概念关系网络" in artifact.content
        assert "rel-badge" in artifact.content

    def test_empty_model(self) -> None:
        r = InfographicRenderer()
        artifact = r.render(KnowledgeModel())
        assert "<!DOCTYPE html>" in artifact.content
        assert "暂无概念" in artifact.content


# ---------------------------------------------------------------------------
# AnatomyChartRenderer
# ---------------------------------------------------------------------------

class TestAnatomyChartRenderer:
    def test_render_full(self, rich_knowledge_model: KnowledgeModel) -> None:
        r = AnatomyChartRenderer()
        artifact = r.render(rich_knowledge_model)

        assert "<!DOCTYPE html>" in artifact.content
        assert "知识管理" in artifact.content
        assert "anatomy-card" in artifact.content
        assert "核心特征" in artifact.content
        assert "概念对比" in artifact.content
        assert "应用场景" in artifact.content
        assert "核心洞察" in artifact.content

    def test_has_insight_bar(self, rich_knowledge_model: KnowledgeModel) -> None:
        r = AnatomyChartRenderer()
        artifact = r.render(rich_knowledge_model)
        assert "insight-bar" in artifact.content
        assert "知识不在多，在用" in artifact.content

    def test_has_counterexamples(self, rich_knowledge_model: KnowledgeModel) -> None:
        r = AnatomyChartRenderer()
        artifact = r.render(rich_knowledge_model)
        assert "什么不属于此概念" in artifact.content
        assert "单纯文件存储" in artifact.content

    def test_empty_model(self) -> None:
        r = AnatomyChartRenderer()
        artifact = r.render(KnowledgeModel())
        assert "<!DOCTYPE html>" in artifact.content
        assert "共 0 个" in artifact.content

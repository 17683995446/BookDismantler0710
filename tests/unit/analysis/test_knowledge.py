"""知识模型领域测试。"""

from __future__ import annotations

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


class TestOutlineNode:
    def test_flatten(self) -> None:
        root = OutlineNode(
            title="根",
            children=[
                OutlineNode(title="子1", children=[OutlineNode(title="孙1")]),
                OutlineNode(title="子2"),
            ],
        )
        flat = root.flatten()
        assert len(flat) == 4

    def test_total_descendants(self) -> None:
        node = OutlineNode(
            title="root",
            children=[OutlineNode(title="a"), OutlineNode(title="b")],
        )
        assert node.total_descendants == 2


class TestConcept:
    def test_key(self) -> None:
        c = Concept(name="知识管理")
        assert c.key == "知识管理"

    def test_key_normalizes(self) -> None:
        c1 = Concept(name="  Knowledge Management  ")
        c2 = Concept(name="knowledge management")
        assert c1.key == c2.key


class TestRelationship:
    def test_key_symmetric_undirected(self) -> None:
        """无向关系（supports/contradicts/related-to）A→B 等于 B→A。"""
        r1 = Relationship(source="A", target="B", type=RelationshipType.SUPPORTS)
        r2 = Relationship(source="B", target="A", type=RelationshipType.SUPPORTS)
        assert r1.key == r2.key

    def test_key_directed_not_symmetric(self) -> None:
        """有向关系（is-a/part-of/depends-on）A→B 不等于 B→A。"""
        r1 = Relationship(source="A", target="B", type=RelationshipType.IS_A)
        r2 = Relationship(source="B", target="A", type=RelationshipType.IS_A)
        assert r1.key != r2.key

    def test_key_directed_part_of(self) -> None:
        """part-of 关系保持方向。"""
        r1 = Relationship(source="A", target="B", type=RelationshipType.PART_OF)
        r2 = Relationship(source="B", target="A", type=RelationshipType.PART_OF)
        assert r1.key != r2.key


class TestKnowledgeModel:
    def test_empty(self) -> None:
        km = KnowledgeModel()
        assert km.concept_count == 0
        assert km.relationship_count == 0

    def test_get_concept(self) -> None:
        km = KnowledgeModel(concepts=[Concept(name="测试")])
        found = km.get_concept("测试")
        assert found is not None
        assert found.name == "测试"
        assert km.get_concept("不存在") is None

    def test_get_high_importance(self) -> None:
        km = KnowledgeModel(
            concepts=[
                Concept(name="高", importance=ConceptImportance.HIGH),
                Concept(name="低", importance=ConceptImportance.LOW),
            ]
        )
        high = km.get_high_importance_concepts()
        assert len(high) == 1
        assert high[0].name == "高"

    def test_merge_deduplicates_concepts(self) -> None:
        km1 = KnowledgeModel(concepts=[Concept(name="概念A", definition="定义1")])
        km2 = KnowledgeModel(concepts=[Concept(name="概念A", definition="定义2更长的"), Concept(name="概念B")])
        merged = km1.merge(km2)
        # merge 做简单去重（保留首个出现），字段级合并在 Aggregator
        assert merged.concept_count == 2
        assert merged.concepts[0].name == "概念A"

    def test_merge_deduplicates_relationships(self) -> None:
        km1 = KnowledgeModel(
            relationships=[Relationship(source="A", target="B", type=RelationshipType.SUPPORTS)]
        )
        km2 = KnowledgeModel(
            relationships=[Relationship(source="B", target="A", type=RelationshipType.SUPPORTS)]
        )
        merged = km1.merge(km2)
        assert merged.relationship_count == 1

    def test_serialization_roundtrip(self) -> None:
        km = KnowledgeModel(
            book_title="测试书",
            concepts=[Concept(name="概念", importance=ConceptImportance.HIGH)],
            outline=[OutlineNode(title="章节")],
        )
        json_str = km.model_dump_json()
        restored = KnowledgeModel.model_validate_json(json_str)
        assert restored.book_title == "测试书"
        assert restored.concept_count == 1
        assert restored.concepts[0].importance == ConceptImportance.HIGH


class TestConceptAnatomy:
    def test_creation(self) -> None:
        a = ConceptAnatomy(
            concept="知识管理",
            definition="组织知识的系统方法",
            characteristics=["系统性", "持续性"],
            comparisons=[
                ConceptComparison(concept="信息管理", similarity="都管信息", difference="KM更重应用")
            ],
            applications=["企业知识库", "个人笔记"],
            counterexamples=["单纯的文件存储"],
            insight="知识不在多，在用。",
        )
        assert a.concept == "知识管理"
        assert len(a.characteristics) == 2
        assert a.comparisons[0].concept == "信息管理"

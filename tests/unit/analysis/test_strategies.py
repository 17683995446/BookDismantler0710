"""分析策略单元测试：mock LLM 验证策略逻辑。"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

from book_dismantler.analysis.strategies.anatomy import AnatomyStrategy
from book_dismantler.analysis.strategies.concepts import ConceptStrategy
from book_dismantler.analysis.strategies.outline import OutlineStrategy
from book_dismantler.analysis.strategies.relationships import RelationshipStrategy
from book_dismantler.domain.chunk import TextChunk
from book_dismantler.domain.knowledge import ConceptImportance, RelationshipType
from book_dismantler.llm.base import StructuredResponse, Usage


def make_mock_client(response_data: dict[str, Any] | None) -> MagicMock:
    """构造返回指定数据的 mock LLMClient。"""
    client = MagicMock()
    response = StructuredResponse(
        raw_content="{}",
        parsed=response_data,
        usage=Usage(prompt_tokens=10, completion_tokens=5, total_tokens=15),
        model="mock",
    )
    client.complete.return_value = response
    return client


def make_chunk(text: str = "测试内容", idx: int = 0) -> TextChunk:
    return TextChunk(
        text=text,
        chapter_index=0,
        chapter_title="第一章",
        chunk_index=idx,
        token_estimate=10,
        char_count=len(text),
    )


class TestOutlineStrategy:
    def test_analyze_success(self) -> None:
        data = {
            "nodes": [
                {"title": "第一章", "summary": "概述", "level": 1, "children": []},
                {"title": "第二章", "summary": "深入", "level": 1, "children": [
                    {"title": "2.1", "summary": "子节", "level": 2}
                ]},
            ]
        }
        client = make_mock_client(data)
        strategy = OutlineStrategy(client, book_title="测试书")
        result = strategy.analyze(make_chunk())

        assert result.outline_node_count >= 2
        assert result.outline[0].title == "第一章"

    def test_analyze_empty_response(self) -> None:
        client = make_mock_client(None)
        strategy = OutlineStrategy(client)
        result = strategy.analyze(make_chunk())
        assert result.concept_count == 0
        assert len(result.outline) == 0

    def test_name_and_template(self) -> None:
        client = make_mock_client(None)
        strategy = OutlineStrategy(client)
        assert strategy.name == "outline"
        assert strategy.prompt_template == "outline_extraction.j2"


class TestConceptStrategy:
    def test_analyze_success(self) -> None:
        data = {
            "concepts": [
                {"name": "知识管理", "definition": "管理知识的方法", "type": "方法论",
                 "examples": ["知识库"], "importance": "high"},
                {"name": "SECI模型", "definition": "知识转化模型", "importance": "medium"},
            ]
        }
        client = make_mock_client(data)
        strategy = ConceptStrategy(client, book_title="测试书")
        result = strategy.analyze(make_chunk())

        assert result.concept_count == 2
        assert result.concepts[0].name == "知识管理"
        assert result.concepts[0].importance == ConceptImportance.HIGH
        assert result.concepts[0].source_chapter == "第一章"

    def test_analyze_invalid_importance_falls_back(self) -> None:
        data = {
            "concepts": [
                {"name": "概念", "importance": "invalid_value"}
            ]
        }
        client = make_mock_client(data)
        strategy = ConceptStrategy(client)
        result = strategy.analyze(make_chunk())
        assert result.concepts[0].importance == ConceptImportance.MEDIUM

    def test_analyze_empty_concepts(self) -> None:
        client = make_mock_client({"concepts": []})
        strategy = ConceptStrategy(client)
        result = strategy.analyze(make_chunk())
        assert result.concept_count == 0


class TestRelationshipStrategy:
    def test_analyze_success(self) -> None:
        data = {
            "relationships": [
                {"source": "知识管理", "target": "SECI模型", "type": "part-of",
                 "description": "SECI是KM的一部分", "evidence": "书中提到"},
                {"source": "隐性知识", "target": "显性知识", "type": "contradicts"},
            ]
        }
        client = make_mock_client(data)
        strategy = RelationshipStrategy(client, book_title="测试书")
        result = strategy.analyze(make_chunk())

        assert result.relationship_count == 2
        assert result.relationships[0].type == RelationshipType.PART_OF

    def test_invalid_type_falls_back(self) -> None:
        data = {
            "relationships": [
                {"source": "A", "target": "B", "type": "unknown_type"}
            ]
        }
        client = make_mock_client(data)
        strategy = RelationshipStrategy(client)
        result = strategy.analyze(make_chunk())
        assert result.relationships[0].type == RelationshipType.RELATED_TO

    def test_filters_empty_source_target(self) -> None:
        data = {
            "relationships": [
                {"source": "", "target": "B", "type": "supports"},
                {"source": "A", "target": "B", "type": "supports"},
            ]
        }
        client = make_mock_client(data)
        strategy = RelationshipStrategy(client)
        result = strategy.analyze(make_chunk())
        assert result.relationship_count == 1


class TestAnatomyStrategy:
    def test_analyze_success(self) -> None:
        data = {
            "concept": "知识管理",
            "definition": "系统管理知识的方法论",
            "characteristics": ["系统性", "持续性", "目标导向"],
            "comparisons": [
                {"concept": "信息管理", "similarity": "都处理信息", "difference": "KM重应用"}
            ],
            "applications": ["企业知识库", "学习型组织"],
            "counterexamples": ["单纯文件存储"],
            "insight": "知识不在多，在用",
        }
        client = make_mock_client(data)
        strategy = AnatomyStrategy(client, book_title="测试书", target_concepts=["知识管理"])
        result = strategy.analyze(make_chunk())

        assert len(result.anatomies) == 1
        assert result.anatomies[0].concept == "知识管理"
        assert len(result.anatomies[0].characteristics) == 3
        assert result.anatomies[0].insight == "知识不在多，在用"

    def test_analyze_no_data(self) -> None:
        client = make_mock_client(None)
        strategy = AnatomyStrategy(client)
        result = strategy.analyze(make_chunk())
        assert len(result.anatomies) == 0

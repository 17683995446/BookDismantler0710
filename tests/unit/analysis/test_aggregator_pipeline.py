"""聚合器与流水线测试。"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest

from book_dismantler.analysis.aggregator import Aggregator
from book_dismantler.analysis.pipeline import AnalysisPipeline
from book_dismantler.analysis.strategies import AnalysisStrategy
from book_dismantler.core.exceptions import JobCancelledError
from book_dismantler.domain.chunk import TextChunk
from book_dismantler.domain.document import (
    Chapter,
    Metadata,
    Paragraph,
    ParsedDocument,
    Section,
)
from book_dismantler.domain.knowledge import (
    Concept,
    ConceptAnatomy,
    ConceptImportance,
    KnowledgeModel,
    OutlineNode,
    Relationship,
    RelationshipType,
)


class TestAggregator:
    """聚合器测试。"""

    def test_aggregate_empty(self) -> None:
        agg = Aggregator("书名", "作者")
        result = agg.aggregate([])
        assert result.book_title == "书名"
        assert result.concept_count == 0

    def test_aggregate_concepts_dedup(self) -> None:
        partials = [
            KnowledgeModel(concepts=[
                Concept(name="概念A", definition="短定义", importance=ConceptImportance.LOW),
            ]),
            KnowledgeModel(concepts=[
                Concept(name="概念A", definition="更长的定义内容", importance=ConceptImportance.HIGH),
                Concept(name="概念B", importance=ConceptImportance.MEDIUM),
            ]),
        ]
        agg = Aggregator()
        result = agg.aggregate(partials)
        assert result.concept_count == 2
        # 同名概念应合并并提升重要度
        a = result.get_concept("概念A")
        assert a is not None
        assert a.importance == ConceptImportance.HIGH
        assert "更长" in a.definition

    def test_aggregate_relationships_dedup(self) -> None:
        partials = [
            KnowledgeModel(relationships=[
                Relationship(source="A", target="B", type=RelationshipType.SUPPORTS),
            ]),
            KnowledgeModel(relationships=[
                Relationship(source="B", target="A", type=RelationshipType.SUPPORTS),
                Relationship(source="C", target="D", type=RelationshipType.IS_A),
            ]),
        ]
        agg = Aggregator()
        result = agg.aggregate(partials)
        assert result.relationship_count == 2  # AB去重 + CD

    def test_aggregate_anatomies_dedup(self) -> None:
        partials = [
            KnowledgeModel(anatomies=[
                ConceptAnatomy(concept="知识管理", characteristics=["a", "b"]),
            ]),
            KnowledgeModel(anatomies=[
                ConceptAnatomy(concept="知识管理", characteristics=["a", "b", "c", "d"]),
            ]),
        ]
        agg = Aggregator()
        result = agg.aggregate(partials)
        assert len(result.anatomies) == 1
        # 保留特征更多的
        assert len(result.anatomies[0].characteristics) == 4

    def test_aggregate_metadata(self) -> None:
        partials = [KnowledgeModel(concepts=[Concept(name="x")])]
        agg = Aggregator("书名", "作者")
        result = agg.aggregate(partials)
        assert result.metadata["chunk_count"] == 1
        assert result.metadata["total_concepts_raw"] == 1

    def test_aggregate_idempotent(self) -> None:
        """相同输入两次聚合结果一致。"""
        partials = [
            KnowledgeModel(concepts=[Concept(name="A"), Concept(name="B")]),
            KnowledgeModel(concepts=[Concept(name="A"), Concept(name="C")]),
        ]
        agg = Aggregator()
        r1 = agg.aggregate(partials)
        r2 = agg.aggregate(partials)
        assert r1.concept_count == r2.concept_count


class TestPipeline:
    """流水线测试。"""

    def _make_doc(self) -> ParsedDocument:
        """构造测试文档。"""
        return ParsedDocument(
            metadata=Metadata(title="测试书", author="作者"),
            chapters=[
                Chapter(
                    title="第一章",
                    sections=[
                        Section(paragraphs=[
                            Paragraph(text="知识管理是组织能力的核心。", index=0),
                            Paragraph(text="SECI模型描述了知识转化的过程。", index=1),
                        ])
                    ],
                    index=0,
                ),
            ],
        )

    def test_pipeline_runs_with_mock_strategies(self) -> None:
        """mock 策略的端到端流水线。"""
        doc = self._make_doc()

        # Mock 策略：返回固定知识模型
        class MockStrategy(AnalysisStrategy):
            def __init__(self, client: Any, book_title: str = "") -> None:
                pass

            @property
            def name(self) -> str:
                return "mock"

            @property
            def prompt_template(self) -> str:
                return "outline_extraction.j2"

            def analyze(self, chunk: TextChunk) -> KnowledgeModel:
                return KnowledgeModel(
                    book_title="测试书",
                    concepts=[Concept(name="知识管理", source_chunk=chunk.chunk_index)],
                    outline=[OutlineNode(title=chunk.chapter_title)],
                )

        client = MagicMock()
        pipeline = AnalysisPipeline(
            client=client,
            strategies=[MockStrategy(client)],
            chunk_size=2000,
            chunk_overlap=0,
            max_concurrent=2,
        )

        result = pipeline.run(doc)

        assert result.book_title == "测试书"
        assert result.concept_count >= 1
        assert result.outline_node_count >= 1

    def test_pipeline_progress_callback(self) -> None:
        """进度回调被调用。"""
        doc = self._make_doc()
        progress_calls: list[tuple[int, int, int]] = []

        class MockStrategy(AnalysisStrategy):
            def __init__(self, client: Any, book_title: str = "") -> None:
                pass

            @property
            def name(self) -> str:
                return "mock"

            @property
            def prompt_template(self) -> str:
                return "outline_extraction.j2"

            def analyze(self, chunk: TextChunk) -> KnowledgeModel:
                return KnowledgeModel()

        client = MagicMock()
        pipeline = AnalysisPipeline(
            client=client,
            strategies=[MockStrategy(client)],
            chunk_size=2000,
            chunk_overlap=0,
        )

        pipeline.run(doc, on_progress=lambda c, t, i: progress_calls.append((c, t, i)))
        assert len(progress_calls) >= 1
        # 最后一次 completed == total
        assert progress_calls[-1][0] == progress_calls[-1][1]

    def test_pipeline_empty_document(self) -> None:
        """空文档返回空知识模型。"""
        doc = ParsedDocument(metadata=Metadata(title="空"), chapters=[])
        client = MagicMock()

        class MockStrategy(AnalysisStrategy):
            def __init__(self, client: Any, book_title: str = "") -> None:
                pass

            @property
            def name(self) -> str:
                return "mock"

            @property
            def prompt_template(self) -> str:
                return "outline_extraction.j2"

            def analyze(self, chunk: TextChunk) -> KnowledgeModel:
                return KnowledgeModel()

        pipeline = AnalysisPipeline(
            client=client,
            strategies=[MockStrategy(client)],
        )
        result = pipeline.run(doc)
        assert result.concept_count == 0
        assert result.book_title == "空"

    def test_pipeline_strategy_failure_does_not_crash(self) -> None:
        """单个策略失败不影响整体。"""
        doc = self._make_doc()

        class FailingStrategy(AnalysisStrategy):
            def __init__(self, client: Any, book_title: str = "") -> None:
                pass

            @property
            def name(self) -> str:
                return "failing"

            @property
            def prompt_template(self) -> str:
                return "outline_extraction.j2"

            def analyze(self, chunk: TextChunk) -> KnowledgeModel:
                raise RuntimeError("策略故意失败")

        class GoodStrategy(AnalysisStrategy):
            def __init__(self, client: Any, book_title: str = "") -> None:
                pass

            @property
            def name(self) -> str:
                return "good"

            @property
            def prompt_template(self) -> str:
                return "outline_extraction.j2"

            def analyze(self, chunk: TextChunk) -> KnowledgeModel:
                return KnowledgeModel(concepts=[Concept(name="成功概念")])

        client = MagicMock()
        pipeline = AnalysisPipeline(
            client=client,
            strategies=[FailingStrategy(client), GoodStrategy(client)],
            chunk_size=2000,
            chunk_overlap=0,
        )
        result = pipeline.run(doc)
        # 失败策略不影响成功策略
        assert result.concept_count >= 1


class TestPipelineCancel:
    """流水线取消机制测试（Stage 3 引入的 cancel_check）。"""

    def _make_multi_chunk_doc(self) -> ParsedDocument:
        """构造足以分出多块的文档（多段落，使 Chunker 能切分）。"""
        # 每个段落约 100 tokens，chunk_size=500 → 每 5 段一块
        para_text = "知识管理是组织能力的核心要素，涉及知识的获取、分享与应用。"
        paragraphs = [
            Paragraph(text=para_text + f" 编号{i}。", index=i)
            for i in range(20)
        ]
        return ParsedDocument(
            metadata=Metadata(title="多块书", author="作者"),
            chapters=[
                Chapter(
                    title="第一章",
                    sections=[
                        Section(paragraphs=paragraphs)
                    ],
                    index=0,
                ),
            ],
        )

    def _make_slow_strategy(self) -> type[AnalysisStrategy]:
        """创建一个带 sleep 的策略，确保有 chunk 在 cancel 时尚未完成。"""

        import time

        class SlowStrategy(AnalysisStrategy):
            def __init__(self, client: Any, book_title: str = "") -> None:
                pass

            @property
            def name(self) -> str:
                return "slow"

            @property
            def prompt_template(self) -> str:
                return "outline_extraction.j2"

            def analyze(self, chunk: TextChunk) -> KnowledgeModel:
                time.sleep(0.1)
                return KnowledgeModel(
                    concepts=[Concept(name=f"概念{chunk.chunk_index}", source_chunk=chunk.chunk_index)]
                )

        return SlowStrategy

    def test_cancel_raises_job_cancelled_error(self) -> None:
        """cancel_check 返回 True 时抛出 JobCancelledError。"""
        doc = self._make_multi_chunk_doc()
        cancel_flag = {"cancelled": False}

        def cancel_check() -> bool:
            return cancel_flag["cancelled"]

        slow_strategy_cls = self._make_slow_strategy()
        client = MagicMock()
        pipeline = AnalysisPipeline(
            client=client,
            strategies=[slow_strategy_cls(client)],
            chunk_size=500,
            chunk_overlap=0,
            max_concurrent=2,
        )

        # 在第一个进度回调后触发取消
        def on_progress(completed: int, total: int, idx: int) -> None:
            if completed >= 1:
                cancel_flag["cancelled"] = True

        with pytest.raises(JobCancelledError, match="取消"):
            pipeline.run(doc, on_progress=on_progress, cancel_check=cancel_check)

    def test_cancel_without_check_does_not_raise(self) -> None:
        """不传 cancel_check 时正常运行（向后兼容）。"""
        doc = self._make_multi_chunk_doc()

        slow_strategy_cls = self._make_slow_strategy()
        client = MagicMock()
        pipeline = AnalysisPipeline(
            client=client,
            strategies=[slow_strategy_cls(client)],
            chunk_size=500,
            chunk_overlap=0,
            max_concurrent=2,
        )

        result = pipeline.run(doc)
        assert result.concept_count >= 1

    def test_cancel_never_triggered_completes_normally(self) -> None:
        """cancel_check 始终返回 False 时正常完成。"""
        doc = self._make_multi_chunk_doc()

        slow_strategy_cls = self._make_slow_strategy()
        client = MagicMock()
        pipeline = AnalysisPipeline(
            client=client,
            strategies=[slow_strategy_cls(client)],
            chunk_size=500,
            chunk_overlap=0,
            max_concurrent=2,
        )

        result = pipeline.run(doc, cancel_check=lambda: False)
        assert result.concept_count >= 1

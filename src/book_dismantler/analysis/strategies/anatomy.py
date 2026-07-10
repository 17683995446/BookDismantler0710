"""概念多维解剖策略。"""

from __future__ import annotations

from typing import Any

from book_dismantler.analysis.strategies import AnalysisStrategy
from book_dismantler.core.logging import get_logger
from book_dismantler.domain.chunk import TextChunk
from book_dismantler.domain.knowledge import (
    ConceptAnatomy,
    ConceptComparison,
    KnowledgeModel,
)

logger = get_logger("analysis.anatomy")


class AnatomyStrategy(AnalysisStrategy):
    """概念多维解剖策略。

    对指定概念从定义、特征、对比、应用、反例、洞察六个维度深度剖析。
    """

    def __init__(
        self,
        client: Any,
        book_title: str = "",
        target_concepts: list[str] | None = None,
    ) -> None:
        super().__init__(client, book_title)
        self.target_concepts = target_concepts or []

    @property
    def name(self) -> str:
        return "anatomy"

    @property
    def prompt_template(self) -> str:
        return "concept_anatomy.j2"

    @property
    def response_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "concept": {"type": "string"},
                "definition": {"type": "string"},
                "characteristics": {"type": "array", "items": {"type": "string"}},
                "comparisons": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "concept": {"type": "string"},
                            "similarity": {"type": "string"},
                            "difference": {"type": "string"},
                        },
                    },
                },
                "applications": {"type": "array", "items": {"type": "string"}},
                "counterexamples": {"type": "array", "items": {"type": "string"}},
                "insight": {"type": "string"},
            },
            "required": ["concept"],
        }

    def analyze(self, chunk: TextChunk) -> KnowledgeModel:
        """对文本块中的核心概念进行多维解剖。"""
        concept_name = self.target_concepts[0] if self.target_concepts else ""

        prompt = self._render_prompt(
            concept=concept_name,
            content=chunk.text,
        )

        data = self._call_llm(prompt)

        if not data:
            logger.warning("概念解剖未返回有效数据")
            return KnowledgeModel(book_title=self.book_title)

        anatomy = self._parse_anatomy(data)
        if anatomy:
            return KnowledgeModel(
                book_title=self.book_title,
                anatomies=[anatomy],
            )
        return KnowledgeModel(book_title=self.book_title)

    def _parse_anatomy(self, data: dict[str, Any]) -> ConceptAnatomy | None:
        """将原始 dict 解析为 ConceptAnatomy。"""
        try:
            comparisons = [
                ConceptComparison(
                    concept=c.get("concept", ""),
                    similarity=c.get("similarity", ""),
                    difference=c.get("difference", ""),
                )
                for c in data.get("comparisons", [])
            ]
            return ConceptAnatomy(
                concept=data.get("concept", ""),
                definition=data.get("definition", ""),
                characteristics=data.get("characteristics", []),
                comparisons=comparisons,
                applications=data.get("applications", []),
                counterexamples=data.get("counterexamples", []),
                insight=data.get("insight", ""),
            )
        except Exception as e:
            logger.warning("解剖解析失败: %s", e)
            return None

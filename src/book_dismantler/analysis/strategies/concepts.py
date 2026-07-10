"""概念抽取策略。"""

from __future__ import annotations

from typing import Any

from book_dismantler.analysis.strategies import AnalysisStrategy
from book_dismantler.core.logging import get_logger
from book_dismantler.domain.chunk import TextChunk
from book_dismantler.domain.knowledge import (
    Concept,
    ConceptImportance,
    KnowledgeModel,
)

logger = get_logger("analysis.concepts")


class ConceptStrategy(AnalysisStrategy):
    """概念抽取策略。"""

    @property
    def name(self) -> str:
        return "concepts"

    @property
    def prompt_template(self) -> str:
        return "concept_extraction.j2"

    @property
    def response_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "concepts": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string"},
                            "definition": {"type": "string"},
                            "type": {"type": "string"},
                            "examples": {"type": "array", "items": {"type": "string"}},
                            "importance": {
                                "type": "string",
                                "enum": ["high", "medium", "low"],
                            },
                        },
                        "required": ["name"],
                    },
                }
            },
            "required": ["concepts"],
        }

    def analyze(self, chunk: TextChunk) -> KnowledgeModel:
        """从文本块中抽取核心概念。"""
        prompt = self._render_prompt(
            book_title=self.book_title,
            chapter_title=chunk.chapter_title,
            content=chunk.text,
        )

        data = self._call_llm(prompt)

        if not data or "concepts" not in data:
            logger.warning("概念抽取未返回有效数据: chunk #%d", chunk.chunk_index)
            return KnowledgeModel(book_title=self.book_title)

        concepts = self._parse_concepts(data["concepts"], chunk)
        return KnowledgeModel(
            book_title=self.book_title,
            concepts=concepts,
        )

    def _parse_concepts(
        self, raw: list[dict[str, Any]], chunk: TextChunk
    ) -> list[Concept]:
        """将原始 dict 列表解析为 Concept。"""
        result: list[Concept] = []
        for item in raw:
            try:
                importance_str = item.get("importance", "medium").lower()
                try:
                    importance = ConceptImportance(importance_str)
                except ValueError:
                    importance = ConceptImportance.MEDIUM

                concept = Concept(
                    name=item.get("name", ""),
                    definition=item.get("definition", ""),
                    type=item.get("type", "术语"),
                    examples=item.get("examples", []),
                    importance=importance,
                    source_chapter=chunk.chapter_title,
                    source_chunk=chunk.chunk_index,
                )
                if concept.name:
                    result.append(concept)
            except Exception as e:
                logger.warning("概念解析失败: %s", e)
        return result

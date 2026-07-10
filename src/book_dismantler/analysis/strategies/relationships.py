"""关系挖掘策略。"""

from __future__ import annotations

from typing import Any

from book_dismantler.analysis.strategies import AnalysisStrategy
from book_dismantler.core.logging import get_logger
from book_dismantler.domain.chunk import TextChunk
from book_dismantler.domain.knowledge import KnowledgeModel, Relationship, RelationshipType

logger = get_logger("analysis.relationships")


class RelationshipStrategy(AnalysisStrategy):
    """概念间关系挖掘策略。"""

    def __init__(
        self,
        client: Any,
        book_title: str = "",
        known_concepts: list[str] | None = None,
    ) -> None:
        super().__init__(client, book_title)
        self.known_concepts = known_concepts or []

    @property
    def name(self) -> str:
        return "relationships"

    @property
    def prompt_template(self) -> str:
        return "relationship_mining.j2"

    @property
    def response_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "relationships": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "source": {"type": "string"},
                            "target": {"type": "string"},
                            "type": {
                                "type": "string",
                                "enum": [
                                    "is-a", "part-of", "depends-on",
                                    "contradicts", "supports", "related-to",
                                ],
                            },
                            "description": {"type": "string"},
                            "evidence": {"type": "string"},
                        },
                        "required": ["source", "target"],
                    },
                }
            },
            "required": ["relationships"],
        }

    def analyze(self, chunk: TextChunk) -> KnowledgeModel:
        """挖掘文本块中概念间的关系。"""
        concepts_str = "、".join(self.known_concepts) if self.known_concepts else ""
        prompt = self._render_prompt(
            concepts=concepts_str,
            content=chunk.text,
        )

        data = self._call_llm(prompt)

        if not data or "relationships" not in data:
            logger.warning("关系挖掘未返回有效数据: chunk #%d", chunk.chunk_index)
            return KnowledgeModel(book_title=self.book_title)

        relationships = self._parse_relationships(data["relationships"])
        return KnowledgeModel(
            book_title=self.book_title,
            relationships=relationships,
        )

    def _parse_relationships(self, raw: list[dict[str, Any]]) -> list[Relationship]:
        """将原始 dict 列表解析为 Relationship。"""
        result: list[Relationship] = []
        for item in raw:
            try:
                type_str = item.get("type", "related-to").lower()
                try:
                    rel_type = RelationshipType(type_str)
                except ValueError:
                    rel_type = RelationshipType.RELATED_TO

                rel = Relationship(
                    source=item.get("source", ""),
                    target=item.get("target", ""),
                    type=rel_type,
                    description=item.get("description", ""),
                    evidence=item.get("evidence", ""),
                )
                if rel.source and rel.target:
                    result.append(rel)
            except Exception as e:
                logger.warning("关系解析失败: %s", e)
        return result

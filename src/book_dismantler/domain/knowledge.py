"""知识模型：AI 拆书分析的核心输出契约。

包含大纲、概念、关系、概念解剖四种知识结构，
是分析层→渲染层的统一数据契约。
"""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class ConceptImportance(str, Enum):
    """概念重要程度。"""

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"

    @property
    def icon(self) -> str:
        """重要度对应的 emoji 图标（🔴/🟡/🟢）。"""
        if self is ConceptImportance.HIGH:
            return "🔴"
        if self is ConceptImportance.MEDIUM:
            return "🟡"
        return "🟢"

    @property
    def label(self) -> str:
        """重要度对应的中文标签（核心/重要/参考）。"""
        if self is ConceptImportance.HIGH:
            return "核心"
        if self is ConceptImportance.MEDIUM:
            return "重要"
        return "参考"


class RelationshipType(str, Enum):
    """概念间关系类型。"""

    IS_A = "is-a"
    PART_OF = "part-of"
    DEPENDS_ON = "depends-on"
    CONTRADICTS = "contradicts"
    SUPPORTS = "supports"
    RELATED_TO = "related-to"

    @property
    def is_directed(self) -> bool:
        """是否有向关系（A→B ≠ B→A）。"""
        return self in (
            RelationshipType.IS_A,
            RelationshipType.PART_OF,
            RelationshipType.DEPENDS_ON,
        )

    @property
    def label(self) -> str:
        """关系类型的中文标签。"""
        labels = {
            RelationshipType.IS_A: "属于",
            RelationshipType.PART_OF: "包含",
            RelationshipType.DEPENDS_ON: "依赖",
            RelationshipType.CONTRADICTS: "对立",
            RelationshipType.SUPPORTS: "支持",
            RelationshipType.RELATED_TO: "相关",
        }
        return labels[self]


class OutlineNode(BaseModel):
    """大纲节点：层级树结构。"""

    title: str = Field(..., description="节点标题")
    summary: str = Field(default="", description="一句话摘要")
    level: int = Field(default=1, ge=1, description="层级深度")
    children: list[OutlineNode] = Field(default_factory=list)

    def flatten(self) -> list[OutlineNode]:
        """展平为列表（深度优先）。"""
        result = [self]
        for child in self.children:
            result.extend(child.flatten())
        return result

    @property
    def total_descendants(self) -> int:
        """后代节点总数。"""
        return sum(c.total_descendants + 1 for c in self.children)


class Concept(BaseModel):
    """概念：知识的最小单元。"""

    name: str = Field(..., description="概念名称")
    definition: str = Field(default="", description="概念定义")
    type: str = Field(default="术语", description="概念类型")
    examples: list[str] = Field(default_factory=list, description="示例列表")
    importance: ConceptImportance = Field(
        default=ConceptImportance.MEDIUM, description="重要程度"
    )
    source_chapter: str = Field(default="", description="来源章节")
    source_chunk: int = Field(default=-1, ge=-1, description="来源块序号")

    @property
    def key(self) -> str:
        """去重用的标准化键（小写去空格）。"""
        return self.name.strip().lower()


class ConceptComparison(BaseModel):
    """概念对比项。"""

    concept: str = Field(..., description="对比概念名称")
    similarity: str = Field(default="", description="相同点")
    difference: str = Field(default="", description="不同点")


class ConceptAnatomy(BaseModel):
    """概念多维解剖。"""

    concept: str = Field(..., description="概念名称")
    definition: str = Field(default="", description="精确定义")
    characteristics: list[str] = Field(default_factory=list, description="核心特征")
    comparisons: list[ConceptComparison] = Field(
        default_factory=list, description="与相近概念对比"
    )
    applications: list[str] = Field(default_factory=list, description="应用场景")
    counterexamples: list[str] = Field(
        default_factory=list, description="反例（什么不属于此概念）"
    )
    insight: str = Field(default="", description="一句话核心洞察")


class Relationship(BaseModel):
    """概念间关系。"""

    source: str = Field(..., description="源概念")
    target: str = Field(..., description="目标概念")
    type: RelationshipType = Field(
        default=RelationshipType.RELATED_TO, description="关系类型"
    )
    description: str = Field(default="", description="关系描述")
    evidence: str = Field(default="", description="文本依据")

    @property
    def key(self) -> str:
        """去重键。

        有向关系（is-a/part-of/depends-on）保持方向敏感：
        A→B 与 B→A 视为不同关系。
        无向关系（contradicts/supports/related-to）忽略方向：
        A→B 与 B→A 视为同一关系。
        """
        s = self.source.strip().lower()
        t = self.target.strip().lower()
        if self.type.is_directed:
            return f"{s}|{self.type.value}|{t}"
        pair = sorted([s, t])
        return f"{pair[0]}|{self.type.value}|{pair[1]}"


class KnowledgeModel(BaseModel):
    """知识模型：AI 拆书的核心输出。

    汇聚大纲、概念、关系、概念解剖四种知识结构，
    是分析层→渲染层的统一契约。
    """

    book_title: str = Field(default="", description="书名")
    book_author: str = Field(default="", description="作者")
    outline: list[OutlineNode] = Field(
        default_factory=list, description="结构大纲"
    )
    concepts: list[Concept] = Field(
        default_factory=list, description="概念列表"
    )
    relationships: list[Relationship] = Field(
        default_factory=list, description="概念关系"
    )
    anatomies: list[ConceptAnatomy] = Field(
        default_factory=list, description="概念解剖"
    )
    summary: str = Field(default="", description="全书总结")
    metadata: dict[str, Any] = Field(
        default_factory=dict, description="附加元信息"
    )

    @property
    def concept_count(self) -> int:
        return len(self.concepts)

    @property
    def relationship_count(self) -> int:
        return len(self.relationships)

    @property
    def outline_node_count(self) -> int:
        return sum(node.total_descendants + 1 for node in self.outline)

    def get_concept(self, name: str) -> Concept | None:
        """按名称查找概念。"""
        key = name.strip().lower()
        for c in self.concepts:
            if c.key == key:
                return c
        return None

    def get_high_importance_concepts(self) -> list[Concept]:
        """获取高重要度概念。"""
        return [c for c in self.concepts if c.importance == ConceptImportance.HIGH]

    def merge(self, other: KnowledgeModel) -> KnowledgeModel:
        """合并另一个知识模型（用于跨 chunk 聚合）。

        Returns:
            合并后的新 KnowledgeModel。
        """
        return KnowledgeModel(
            book_title=self.book_title or other.book_title,
            book_author=self.book_author or other.book_author,
            outline=self.outline + other.outline,
            concepts=self._merge_concepts(other.concepts),
            relationships=self._merge_relationships(other.relationships),
            anatomies=self.anatomies + other.anatomies,
            summary=self.summary or other.summary,
            metadata={**self.metadata, **other.metadata},
        )

    def _merge_concepts(self, others: list[Concept]) -> list[Concept]:
        """合并概念列表，去重保留首个。"""
        seen: set[str] = set()
        merged: list[Concept] = []
        for c in self.concepts + others:
            if c.key not in seen:
                seen.add(c.key)
                merged.append(c)
        return merged

    def _merge_relationships(self, others: list[Relationship]) -> list[Relationship]:
        """合并关系列表，去重。"""
        seen: set[str] = set()
        merged: list[Relationship] = []
        for r in self.relationships + others:
            if r.key not in seen:
                seen.add(r.key)
                merged.append(r)
        return merged

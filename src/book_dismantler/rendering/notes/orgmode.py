"""org-mode 笔记渲染器。

输出 Emacs org-mode 格式，支持层级标题、属性、链接。
"""

from __future__ import annotations

from book_dismantler.domain.knowledge import (
    Concept,
    KnowledgeModel,
    OutlineNode,
)
from book_dismantler.rendering.base import ArtifactType, RenderedArtifact, Renderer


class OrgModeRenderer(Renderer):
    """org-mode 结构化笔记渲染器。"""

    @property
    def artifact_type(self) -> ArtifactType:
        return ArtifactType.ORG_NOTES

    def render(self, model: KnowledgeModel) -> RenderedArtifact:
        """渲染知识模型为 org-mode 笔记。"""
        lines: list[str] = []

        title = model.book_title or "拆书笔记"
        lines.append(f"#+TITLE: {title}")
        if model.book_author:
            lines.append(f"#+AUTHOR: {model.book_author}")
        lines.append("#+OPTIONS: toc:2 num:t")
        lines.append("")

        # 全书总结
        if model.summary:
            lines.append("* 全书总结")
            lines.append(f"{model.summary}\n")

        # 结构大纲
        if model.outline:
            lines.append("* 结构大纲")
            for node in model.outline:
                lines.extend(self._render_outline_node(node, 1))
            lines.append("")

        # 核心概念
        if model.concepts:
            lines.append("* 核心概念")
            for concept in model.concepts:
                lines.extend(self._render_concept(concept))
            lines.append("")

        # 概念关系
        if model.relationships:
            lines.append("* 概念关系")
            for rel in model.relationships:
                lines.append(
                    f"  - {rel.source} [[{rel.type.value}]]-> {rel.target}: {rel.description}"
                )
            lines.append("")

        # 概念解剖
        if model.anatomies:
            lines.append("* 概念深度解剖")
            for anatomy in model.anatomies:
                lines.append(f"** {anatomy.concept}")
                if anatomy.definition:
                    lines.append(f"   定义：{anatomy.definition}")
                if anatomy.characteristics:
                    lines.append("   特征：")
                    for char in anatomy.characteristics:
                        lines.append(f"   - {char}")
                if anatomy.insight:
                    lines.append("   #+BEGIN_QUOTE")
                    lines.append(f"   {anatomy.insight}")
                    lines.append("   #+END_QUOTE")
                lines.append("")

        content = "\n".join(lines)
        return RenderedArtifact(
            artifact_type=self.artifact_type,
            content=content,
            title=title,
        )

    def _render_outline_node(self, node: OutlineNode, depth: int = 1) -> list[str]:
        """渲染大纲节点为 org 标题。"""
        lines: list[str] = []
        stars = "*" * min(depth + 1, 6)
        lines.append(f"{stars} {node.title}")
        if node.summary:
            lines.append(f"  {node.summary}")
        lines.append("  :PROPERTIES:")
        lines.append(f"  :LEVEL: {node.level}")
        lines.append("  :END:")
        lines.append("")
        for child in node.children:
            lines.extend(self._render_outline_node(child, depth + 1))
        return lines

    def _render_concept(self, concept: Concept) -> list[str]:
        """渲染单个概念。"""
        lines: list[str] = []
        lines.append(f"** {concept.name}")
        lines.append("   :PROPERTIES:")
        lines.append(f"   :IMPORTANCE: {concept.importance.value}")
        lines.append(f"   :TYPE: {concept.type}")
        if concept.source_chapter:
            lines.append(f"   :SOURCE: {concept.source_chapter}")
        lines.append("   :END:")
        if concept.definition:
            lines.append(f"   {concept.definition}")
        if concept.examples:
            lines.append("   示例：")
            for ex in concept.examples:
                lines.append(f"   - {ex}")
        lines.append("")
        return lines

"""海报式信息图渲染器。

将全书知识总览渲染为单页大图，
包含书名、核心概念矩阵、关系网络、统计信息。
"""

from __future__ import annotations

from book_dismantler.domain.knowledge import (
    Concept,
    ConceptImportance,
    KnowledgeModel,
    RelationshipType,
)
from book_dismantler.rendering.base import ArtifactType, RenderedArtifact, Renderer


class InfographicRenderer(Renderer):
    """海报式信息图渲染器。

    输出单页 HTML 海报，信息密集、视觉层次清晰。
    """

    @property
    def artifact_type(self) -> ArtifactType:
        return ArtifactType.INFOGRAPHIC

    def render(self, model: KnowledgeModel) -> RenderedArtifact:
        """渲染知识模型为海报式信息图。"""
        title = model.book_title or "知识总览"
        author = model.book_author or ""

        # 核心概念矩阵
        concepts_html = self._render_concepts_grid(model.concepts)

        # 关系网络摘要
        relationships_html = self._render_relationships_summary(model)

        # 统计信息
        stats_html = self._render_stats(model)

        html = self._wrap_html(title, author, concepts_html, relationships_html, stats_html)

        return RenderedArtifact(
            artifact_type=self.artifact_type,
            content=html,
            title=title,
            metadata={
                "concept_count": model.concept_count,
                "relationship_count": model.relationship_count,
            },
        )

    def _render_concepts_grid(self, concepts: list[Concept]) -> str:
        """渲染核心概念矩阵。"""
        if not concepts:
            return '<p class="empty">暂无概念</p>'

        cards = []
        for concept in concepts[:12]:  # 最多展示12个
            importance_class = {
                ConceptImportance.HIGH: "high",
                ConceptImportance.MEDIUM: "medium",
                ConceptImportance.LOW: "low",
            }.get(concept.importance, "medium")

            def_text = concept.definition
            if len(def_text) > 60:
                def_text = def_text[:60] + "..."
            cards.append(f"""
            <div class="concept-box {importance_class}">
                <div class="concept-name">{concept.name}</div>
                <div class="concept-def">{def_text}</div>
                <div class="concept-type">{concept.type}</div>
            </div>""")

        return f'<div class="concepts-grid">{"".join(cards)}</div>'

    def _render_relationships_summary(self, model: KnowledgeModel) -> str:
        """渲染关系网络摘要。"""
        if not model.relationships:
            return ""

        # 按关系类型分组统计
        type_counts: dict[RelationshipType, int] = {}
        for rel in model.relationships:
            type_counts[rel.type] = type_counts.get(rel.type, 0) + 1

        badges = []
        for rel_type, count in type_counts.items():
            badges.append(
                f'<span class="rel-badge">{rel_type.label}: {count}</span>'
            )

        # 前5条关系
        top_rels = model.relationships[:5]
        rel_items = []
        for rel in top_rels:
            rel_items.append(
                f'<div class="rel-item">'
                f'<span class="rel-source">{rel.source}</span>'
                f'<span class="rel-arrow">{rel.type.value}</span>'
                f'<span class="rel-target">{rel.target}</span>'
                f'</div>'
            )

        return f"""
        <div class="relationships-section">
            <h3>🔗 概念关系网络</h3>
            <div class="rel-badges">{''.join(badges)}</div>
            <div class="rel-list">{''.join(rel_items)}</div>
        </div>"""

    def _render_stats(self, model: KnowledgeModel) -> str:
        """渲染统计信息。"""
        return f"""
        <div class="stats-bar">
            <div class="stat-item">
                <div class="stat-num">{model.concept_count}</div>
                <div class="stat-label">概念</div>
            </div>
            <div class="stat-item">
                <div class="stat-num">{model.relationship_count}</div>
                <div class="stat-label">关系</div>
            </div>
            <div class="stat-item">
                <div class="stat-num">{model.outline_node_count}</div>
                <div class="stat-label">大纲节点</div>
            </div>
            <div class="stat-item">
                <div class="stat-num">{len(model.anatomies)}</div>
                <div class="stat-label">深度解剖</div>
            </div>
        </div>"""

    def _wrap_html(
        self,
        title: str,
        author: str,
        concepts_html: str,
        relationships_html: str,
        stats_html: str,
    ) -> str:
        """包裹为完整海报 HTML。"""
        author_line = f'<div class="author">作者：{author}</div>' if author else ""
        return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title} - 信息图</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: "Noto Sans SC", "Microsoft YaHei", sans-serif;
            background: #f0ebe4;
        }}
        .poster {{
            max-width: 1200px;
            margin: 0 auto;
            padding: 40px;
            background: #f5f1ec;
        }}
        .poster-header {{
            text-align: center;
            padding: 40px 0;
            border-bottom: 3px solid #1a7a6d;
            margin-bottom: 32px;
        }}
        .poster-header h1 {{
            font-size: 42px;
            color: #1a7a6d;
            font-weight: 900;
        }}
        .author {{
            color: #666;
            font-size: 16px;
            margin-top: 8px;
        }}
        .section-title {{
            font-size: 24px;
            color: #1a7a6d;
            margin: 32px 0 16px;
            font-weight: 700;
            border-left: 4px solid #e8713a;
            padding-left: 12px;
        }}
        .concepts-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(260px, 1fr));
            gap: 16px;
        }}
        .concept-box {{
            padding: 16px;
            border-radius: 12px;
            background: white;
            border-left: 4px solid;
        }}
        .concept-box.high {{ border-color: #e11d48; }}
        .concept-box.medium {{ border-color: #d97706; }}
        .concept-box.low {{ border-color: #059669; }}
        .concept-name {{
            font-size: 18px;
            font-weight: 700;
            color: #1a1a1a;
            margin-bottom: 8px;
        }}
        .concept-def {{
            font-size: 14px;
            color: #555;
            line-height: 1.5;
            margin-bottom: 8px;
        }}
        .concept-type {{
            font-size: 12px;
            color: #888;
            text-transform: uppercase;
        }}
        .relationships-section {{
            background: #1a1a1a;
            color: white;
            padding: 24px;
            border-radius: 16px;
            margin: 32px 0;
        }}
        .relationships-section h3 {{
            font-size: 20px;
            margin-bottom: 16px;
        }}
        .rel-badges {{
            display: flex;
            gap: 12px;
            flex-wrap: wrap;
            margin-bottom: 16px;
        }}
        .rel-badge {{
            background: #1a7a6d;
            padding: 4px 12px;
            border-radius: 12px;
            font-size: 13px;
        }}
        .rel-list {{
            display: flex;
            flex-direction: column;
            gap: 8px;
        }}
        .rel-item {{
            display: flex;
            align-items: center;
            gap: 8px;
            font-size: 14px;
        }}
        .rel-source {{ color: #5ee6d0; }}
        .rel-arrow {{
            color: #e8713a;
            font-family: monospace;
            font-size: 12px;
        }}
        .rel-target {{ color: #fff; }}
        .stats-bar {{
            display: flex;
            justify-content: space-around;
            background: #145f54;
            padding: 24px;
            border-radius: 16px;
            margin-top: 32px;
        }}
        .stat-item {{
            text-align: center;
        }}
        .stat-num {{
            font-size: 36px;
            font-weight: 900;
            color: #5ee6d0;
        }}
        .stat-label {{
            font-size: 14px;
            color: #c5e8e0;
            margin-top: 4px;
        }}
        .empty {{ color: #999; text-align: center; padding: 32px; }}
    </style>
</head>
<body>
    <div class="poster">
        <div class="poster-header">
            <h1>{title}</h1>
            {author_line}
        </div>
        <div class="section-title">🧠 核心概念矩阵</div>
        {concepts_html}
        {relationships_html}
        {stats_html}
    </div>
</body>
</html>"""

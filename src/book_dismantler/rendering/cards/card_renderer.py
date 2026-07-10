"""概念卡片渲染器。

为每个概念生成高颜值的 HTML 卡片，支持主题色、图标、金句。
卡片可单独导出或组合为卡片组。
"""

from __future__ import annotations

from book_dismantler.domain.knowledge import Concept, ConceptImportance, KnowledgeModel
from book_dismantler.rendering.base import ArtifactType, RenderedArtifact, Renderer

# ── 精致主题色方案 ──────────────────────────────────────────────
# 每个主题包含渐变起止色、浅色背景、边框色
THEMES = {
    "blue": {
        "from": "#3b82f6",
        "to": "#2563eb",
        "light": "#eff6ff",
        "border": "#bfdbfe",
        "tint": "rgba(59,130,246,0.08)",
    },
    "green": {
        "from": "#10b981",
        "to": "#059669",
        "light": "#ecfdf5",
        "border": "#a7f3d0",
        "tint": "rgba(16,185,129,0.08)",
    },
    "orange": {
        "from": "#f59e0b",
        "to": "#d97706",
        "light": "#fffbeb",
        "border": "#fde68a",
        "tint": "rgba(245,158,11,0.08)",
    },
    "red": {
        "from": "#f43f5e",
        "to": "#e11d48",
        "light": "#fff1f2",
        "border": "#fecdd3",
        "tint": "rgba(244,63,94,0.08)",
    },
    "purple": {
        "from": "#8b5cf6",
        "to": "#7c3aed",
        "light": "#f5f3ff",
        "border": "#ddd6fe",
        "tint": "rgba(139,92,246,0.08)",
    },
    "teal": {
        "from": "#06b6d4",
        "to": "#0891b2",
        "light": "#ecfeff",
        "border": "#a5f3fc",
        "tint": "rgba(6,182,212,0.08)",
    },
}

# ── 概念类型 → SVG 图标 ─────────────────────────────────────────
# 使用内联 SVG 替代 emoji，确保在任何环境下都能正确渲染
TYPE_ICONS: dict[str, str] = {
    "方法论": (
        '<svg width="20" height="20" viewBox="0 0 24 24" fill="none">'
        '<path d="M10 3h4v3a2 2 0 002 2h1v4h-1a2 2 0 00-2 2v3h-4v-3'
        'a2 2 0 00-2-2H8V8h1a2 2 0 002-2V3z" fill="currentColor"/>'
        '<path d="M6 17h4v4H6zM14 17h4v4h-4z" fill="currentColor" opacity=".5"/>'
        "</svg>"
    ),
    "术语": (
        '<svg width="20" height="20" viewBox="0 0 24 24" fill="none">'
        '<path d="M5 3h14a1 1 0 011 1v16l-8-3.5L4 20V4a1 1 0 011-1z"'
        ' fill="currentColor"/>'
        "</svg>"
    ),
    "模型": (
        '<svg width="20" height="20" viewBox="0 0 24 24" fill="none">'
        '<path d="M12 2l9 5v10l-9 5-9-5V7l9-5z" stroke="currentColor"'
        ' stroke-width="2" stroke-linejoin="round"/>'
        '<path d="M12 2v20M3 7l9 5 9-5" stroke="currentColor"'
        ' stroke-width="1.5" opacity=".5"/>'
        "</svg>"
    ),
    "原则": (
        '<svg width="20" height="20" viewBox="0 0 24 24" fill="none">'
        '<path d="M12 3v18M5 7h14M7 7l-3 6a3 3 0 006 0L7 7zM17 7l-3 6'
        'a3 3 0 006 0l-3-6z" stroke="currentColor" stroke-width="2"'
        ' stroke-linecap="round" stroke-linejoin="round"/>'
        "</svg>"
    ),
    "概念": (
        '<svg width="20" height="20" viewBox="0 0 24 24" fill="none">'
        '<path d="M9 18h6M10 21h4M12 2a7 7 0 00-4 12.7c.6.5 1 1.2 1 2v.3h6V17'
        'c0-.8.4-1.5 1-2A7 7 0 0012 2z" stroke="currentColor"'
        ' stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>'
        "</svg>"
    ),
}

# ── 重要度 → 颜色 & 徽章 ────────────────────────────────────────
IMPORTANCE_COLORS = {
    ConceptImportance.HIGH: "red",
    ConceptImportance.MEDIUM: "orange",
    ConceptImportance.LOW: "green",
}

IMPORTANCE_BADGES = {
    ConceptImportance.HIGH: {
        "label": "核心概念",
        "icon": (
            '<svg width="14" height="14" viewBox="0 0 24 24" fill="none">'
            '<path d="M12 2c1 3 3 4 3 7a3 3 0 11-6 0c0-1 .5-2 1-3'
            '-2 1-4 3-4 6a6 6 0 1012 0c0-5-4-7-6-10z" fill="currentColor"/>'
            "</svg>"
        ),
    },
    ConceptImportance.MEDIUM: {
        "label": "重要概念",
        "icon": (
            '<svg width="14" height="14" viewBox="0 0 24 24" fill="none">'
            '<path d="M12 2l2.4 7.4H22l-6 4.4 2.3 7.2L12 16.6 5.7 21l2.3-7.2'
            '-6-4.4h7.6L12 2z" fill="currentColor"/>'
            "</svg>"
        ),
    },
    ConceptImportance.LOW: {
        "label": "参考概念",
        "icon": (
            '<svg width="14" height="14" viewBox="0 0 24 24" fill="none">'
            '<circle cx="12" cy="12" r="9" stroke="currentColor" stroke-width="2"/>'
            '<path d="M12 8v5M12 16v.5" stroke="currentColor"'
            ' stroke-width="2" stroke-linecap="round"/>'
            "</svg>"
        ),
    },
}


class ConceptCardRenderer(Renderer):
    """单概念卡片渲染器。

    为知识模型中每个概念生成一张视觉信息密集的 HTML 卡片。
    """

    def __init__(self, theme: str = "teal") -> None:
        self.theme = THEMES.get(theme, THEMES["teal"])

    @property
    def artifact_type(self) -> ArtifactType:
        return ArtifactType.CONCEPT_CARD

    def render(self, model: KnowledgeModel) -> RenderedArtifact:
        """渲染所有概念为卡片组 HTML。"""
        title = f"{model.book_title} - 概念卡片" if model.book_title else "概念卡片"
        cards_html = []

        for concept in model.concepts:
            cards_html.append(self._render_card(concept))

        html = self._wrap_html(title, "\n".join(cards_html), model.concept_count)
        return RenderedArtifact(
            artifact_type=self.artifact_type,
            content=html,
            title=title,
            metadata={"card_count": model.concept_count},
        )

    def render_single(self, concept: Concept, book_title: str = "") -> str:
        """渲染单个概念卡片 HTML。"""
        return self._render_card(concept)

    def _render_card(self, concept: Concept) -> str:
        """渲染单张概念卡片。"""
        theme_key = IMPORTANCE_COLORS.get(concept.importance, "teal")
        theme = THEMES.get(theme_key, self.theme)
        icon = TYPE_ICONS.get(concept.type, TYPE_ICONS["概念"])

        examples_html = ""
        if concept.examples:
            examples_items = "".join(
                f"<li>{self._esc(ex)}</li>" for ex in concept.examples
            )
            examples_html = f"""
            <div class="card-section">
                <span class="section-label">示例</span>
                <ul class="examples-list">{examples_items}</ul>
            </div>"""

        source_html = ""
        if concept.source_chapter:
            source_html = (
                f'<span class="source-tag">'
                f'<svg width="12" height="12" viewBox="0 0 24 24" fill="none">'
                f'<path d="M4 4h12a4 4 0 014 4v12H8a4 4 0 01-4-4V4z" '
                f'stroke="currentColor" stroke-width="2" stroke-linejoin="round"/>'
                f'<path d="M4 4v12a4 4 0 004 4" stroke="currentColor" '
                f'stroke-width="2"/></svg>'
                f" {self._esc(concept.source_chapter)}</span>"
            )

        badge_info = IMPORTANCE_BADGES.get(
            concept.importance, IMPORTANCE_BADGES[ConceptImportance.LOW]
        )

        name = self._esc(concept.name)
        definition = self._esc(concept.definition or "（暂无定义）")
        ctype = self._esc(concept.type)

        return f"""
        <div class="concept-card" style="--c-from:{theme['from']};--c-to:{theme['to']};--c-light:{theme['light']};--c-border:{theme['border']};--c-tint:{theme['tint']};">
            <div class="card-accent-bar"></div>
            <div class="card-body">
                <div class="card-top-row">
                    <div class="icon-circle">{icon}</div>
                    <span class="importance-badge">{badge_info['icon']}{badge_info['label']}</span>
                </div>
                <h3 class="card-title">{name}</h3>
                <div class="card-section">
                    <span class="section-label">定义</span>
                    <p class="definition">{definition}</p>
                </div>
                <div class="card-section type-row">
                    <span class="section-label">类型</span>
                    <span class="type-tag">{ctype}</span>
                </div>
                {examples_html}
                <div class="card-footer">
                    {source_html}
                </div>
            </div>
        </div>"""

    @staticmethod
    def _esc(text: str) -> str:
        """HTML 转义。"""
        return (
            text.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
        )

    def _wrap_html(self, title: str, cards_html: str, card_count: int) -> str:
        """包裹为完整 HTML 页面。"""
        esc_title = title.replace("<", "&lt;").replace(">", "&gt;")
        return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{esc_title}</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}

        body {{
            font-family: 'Inter', -apple-system, BlinkMacSystemFont,
                'Segoe UI', 'PingFang SC', 'Microsoft YaHei',
                'Noto Sans SC', sans-serif;
            background: linear-gradient(135deg, #f0f4f8 0%, #e8eef5 50%, #f0ebe4 100%);
            background-attachment: fixed;
            min-height: 100vh;
            padding: 32px 20px;
            color: #1e293b;
            -webkit-font-smoothing: antialiased;
            -moz-osx-font-smoothing: grayscale;
        }}

        .page-header {{
            text-align: center;
            margin-bottom: 36px;
            max-width: 700px;
            margin-left: auto;
            margin-right: auto;
        }}
        .page-header h1 {{
            font-size: 28px;
            font-weight: 800;
            letter-spacing: -0.5px;
            background: linear-gradient(135deg, #1e293b, #475569);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
        }}
        .page-header .count {{
            color: #64748b;
            font-size: 14px;
            font-weight: 500;
            margin-top: 6px;
        }}
        .page-header .count strong {{
            color: #334155;
            font-weight: 700;
        }}

        .cards-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(340px, 1fr));
            gap: 20px;
            max-width: 1200px;
            margin: 0 auto;
        }}

        /* ── 卡片 ── */
        .concept-card {{
            position: relative;
            background: #ffffff;
            border-radius: 16px;
            overflow: hidden;
            box-shadow:
                0 1px 3px rgba(0,0,0,0.06),
                0 1px 2px rgba(0,0,0,0.04);
            transition: transform 0.25s cubic-bezier(.4,0,.2,1),
                        box-shadow 0.25s cubic-bezier(.4,0,.2,1);
            border: 1px solid rgba(0,0,0,0.04);
        }}
        .concept-card:hover {{
            transform: translateY(-4px);
            box-shadow:
                0 12px 24px rgba(0,0,0,0.08),
                0 4px 8px rgba(0,0,0,0.04);
        }}

        .card-accent-bar {{
            height: 4px;
            background: linear-gradient(90deg, var(--c-from), var(--c-to));
        }}

        .card-body {{
            padding: 20px 22px 18px;
        }}

        .card-top-row {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 14px;
        }}

        .icon-circle {{
            width: 40px;
            height: 40px;
            border-radius: 12px;
            background: var(--c-tint);
            display: flex;
            align-items: center;
            justify-content: center;
            color: var(--c-from);
        }}

        .importance-badge {{
            display: inline-flex;
            align-items: center;
            gap: 5px;
            font-size: 12px;
            font-weight: 600;
            color: var(--c-to);
            background: var(--c-tint);
            padding: 4px 10px;
            border-radius: 20px;
            letter-spacing: 0.3px;
        }}
        .importance-badge svg {{
            flex-shrink: 0;
        }}

        .card-title {{
            font-size: 20px;
            font-weight: 700;
            letter-spacing: -0.3px;
            margin-bottom: 14px;
            color: #0f172a;
            line-height: 1.35;
        }}

        .card-section {{
            margin-bottom: 12px;
        }}
        .card-section:last-of-type {{
            margin-bottom: 0;
        }}

        .section-label {{
            display: block;
            font-size: 11px;
            font-weight: 700;
            color: #94a3b8;
            text-transform: uppercase;
            letter-spacing: 1.2px;
            margin-bottom: 5px;
        }}

        .definition {{
            font-size: 14px;
            line-height: 1.65;
            color: #334155;
            padding: 10px 14px;
            background: #f8fafc;
            border-radius: 8px;
            border-left: 3px solid var(--c-border);
        }}

        .type-row {{
            display: flex;
            align-items: center;
            gap: 10px;
        }}
        .type-row .section-label {{
            margin-bottom: 0;
        }}
        .type-tag {{
            display: inline-block;
            padding: 3px 12px;
            border-radius: 20px;
            background: var(--c-tint);
            color: var(--c-to);
            font-size: 12px;
            font-weight: 600;
        }}

        .examples-list {{
            list-style: none;
            padding-left: 0;
        }}
        .examples-list li {{
            font-size: 13px;
            color: #475569;
            padding: 5px 0 5px 18px;
            position: relative;
            line-height: 1.5;
        }}
        .examples-list li::before {{
            content: "";
            position: absolute;
            left: 4px;
            top: 11px;
            width: 6px;
            height: 6px;
            border-radius: 50%;
            background: var(--c-from);
        }}

        .card-footer {{
            margin-top: 14px;
            padding-top: 12px;
            border-top: 1px solid #f1f5f9;
            display: flex;
            align-items: center;
            gap: 8px;
        }}
        .source-tag {{
            display: inline-flex;
            align-items: center;
            gap: 5px;
            font-size: 12px;
            color: #94a3b8;
            font-weight: 500;
        }}
        .source-tag svg {{
            flex-shrink: 0;
            opacity: 0.7;
        }}

        @media (max-width: 640px) {{
            body {{ padding: 16px 12px; }}
            .cards-grid {{
                grid-template-columns: 1fr;
                gap: 14px;
            }}
            .page-header h1 {{ font-size: 22px; }}
            .card-title {{ font-size: 18px; }}
        }}
    </style>
</head>
<body>
    <div class="page-header">
        <h1>{esc_title}</h1>
        <div class="count">共 <strong>{card_count}</strong> 个概念</div>
    </div>
    <div class="cards-grid">
        {cards_html}
    </div>
</body>
</html>"""

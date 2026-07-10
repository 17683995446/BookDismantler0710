"""卡片组装配器：索引页 + 多卡导航。"""

from __future__ import annotations

from book_dismantler.domain.knowledge import KnowledgeModel
from book_dismantler.rendering.base import ArtifactType, RenderedArtifact, Renderer
from book_dismantler.rendering.cards.card_renderer import ConceptCardRenderer


class CardDeckRenderer(Renderer):
    """卡片组渲染器：生成带索引导航的概念卡片组。"""

    def __init__(self, theme: str = "teal") -> None:
        self.card_renderer = ConceptCardRenderer(theme=theme)

    @property
    def artifact_type(self) -> ArtifactType:
        return ArtifactType.CONCEPT_CARD

    def render(self, model: KnowledgeModel) -> RenderedArtifact:
        """渲染带索引页的卡片组。"""
        title = f"{model.book_title} - 知识卡片组" if model.book_title else "知识卡片组"

        # 生成索引
        index_items = []
        for i, concept in enumerate(model.concepts):
            index_items.append(
                f'<a href="#card-{i}" class="index-item">{concept.name}</a>'
            )
        index_html = "\n".join(index_items)

        # 生成卡片
        cards_html = []
        for i, concept in enumerate(model.concepts):
            card = self.card_renderer.render_single(concept)
            card = card.replace('class="concept-card"', f'class="concept-card" id="card-{i}"')
            cards_html.append(card)

        html = self._wrap_deck_html(title, index_html, "\n".join(cards_html), model.concept_count)

        return RenderedArtifact(
            artifact_type=self.artifact_type,
            content=html,
            title=title,
            metadata={"card_count": model.concept_count},
        )

    def _wrap_deck_html(
        self, title: str, index_html: str, cards_html: str, count: int
    ) -> str:
        """包裹卡片组 HTML。"""
        return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: "Noto Sans SC", "Microsoft YaHei", sans-serif;
            background: #f0ebe4;
        }}
        .sidebar {{
            position: fixed;
            left: 0; top: 0;
            width: 240px;
            height: 100vh;
            background: #1a7a6d;
            padding: 24px 16px;
            overflow-y: auto;
        }}
        .sidebar h2 {{
            color: white;
            font-size: 18px;
            margin-bottom: 16px;
        }}
        .index-item {{
            display: block;
            color: #c5e8e0;
            text-decoration: none;
            padding: 8px 12px;
            border-radius: 8px;
            font-size: 14px;
            margin-bottom: 4px;
            transition: background 0.2s;
        }}
        .index-item:hover {{
            background: rgba(255,255,255,0.1);
            color: white;
        }}
        .main-content {{
            margin-left: 240px;
            padding: 24px;
        }}
        .cards-container {{
            display: flex;
            flex-direction: column;
            gap: 24px;
            max-width: 800px;
        }}
    </style>
</head>
<body>
    <div class="sidebar">
        <h2>📚 目录</h2>
        {index_html}
    </div>
    <div class="main-content">
        <div class="cards-container">
            {cards_html}
        </div>
    </div>
</body>
</html>"""

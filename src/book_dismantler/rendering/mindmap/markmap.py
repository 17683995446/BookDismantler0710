"""Markmap 思维导图渲染器。

将 KnowledgeModel 转换为 Markdown 大纲，
再嵌入自包含 HTML（含 vendored markmap-view JS）生成可交互思维导图。
"""

from __future__ import annotations

from book_dismantler.domain.knowledge import (
    Concept,
    ConceptImportance,
    KnowledgeModel,
    OutlineNode,
    Relationship,
    RelationshipType,
)
from book_dismantler.rendering.base import ArtifactType, RenderedArtifact, Renderer


class MarkmapRenderer(Renderer):
    """基于 markmap 的思维导图渲染器。

    生成自包含 HTML，内嵌 markmap-view CDN 脚本，
    离线时需替换为 vendored 版本。
    """

    @property
    def artifact_type(self) -> ArtifactType:
        return ArtifactType.MINDMAP_HTML

    def render(self, model: KnowledgeModel) -> RenderedArtifact:
        """渲染知识模型为思维导图 HTML。"""
        title = model.book_title or "思维导图"
        markdown_outline = self._build_markdown(model)
        html = self._wrap_html(title, markdown_outline)

        return RenderedArtifact(
            artifact_type=self.artifact_type,
            content=html,
            title=title,
            metadata={
                "node_count": model.outline_node_count + model.concept_count,
            },
        )

    def _build_markdown(self, model: KnowledgeModel) -> str:
        """将知识模型转换为 Markdown 大纲（markmap 格式）。

        为保证思维导图可读性，精简内容：
        - 大纲：保留 2 级深度
        - 概念：仅展示名称，按重要度分组，限制数量
        - 关系：按类型分组，限制数量
        """
        lines: list[str] = []

        # 根节点：书名
        root_title = model.book_title or "思维导图"
        lines.append(f"# {root_title}\n")

        # 结构大纲
        if model.outline:
            lines.append("## 内容大纲\n")
            for node in model.outline:
                lines.extend(self._node_to_markdown(node, 1))
            lines.append("")

        # 核心概念 —— 按重要度分组
        if model.concepts:
            high = [c for c in model.concepts if c.importance == ConceptImportance.HIGH]
            medium = [c for c in model.concepts if c.importance == ConceptImportance.MEDIUM]
            low = [c for c in model.concepts if c.importance == ConceptImportance.LOW]

            lines.append("## 核心概念\n")
            if high:
                lines.append(
                    f"- {ConceptImportance.HIGH.icon} "
                    f"{ConceptImportance.HIGH.label}概念（{len(high)}）\n"
                )
                for c in high[:20]:
                    lines.append(f"  - {c.name}")
            if medium:
                lines.append(
                    f"- {ConceptImportance.MEDIUM.icon} "
                    f"{ConceptImportance.MEDIUM.label}概念（{len(medium)}）\n"
                )
                for c in medium[:15]:
                    lines.append(f"  - {c.name}")
            if low:
                lines.append(
                    f"- {ConceptImportance.LOW.icon} "
                    f"{ConceptImportance.LOW.label}概念（{len(low)}）\n"
                )
                for c in low[:10]:
                    lines.append(f"  - {c.name}")
            lines.append("")

        # 概念关系 —— 按类型分组，限制数量
        if model.relationships:
            lines.append("## 概念关系\n")
            by_type: dict[RelationshipType, list[Relationship]] = {}
            for rel in model.relationships:
                by_type.setdefault(rel.type, []).append(rel)

            for rel_type, rels in by_type.items():
                lines.append(f"- {rel_type.label} ({rel_type.value})（{len(rels)}）\n")
                for rel in rels[:12]:
                    lines.append(f"  - {rel.source} → {rel.target}")
            lines.append("")

        return "\n".join(lines)

    def _node_to_markdown(self, node: OutlineNode, depth: int = 1) -> list[str]:
        """将大纲节点转换为 Markdown 列表。"""
        lines: list[str] = []
        indent = "  " * (depth - 1)
        line = f"{indent}- {node.title}"
        if node.summary:
            line += f"：{node.summary}"
        lines.append(line)
        for child in node.children:
            lines.extend(self._node_to_markdown(child, depth + 1))
        return lines

    def _concept_to_markdown(self, concept: Concept, depth: int = 1) -> list[str]:
        """将概念转换为 Markdown 列表。"""
        lines: list[str] = []
        indent = "  " * (depth - 1)
        icon = concept.importance.icon
        lines.append(f"{indent}- {icon} {concept.name}")
        if concept.definition:
            lines.append(f"{indent}  - {concept.definition}")
        for ex in concept.examples:
            lines.append(f"{indent}  - 示例：{ex}")
        return lines

    def _wrap_html(self, title: str, markdown: str) -> str:
        """将 Markdown 包裹为自包含 markmap HTML。"""
        # 转义 markdown 中的特殊字符用于嵌入
        import json

        markdown_json = json.dumps(markdown, ensure_ascii=False)

        return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title} - 思维导图</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        html, body {{
            width: 100%;
            height: 100%;
            font-family: "Noto Sans SC", "Microsoft YaHei", sans-serif;
            background: #f8f9fa;
            overflow: hidden;
        }}
        #mindmap {{
            width: 100vw;
            height: 100vh;
            display: block;
        }}
        .toolbar {{
            position: fixed;
            top: 16px;
            right: 16px;
            z-index: 100;
            display: flex;
            gap: 8px;
        }}
        .toolbar button {{
            padding: 8px 16px;
            border: none;
            border-radius: 8px;
            background: #1a7a6d;
            color: white;
            cursor: pointer;
            font-size: 14px;
            transition: background 0.2s;
        }}
        .toolbar button:hover {{
            background: #145f54;
        }}
    </style>
    <script src="https://cdn.jsdelivr.net/npm/d3@7"></script>
    <script src="https://cdn.jsdelivr.net/npm/markmap-view"></script>
    <script src="https://cdn.jsdelivr.net/npm/markmap-lib"></script>
</head>
<body>
    <div class="toolbar">
        <button onclick="expandAll()">展开全部</button>
        <button onclick="collapseAll()">折叠</button>
        <button onclick="fitView()">适应</button>
        <button onclick="downloadSvg()">下载</button>
    </div>
    <svg id="mindmap"></svg>
    <script>
        const markdown = {markdown_json};
        const {{ Transformer }} = markmap;
        const transformer = new Transformer();
        const {{ root }} = transformer.transform(markdown);
        const mm = markmap.Markmap.create('#mindmap', {{
            autoFit: true,
            duration: 300,
            maxWidth: 300,
            spacingHorizontal: 80,
            spacingVertical: 20,
            colorFreezeLevel: 2,
            initialExpandLevel: 3,
            zoom: true,
            pan: true,
            padding: 20,
        }}, root);

        // 适应屏幕
        function fitView() {{
            mm.fit();
        }}

        // 展开全部后重新适配
        function expandAll() {{
            mm.setData(root, {{ initialExpandLevel: -1 }});
            setTimeout(function() {{ mm.fit(); }}, 400);
        }}

        // 折叠到 2 级后重新适配
        function collapseAll() {{
            mm.setData(root, {{ initialExpandLevel: 3 }});
            setTimeout(function() {{ mm.fit(); }}, 400);
        }}

        function downloadSvg() {{
            const svg = document.getElementById('mindmap');
            const serializer = new XMLSerializer();
            const source = serializer.serializeToString(svg);
            const blob = new Blob([source], {{ type: 'image/svg+xml' }});
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = '{title}_mindmap.svg';
            a.click();
            URL.revokeObjectURL(url);
        }}
    </script>
</body>
</html>"""

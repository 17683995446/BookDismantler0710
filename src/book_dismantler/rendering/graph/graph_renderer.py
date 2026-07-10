"""知识图谱渲染器。

基于 ECharts 力导向图，将概念间关系可视化为交互式知识图谱。
支持节点拖拽、缩放、关系类型颜色区分、Tooltip 详情。
"""

from __future__ import annotations

import json
from typing import Any

from book_dismantler.domain.knowledge import (
    Concept,
    KnowledgeModel,
)
from book_dismantler.rendering.base import ArtifactType, RenderedArtifact, Renderer

# ── 关系类型 → 颜色 & 中文标签 ──────────────────────────────────
RELATION_STYLE: dict[str, dict[str, Any]] = {
    "is-a": {"color": "#3b82f6", "label": "属于", "dash": None},
    "part-of": {"color": "#8b5cf6", "label": "包含", "dash": None},
    "depends-on": {"color": "#f59e0b", "label": "依赖", "dash": [4, 4]},
    "contradicts": {"color": "#ef4444", "label": "对立", "dash": [6, 4]},
    "supports": {"color": "#10b981", "label": "支持", "dash": None},
    "related-to": {"color": "#64748b", "label": "相关", "dash": [2, 4]},
}

# ── 重要度 → 节点大小 & 颜色 ────────────────────────────────────
IMPORTANCE_STYLE: dict[str, dict[str, Any]] = {
    "high": {"size": 48, "color": "#ef4444", "label": "核心"},
    "medium": {"size": 36, "color": "#f59e0b", "label": "重要"},
    "low": {"size": 26, "color": "#10b981", "label": "参考"},
}

# ── 概念类型 → 图标符号 ─────────────────────────────────────────
TYPE_SYMBOLS: dict[str, str] = {
    "方法论": "roundRect",
    "术语": "circle",
    "模型": "diamond",
    "原则": "triangle",
    "概念": "circle",
    "技法": "pin",
    "理论": "rect",
    "化学反应": "circle",
}

# ── HTML 模板（使用占位符避免 f-string 花括号冲突）──────────────
_HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>__TITLE__</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: 'Inter', -apple-system, BlinkMacSystemFont,
                'Segoe UI', 'PingFang SC', 'Microsoft YaHei', sans-serif;
            background: linear-gradient(135deg, #f0f4f8 0%, #e8eef5 50%, #f0ebe4 100%);
            min-height: 100vh;
            -webkit-font-smoothing: antialiased;
        }
        .toolbar {
            position: fixed; top: 16px; right: 20px; z-index: 100;
            display: flex; gap: 8px;
        }
        .toolbar button {
            padding: 8px 16px; border: 1px solid #cbd5e1; border-radius: 8px;
            background: rgba(255,255,255,0.92); color: #334155;
            font-size: 13px; font-weight: 600; cursor: pointer;
            transition: all 0.2s; backdrop-filter: blur(8px);
            display: flex; align-items: center; gap: 5px;
        }
        .toolbar button:hover {
            background: #fff; border-color: #94a3b8;
            box-shadow: 0 2px 8px rgba(0,0,0,0.08);
        }
        .toolbar button svg { flex-shrink: 0; }
        #chart { width: 100vw; height: 100vh; }
        .legend-panel {
            position: fixed; bottom: 60px; left: 20px; z-index: 100;
            background: rgba(255,255,255,0.92); border: 1px solid #e2e8f0;
            border-radius: 12px; padding: 14px 18px;
            backdrop-filter: blur(8px); box-shadow: 0 4px 12px rgba(0,0,0,0.06);
            max-width: 280px;
        }
        .legend-panel h3 {
            font-size: 13px; font-weight: 700; color: #1e293b;
            margin-bottom: 10px; letter-spacing: 0.3px;
        }
        .legend-row {
            display: flex; align-items: center; gap: 8px;
            margin-bottom: 6px; font-size: 12px; color: #475569;
        }
        .legend-line { width: 24px; height: 2px; border-radius: 1px; flex-shrink: 0; }
        .legend-dot { width: 10px; height: 10px; border-radius: 50%; flex-shrink: 0; }
        @media (max-width: 640px) {
            .legend-panel { display: none; }
            .toolbar button { padding: 6px 10px; font-size: 12px; }
        }
    </style>
</head>
<body>
    <div class="toolbar">
        <button onclick="resetZoom()" title="重置缩放">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none">
                <path d="M3 12a9 9 0 1018 0 9 9 0 00-18 0z" stroke="currentColor" stroke-width="2"/>
                <path d="M12 8v8M8 12h8" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>
            </svg>
            重置
        </button>
        <button onclick="toggleLabels()" title="切换标签">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none">
                <path d="M4 7h16M4 12h10M4 17h7" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>
            </svg>
            标签
        </button>
        <button onclick="toggleFullscreen()" title="全屏">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none">
                <path d="M4 9V4h5M20 9V4h-5M4 15v5h5M20 15v5h-5" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>
            </svg>
            全屏
        </button>
    </div>
    <div class="legend-panel">
        <h3>关系类型</h3>
        <div class="legend-row"><span class="legend-line" style="background:#3b82f6"></span>属于 (is-a)</div>
        <div class="legend-row"><span class="legend-line" style="background:#8b5cf6"></span>包含 (part-of)</div>
        <div class="legend-row"><span class="legend-line" style="background:none;border-top:2px dashed #f59e0b"></span>依赖 (depends-on)</div>
        <div class="legend-row"><span class="legend-line" style="background:none;border-top:2px dashed #ef4444"></span>对立 (contradicts)</div>
        <div class="legend-row"><span class="legend-line" style="background:#10b981"></span>支持 (supports)</div>
        <div class="legend-row"><span class="legend-line" style="background:none;border-top:2px dashed #64748b"></span>相关 (related-to)</div>
        <div style="height:8px"></div>
        <h3>节点大小</h3>
        <div class="legend-row"><span class="legend-dot" style="background:#ef4444;width:14px;height:14px"></span>核心概念</div>
        <div class="legend-row"><span class="legend-dot" style="background:#f59e0b;width:11px;height:11px"></span>重要概念</div>
        <div class="legend-row"><span class="legend-dot" style="background:#10b981;width:8px;height:8px"></span>参考概念</div>
    </div>
    <div id="chart"></div>
    <script src="https://cdn.jsdelivr.net/npm/echarts@5.4.3/dist/echarts.min.js"></script>
    <script>
        var chartDom = document.getElementById('chart');
        var myChart = echarts.init(chartDom);
        var nodes = __NODES__;
        var links = __LINKS__;
        var option = __OPTION__;

        option.tooltip.formatter = function(params) {
            if (params.dataType === 'node') {
                var d = params.data;
                var html = '<div style="font-size:15px;font-weight:700;margin-bottom:6px;">' +
                    params.name + '</div>';
                if (d.conceptType && d.conceptType !== '未知') {
                    html += '<div style="font-size:12px;color:#94a3b8;margin-bottom:4px;">类型: ' +
                        d.conceptType + ' · ' + (d.importance === 'high' ? '核心' : d.importance === 'medium' ? '重要' : '参考') + '</div>';
                }
                if (d.value) {
                    html += '<div style="font-size:13px;line-height:1.5;max-width:300px;">' +
                        d.value.substring(0, 200) + (d.value.length > 200 ? '...' : '') + '</div>';
                }
                if (d.sourceChapter) {
                    html += '<div style="font-size:11px;color:#64748b;margin-top:4px;">📍 ' +
                        d.sourceChapter + '</div>';
                }
                if (d.examples && d.examples.length) {
                    html += '<div style="font-size:11px;color:#94a3b8;margin-top:4px;">示例: ' +
                        d.examples.join('；').substring(0, 100) + '</div>';
                }
                return html;
            } else if (params.dataType === 'edge') {
                var d = params.data;
                var html = '<div style="font-weight:700;margin-bottom:4px;">' +
                    d.source + ' → ' + d.target + '</div>';
                html += '<div style="color:#94a3b8;font-size:12px;margin-bottom:4px;">关系: ' +
                    d.value + '</div>';
                if (d.description) {
                    html += '<div style="font-size:13px;line-height:1.5;max-width:280px;">' +
                        d.description + '</div>';
                }
                if (d.evidence) {
                    html += '<div style="font-size:11px;color:#64748b;margin-top:4px;border-top:1px solid #475569;padding-top:4px;">📝 ' +
                        d.evidence.substring(0, 120) + (d.evidence.length > 120 ? '...' : '') + '</div>';
                }
                return html;
            }
            return params.name;
        };

        myChart.setOption(option);
        window.addEventListener('resize', function() { myChart.resize(); });

        function resetZoom() {
            myChart.dispatchAction({ type: 'restore' });
        }
        var labelsVisible = true;
        function toggleLabels() {
            labelsVisible = !labelsVisible;
            myChart.setOption({
                series: [{ label: { show: labelsVisible } }]
            });
        }
        function toggleFullscreen() {
            if (!document.fullscreenElement) {
                document.documentElement.requestFullscreen();
            } else {
                document.exitFullscreen();
            }
        }
    </script>
</body>
</html>"""


class KnowledgeGraphRenderer(Renderer):
    """知识图谱渲染器。

    将知识模型中的概念和关系渲染为基于 ECharts 的交互式力导向图。
    """

    @property
    def artifact_type(self) -> ArtifactType:
        return ArtifactType.KNOWLEDGE_GRAPH

    def render(self, model: KnowledgeModel) -> RenderedArtifact:
        """渲染知识图谱为自包含 HTML。"""
        title = (
            f"{model.book_title} - 知识图谱" if model.book_title else "知识图谱"
        )

        nodes_data = self._build_nodes(model)
        links_data = self._build_links(model)
        categories = self._build_categories()

        graph_option = {
            "title": {
                "text": title,
                "subtext": f"共 {len(nodes_data)} 个概念 · {len(links_data)} 条关系",
                "left": "center",
                "top": 10,
                "textStyle": {"fontSize": 22, "fontWeight": 700, "color": "#1e293b"},
                "subtextStyle": {"fontSize": 13, "color": "#64748b"},
            },
            "tooltip": {
                "trigger": "item",
                "backgroundColor": "rgba(30,41,59,0.95)",
                "borderColor": "#475569",
                "borderWidth": 0,
                "textStyle": {"color": "#f1f5f9", "fontSize": 13},
                "extraCssText": "border-radius:10px;box-shadow:0 8px 24px rgba(0,0,0,0.2);max-width:360px;",
            },
            "legend": [
                {
                    "data": [c["name"] for c in categories],
                    "top": "bottom",
                    "left": "center",
                    "orient": "horizontal",
                    "textStyle": {"fontSize": 12, "color": "#64748b"},
                    "itemGap": 16,
                    "itemWidth": 14,
                    "itemHeight": 14,
                }
            ],
            "animationDurationUpdate": 800,
            "animationEasingUpdate": "cubicInOut",
            "series": [
                {
                    "type": "graph",
                    "layout": "force",
                    "data": nodes_data,
                    "links": links_data,
                    "categories": categories,
                    "roam": True,
                    "zoom": 1.0,
                    "label": {
                        "show": True,
                        "position": "right",
                        "fontSize": 12,
                        "color": "#334155",
                        "fontWeight": 500,
                        "formatter": "{b}",
                    },
                    "labelLayout": {
                        "hideOverlap": True,
                        "moveOverlap": "shiftY",
                    },
                    "force": {
                        "repulsion": 260,
                        "edgeLength": [80, 180],
                        "gravity": 0.08,
                        "friction": 0.6,
                        "layoutAnimation": True,
                    },
                    "lineStyle": {
                        "color": "source",
                        "width": 1.8,
                        "curveness": 0.15,
                        "opacity": 0.7,
                    },
                    "emphasis": {
                        "focus": "adjacency",
                        "lineStyle": {"width": 3, "opacity": 1},
                        "label": {"fontSize": 14, "fontWeight": 700},
                    },
                    "edgeSymbol": ["none", "arrow"],
                    "edgeSymbolSize": [0, 7],
                }
            ],
        }

        option_json = json.dumps(graph_option, ensure_ascii=False)
        nodes_json = json.dumps(nodes_data, ensure_ascii=False)
        links_json = json.dumps(links_data, ensure_ascii=False)
        esc_title = title.replace("<", "&lt;").replace(">", "&gt;")

        html = (
            _HTML_TEMPLATE
            .replace("__TITLE__", esc_title)
            .replace("__NODES__", nodes_json)
            .replace("__LINKS__", links_json)
            .replace("__OPTION__", option_json)
        )

        return RenderedArtifact(
            artifact_type=self.artifact_type,
            content=html,
            title=title,
            metadata={
                "node_count": len(nodes_data),
                "link_count": len(links_data),
            },
        )

    def _build_nodes(self, model: KnowledgeModel) -> list[dict[str, Any]]:
        """构建 ECharts 节点数据。"""
        nodes = []
        concept_map: dict[str, Concept] = {}
        for c in model.concepts:
            concept_map[c.key] = c

        all_names: set[str] = set()
        for r in model.relationships:
            all_names.add(r.source.strip())
            all_names.add(r.target.strip())
        for c in model.concepts:
            all_names.add(c.name.strip())

        for name in sorted(all_names):
            key = name.strip().lower()
            concept = concept_map.get(key)
            if concept:
                imp = concept.importance.value
                style = IMPORTANCE_STYLE.get(imp, IMPORTANCE_STYLE["medium"])
                ctype = concept.type or "概念"
                symbol = TYPE_SYMBOLS.get(ctype, "circle")
                node = {
                    "name": name,
                    "value": concept.definition or "",
                    "symbolSize": style["size"],
                    "itemStyle": {
                        "color": style["color"],
                        "shadowBlur": 8,
                        "shadowColor": style["color"] + "40",
                    },
                    "symbol": symbol,
                    "category": style["label"],
                    "label": {"show": True},
                    "conceptType": ctype,
                    "importance": imp,
                    "sourceChapter": concept.source_chapter or "",
                    "examples": concept.examples[:3] if concept.examples else [],
                }
            else:
                node = {
                    "name": name,
                    "value": "",
                    "symbolSize": 22,
                    "itemStyle": {"color": "#94a3b8", "opacity": 0.8},
                    "symbol": "circle",
                    "category": "参考",
                    "label": {"show": True},
                    "conceptType": "未知",
                    "importance": "low",
                }
            nodes.append(node)
        return nodes

    def _build_links(self, model: KnowledgeModel) -> list[dict[str, Any]]:
        """构建 ECharts 边数据。"""
        links = []
        for r in model.relationships:
            rtype = r.type.value
            style = RELATION_STYLE.get(rtype, RELATION_STYLE["related-to"])
            link = {
                "source": r.source.strip(),
                "target": r.target.strip(),
                "value": style["label"],
                "lineStyle": {
                    "color": style["color"],
                    "width": 1.8,
                    "curveness": 0.15,
                    "type": style["dash"] or "solid",
                },
                "relationType": rtype,
                "description": r.description or "",
                "evidence": r.evidence or "",
            }
            links.append(link)
        return links

    def _build_categories(self) -> list[dict[str, Any]]:
        """构建 ECharts 分类（图例）。"""
        return [
            {"name": "核心", "itemStyle": {"color": "#ef4444"}},
            {"name": "重要", "itemStyle": {"color": "#f59e0b"}},
            {"name": "参考", "itemStyle": {"color": "#10b981"}},
        ]

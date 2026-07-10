"""渲染器抽象接口与产物描述符。"""

from __future__ import annotations

from abc import ABC, abstractmethod
from enum import Enum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from book_dismantler.domain.knowledge import KnowledgeModel


def safe_title(title: str) -> str:
    """将标题转换为安全的文件名片段。

    保留字母、数字、连字符、下划线和空格，去除首尾空白后
    将空格替换为下划线，使其可用作文件名。不含扩展名，
    可能返回空字符串（由调用方处理回退）。

    Args:
        title: 原始标题。

    Returns:
        清理后的安全文件名片段。
    """
    return "".join(
        c for c in title if c.isalnum() or c in "-_ "
    ).strip().replace(" ", "_")


class ArtifactType(str, Enum):
    """产物类型。"""

    MARKDOWN_NOTES = "markdown_notes"
    ORG_NOTES = "org_notes"
    MINDMAP_HTML = "mindmap_html"
    CONCEPT_CARD = "concept_card"
    INFOGRAPHIC = "infographic"
    ANATOMY_CHART = "anatomy_chart"
    KNOWLEDGE_GRAPH = "knowledge_graph"
    PNG_IMAGE = "png_image"
    BUNDLE = "bundle"


class RenderedArtifact(BaseModel):
    """渲染产物描述符。"""

    artifact_type: ArtifactType
    content: str = Field(default="", description="文本内容（HTML/Markdown/org）")
    file_path: str = Field(default="", description="文件路径（若已写盘）")
    title: str = Field(default="", description="产物标题")
    metadata: dict[str, Any] = Field(default_factory=dict, description="附加元信息")

    model_config = {"frozen": False}


class Renderer(ABC):
    """渲染器抽象基类。

    每种渲染器将 ``KnowledgeModel`` 转换为特定格式的 ``RenderedArtifact``。
    """

    @property
    @abstractmethod
    def artifact_type(self) -> ArtifactType:
        """产物类型。"""
        ...

    @abstractmethod
    def render(self, model: KnowledgeModel) -> RenderedArtifact:
        """渲染知识模型为产物。

        Args:
            model: 知识模型。

        Returns:
            渲染产物。
        """
        ...

    def save(self, artifact: RenderedArtifact, output_dir: str | Path) -> Path:
        """将产物写入文件。

        Args:
            artifact: 渲染产物。
            output_dir: 输出目录。

        Returns:
            文件路径。
        """
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        filename = self._get_filename(artifact)
        path = output_dir / filename
        path.write_text(artifact.content, encoding="utf-8")
        return path

    def _get_filename(self, artifact: RenderedArtifact) -> str:
        """根据产物类型生成文件名。"""
        ext_map = {
            ArtifactType.MARKDOWN_NOTES: "md",
            ArtifactType.ORG_NOTES: "org",
            ArtifactType.MINDMAP_HTML: "html",
            ArtifactType.CONCEPT_CARD: "html",
            ArtifactType.INFOGRAPHIC: "html",
            ArtifactType.ANATOMY_CHART: "html",
            ArtifactType.KNOWLEDGE_GRAPH: "html",
        }
        ext = ext_map.get(artifact.artifact_type, "txt")
        title = artifact.title or "output"
        return f"{safe_title(title)}.{ext}"

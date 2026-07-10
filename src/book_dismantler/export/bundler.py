"""产物打包器：将所有渲染产物组织到输出目录或 zip。"""

from __future__ import annotations

import json
import zipfile
from pathlib import Path
from typing import Any

from book_dismantler.core.logging import get_logger
from book_dismantler.domain.knowledge import KnowledgeModel
from book_dismantler.rendering.base import ArtifactType, RenderedArtifact, safe_title

logger = get_logger("export.bundler")


class ArtifactBundler:
    """产物打包器。

    将多种渲染产物统一组织到输出目录，
    并生成 manifest 清单和可选 zip 包。
    """

    def bundle(
        self,
        artifacts: list[RenderedArtifact],
        knowledge_model: KnowledgeModel,
        output_dir: str | Path,
        *,
        create_zip: bool = False,
    ) -> Path:
        """打包所有产物到输出目录。

        Args:
            artifacts: 渲染产物列表。
            knowledge_model: 原始知识模型（导出为 JSON）。
            output_dir: 输出目录。
            create_zip: 是否额外创建 zip 包。

        Returns:
            输出目录路径（或 zip 路径）。
        """
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        manifest: list[dict[str, Any]] = []

        # 写入各产物
        for artifact in artifacts:
            filename = self._get_filename(artifact)
            path = output_dir / filename
            path.write_text(artifact.content, encoding="utf-8")

            manifest.append({
                "type": artifact.artifact_type.value,
                "filename": filename,
                "title": artifact.title,
                "metadata": artifact.metadata,
            })
            logger.info("产物写入: %s", path)

        # 写入知识模型 JSON
        model_path = output_dir / "knowledge_model.json"
        model_path.write_text(
            knowledge_model.model_dump_json(indent=2), encoding="utf-8"
        )
        manifest.append({
            "type": "knowledge_model",
            "filename": "knowledge_model.json",
            "title": "原始知识模型",
        })

        # 写入 manifest
        manifest_path = output_dir / "manifest.json"
        manifest_data = {
            "book_title": knowledge_model.book_title,
            "book_author": knowledge_model.book_author,
            "artifact_count": len(manifest),
            "artifacts": manifest,
            "stats": {
                "concepts": knowledge_model.concept_count,
                "relationships": knowledge_model.relationship_count,
                "outline_nodes": knowledge_model.outline_node_count,
                "anatomies": len(knowledge_model.anatomies),
            },
        }
        manifest_path.write_text(
            json.dumps(manifest_data, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        logger.info("manifest 写入: %s", manifest_path)

        # 可选 zip
        if create_zip:
            zip_path = output_dir.with_suffix(".zip")
            with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
                for file in output_dir.rglob("*"):
                    if file.is_file():
                        zf.write(file, file.relative_to(output_dir))
            logger.info("zip 包创建: %s", zip_path)
            return zip_path

        return output_dir

    def _get_filename(self, artifact: RenderedArtifact) -> str:
        """根据产物类型生成文件名。

        对于 HTML 类产物，在文件名中加入类型后缀以避免同名覆盖。
        """
        ext_map = {
            ArtifactType.MARKDOWN_NOTES: ("notes", "md", ""),
            ArtifactType.ORG_NOTES: ("notes", "org", ""),
            ArtifactType.MINDMAP_HTML: ("mindmap", "html", "-思维导图"),
            ArtifactType.CONCEPT_CARD: ("concept_cards", "html", "-概念卡片"),
            ArtifactType.INFOGRAPHIC: ("infographic", "html", "-信息图"),
            ArtifactType.ANATOMY_CHART: ("anatomy", "html", "-概念解剖"),
            ArtifactType.KNOWLEDGE_GRAPH: ("graph", "html", "-知识图谱"),
        }
        entry = ext_map.get(artifact.artifact_type, ("output", "txt", ""))
        prefix, ext, suffix = entry
        title = artifact.title or prefix
        safe = safe_title(title)[:30] or prefix
        # 中文后缀不经过 safe_title 过滤，直接拼接
        # 但如果 title 中已包含后缀文字则不重复添加
        # 去除标题中的空格后检查后缀是否已存在，避免重复
        title_compact = title.replace(" ", "")
        if suffix and suffix not in title_compact:
            return f"{safe}{suffix}.{ext}"
        return f"{safe}.{ext}"

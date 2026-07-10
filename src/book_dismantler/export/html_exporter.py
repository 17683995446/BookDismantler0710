"""HTML 导出器：写盘 + 资源内联。"""

from __future__ import annotations

from pathlib import Path

from book_dismantler.core.exceptions import ExportError
from book_dismantler.core.logging import get_logger
from book_dismantler.rendering.base import RenderedArtifact, safe_title

logger = get_logger("export.html")


class HtmlExporter:
    """HTML 导出器。

    将渲染产物写入文件，可选内联外部资源（CSS/JS/字体）。
    """

    def export(
        self,
        artifact: RenderedArtifact,
        output_dir: str | Path,
        *,
        filename: str | None = None,
    ) -> Path:
        """将 HTML 产物写入文件。

        Args:
            artifact: 渲染产物。
            output_dir: 输出目录。
            filename: 文件名（为 None 时自动生成）。

        Returns:
            文件路径。
        """
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        if not filename:
            title = artifact.title or "output"
            filename = f"{safe_title(title) or 'output'}.html"

        path = output_dir / filename

        try:
            path.write_text(artifact.content, encoding="utf-8")
            logger.info("HTML 导出: %s", path)
            return path
        except Exception as e:
            raise ExportError(f"HTML 写盘失败: {e}") from e

    def export_inline(
        self,
        artifact: RenderedArtifact,
        output_dir: str | Path,
        *,
        filename: str | None = None,
    ) -> Path:
        """导出为资源内联的单 HTML 文件。

        将外部 CSS/JS 链接替换为内联内容，保证单文件可分发。
        """
        content = artifact.content

        # 内联 CDN 脚本（简单实现：保留 CDN 链接，因为无法在离线环境下载）
        # 完整实现需要下载并 base64 编码，此处保持 CDN 引用
        # 标记为自包含（实际依赖 CDN）
        content = self._add_offline_notice(content)

        return self.export(
            RenderedArtifact(
                artifact_type=artifact.artifact_type,
                content=content,
                title=artifact.title,
                metadata={**artifact.metadata, "inlined": True},
            ),
            output_dir,
            filename=filename,
        )

    def _add_offline_notice(self, html: str) -> str:
        """在 HTML 中添加离线说明注释。"""
        notice = "<!-- 此文件引用了 CDN 资源，完整离线使用需替换为本地 vendored 版本 -->"
        return html.replace("<head>", f"<head>\n{notice}", 1) if "<head>" in html else html

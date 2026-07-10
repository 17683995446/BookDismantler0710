"""PNG 导出器单元测试。

使用 mock 模拟 Playwright，测试 import 缺失、close、async context manager 等分支。
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from book_dismantler.core.exceptions import ExportError
from book_dismantler.export.png_exporter import PngExporter


class TestPngExporterInit:
    """初始化与配置测试。"""

    def test_default_scale(self) -> None:
        exporter = PngExporter()
        assert exporter.scale == 2.0
        assert exporter._playwright is None
        assert exporter._browser is None

    def test_custom_scale(self) -> None:
        exporter = PngExporter(scale=1.5)
        assert exporter.scale == 1.5


class TestPngExporterImportError:
    """Playwright 未安装时的错误处理。"""

    @pytest.mark.asyncio()
    async def test_import_error_raises_export_error(self) -> None:
        exporter = PngExporter()
        with patch.dict("sys.modules", {"playwright.async_api": None}), \
             pytest.raises(ExportError, match="缺少 playwright"):
            await exporter._ensure_browser()


class TestPngExporterClose:
    """close() 方法测试。"""

    @pytest.mark.asyncio()
    async def test_close_with_no_browser(self) -> None:
        exporter = PngExporter()
        await exporter.close()  # 不应抛异常
        assert exporter._browser is None
        assert exporter._playwright is None

    @pytest.mark.asyncio()
    async def test_close_with_active_browser(self) -> None:
        exporter = PngExporter()
        mock_browser = AsyncMock()
        mock_playwright = AsyncMock()
        exporter._browser = mock_browser
        exporter._playwright = mock_playwright

        await exporter.close()

        mock_browser.close.assert_called_once()
        mock_playwright.stop.assert_called_once()
        assert exporter._browser is None
        assert exporter._playwright is None


class TestPngExporterContextManager:
    """async context manager 测试。"""

    @pytest.mark.asyncio()
    async def test_aenter_returns_self(self) -> None:
        exporter = PngExporter()
        result = await exporter.__aenter__()
        assert result is exporter

    @pytest.mark.asyncio()
    async def test_aexit_calls_close(self) -> None:
        exporter = PngExporter()
        exporter.close = AsyncMock()
        await exporter.__aexit__(None, None, None)
        exporter.close.assert_called_once()


class TestPngExporterExport:
    """export_html_to_png 方法测试（使用 mock playwright）。"""

    @pytest.mark.asyncio()
    async def test_export_html_to_png_success(self, tmp_path: Path) -> None:
        """测试正常导出流程。"""
        exporter = PngExporter(scale=1.5)

        # Mock playwright 链式调用
        mock_page = AsyncMock()
        mock_context = AsyncMock()
        mock_context.new_page = AsyncMock(return_value=mock_page)
        mock_browser = AsyncMock()
        mock_browser.new_context = AsyncMock(return_value=mock_context)

        exporter._browser = mock_browser
        exporter._playwright = AsyncMock()

        output = tmp_path / "output.png"
        result = await exporter.export_html_to_png("<html>test</html>", output)

        assert result == output
        mock_browser.new_context.assert_called_once()
        mock_context.new_page.assert_called_once()
        mock_page.set_content.assert_called_once()
        mock_page.screenshot.assert_called_once()
        mock_context.close.assert_called_once()

    @pytest.mark.asyncio()
    async def test_export_with_selector_not_found(self, tmp_path: Path) -> None:
        """测试选择器未匹配元素时抛出 ExportError。"""
        exporter = PngExporter()
        mock_page = AsyncMock()
        mock_page.query_selector = AsyncMock(return_value=None)
        mock_context = AsyncMock()
        mock_context.new_page = AsyncMock(return_value=mock_page)
        mock_browser = AsyncMock()
        mock_browser.new_context = AsyncMock(return_value=mock_context)

        exporter._browser = mock_browser
        exporter._playwright = AsyncMock()

        with pytest.raises(ExportError, match="未找到选择器"):
            await exporter.export_html_to_png(
                "<html></html>",
                tmp_path / "out.png",
                selector=".nonexistent",
            )

    @pytest.mark.asyncio()
    async def test_export_failure_wraps_error(self, tmp_path: Path) -> None:
        """测试导出失败时包装为 ExportError。"""
        exporter = PngExporter()
        mock_browser = AsyncMock()
        mock_browser.new_context = AsyncMock(side_effect=RuntimeError("browser crash"))

        exporter._browser = mock_browser
        exporter._playwright = AsyncMock()

        with pytest.raises(ExportError, match="PNG 导出失败"):
            await exporter.export_html_to_png("<html></html>", tmp_path / "out.png")

    @pytest.mark.asyncio()
    async def test_export_file_to_png(self, tmp_path: Path) -> None:
        """测试从文件路径导出。"""
        html_file = tmp_path / "input.html"
        html_file.write_text("<html><body>test</body></html>", encoding="utf-8")

        exporter = PngExporter()
        mock_page = AsyncMock()
        mock_context = AsyncMock()
        mock_context.new_page = AsyncMock(return_value=mock_page)
        mock_browser = AsyncMock()
        mock_browser.new_context = AsyncMock(return_value=mock_context)

        exporter._browser = mock_browser
        exporter._playwright = AsyncMock()

        output = tmp_path / "output.png"
        result = await exporter.export_file_to_png(html_file, output)

        assert result == output
        mock_page.set_content.assert_called_once()

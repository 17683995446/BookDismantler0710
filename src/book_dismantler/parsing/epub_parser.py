"""EPUB 解析器：基于 ebooklib + BeautifulSoup。

EPUB 本质是打包的 XHTML，按 spine 顺序提取章节，
通过 h1/h2 标签识别章节/小节结构。
"""

from __future__ import annotations

import warnings
from pathlib import Path
from typing import TYPE_CHECKING

from book_dismantler.core.exceptions import ParseError
from book_dismantler.core.logging import get_logger
from book_dismantler.domain.document import (
    Chapter,
    DocumentFormat,
    Metadata,
    Paragraph,
    ParsedDocument,
    Section,
)

if TYPE_CHECKING:
    from bs4 import BeautifulSoup

# 抑制 BeautifulSoup 用 HTML 解析器解析 XHTML 的警告
try:
    from bs4 import XMLParsedAsHTMLWarning
    warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)
except ImportError:
    pass

logger = get_logger("parsing.epub")


class EpubParser:
    """EPUB 文档解析器。"""

    def parse(self, path: str | Path) -> ParsedDocument:
        """解析 EPUB 文件。

        Args:
            path: EPUB 文件路径。

        Returns:
            包含章节与段落的 ``ParsedDocument``。

        Raises:
            ParseError: 文件不存在或解析失败。
        """
        path = Path(path)
        if not path.exists():
            raise ParseError(f"文件不存在: {path}")

        try:
            import ebooklib
            from bs4 import BeautifulSoup
            from ebooklib import epub
        except ImportError as e:
            raise ParseError(f"缺少 EPUB 解析依赖: {e}") from e

        logger.info("开始解析 EPUB: %s", path.name)

        try:
            book = epub.read_epub(str(path), options={"ignore_ncx": True})
        except Exception as e:
            raise ParseError(f"EPUB 读取失败: {e}") from e

        # 元数据
        metadata = self._extract_metadata(book, path)

        # 按 spine 顺序提取章节内容
        chapters: list[Chapter] = []
        chapter_idx = 0

        for item in book.get_items_of_type(ebooklib.ITEM_DOCUMENT):
            html_content = item.get_content()
            if not html_content:
                continue

            soup = BeautifulSoup(html_content, "lxml")
            ch = self._parse_chapter(soup, chapter_idx)
            if ch and ch.paragraph_count > 0:
                chapters.append(ch)
                chapter_idx += 1

        logger.info(
            "EPUB 解析完成: %d 章, %d 段落",
            len(chapters),
            sum(c.paragraph_count for c in chapters),
        )

        return ParsedDocument(
            metadata=metadata,
            chapters=chapters,
            source_path=str(path),
            source_format=DocumentFormat.EPUB,
        )

    def _extract_metadata(self, book: object, path: Path) -> Metadata:
        """从 ebooklib 读取 DC 元数据。"""
        try:
            from ebooklib import epub

            assert isinstance(book, epub.EpubBook)
            title = book.get_metadata("DC", "title")
            author = book.get_metadata("DC", "creator")
            subject = book.get_metadata("DC", "subject")
            description = book.get_metadata("DC", "description")
            publisher = book.get_metadata("DC", "publisher")
            language = book.get_metadata("DC", "language")

            return Metadata(
                title=title[0][0] if title else path.stem,
                author=author[0][0] if author else "",
                subject=subject[0][0] if subject else "",
                description=description[0][0] if description else "",
                publisher=publisher[0][0] if publisher else "",
                language=language[0][0] if language else "",
            )
        except Exception:
            logger.warning("EPUB 元数据提取失败")
            return Metadata(title=path.stem)

    def _parse_chapter(self, soup: BeautifulSoup, chapter_idx: int) -> Chapter | None:
        """从 BeautifulSoup 解析单个 EPUB 章节文档。

        通过 h1/h2 识别标题，p/div 提取段落。
        """
        title = ""
        h1 = soup.find("h1")
        if h1:
            title = h1.get_text(strip=True)

        sections: list[Section] = []
        current_section_title = title or ""
        current_paragraphs: list[Paragraph] = []
        para_idx = 0

        # 遍历所有块级元素
        for elem in soup.find_all(["h1", "h2", "h3", "p", "div", "li", "blockquote"]):
            text = elem.get_text(strip=True)
            if not text:
                continue

            tag = elem.name.lower()
            if tag in ("h2", "h3"):
                # 新小节
                if current_paragraphs:
                    sections.append(
                        Section(title=current_section_title, paragraphs=current_paragraphs)
                    )
                current_section_title = text
                current_paragraphs = []
                para_idx = 0
            elif tag in ("h1",):
                if not title:
                    title = text
            else:
                # 段落
                current_paragraphs.append(Paragraph(text=text, page=None, index=para_idx))
                para_idx += 1

        # 保存最后一节
        if current_paragraphs:
            sections.append(
                Section(title=current_section_title, paragraphs=current_paragraphs)
            )

        if not sections:
            return None

        return Chapter(
            title=title or f"第{chapter_idx + 1}章",
            sections=sections,
            index=chapter_idx,
        )

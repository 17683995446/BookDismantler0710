"""解析器注册表：按文件扩展名分发到对应解析器。"""

from __future__ import annotations

from pathlib import Path

from book_dismantler.core.exceptions import ParseError
from book_dismantler.domain.document import DocumentFormat
from book_dismantler.parsing.base import Parser
from book_dismantler.parsing.epub_parser import EpubParser
from book_dismantler.parsing.pdf_parser import PdfParser

# 扩展名 → 解析器实例（懒初始化）
_PARSERS: dict[str, Parser] = {}


def _ensure_parsers() -> None:
    """懒初始化解析器实例。"""
    if not _PARSERS:
        pdf = PdfParser()
        epub = EpubParser()
        _PARSERS.update({
            ".pdf": pdf,
            ".epub": epub,
        })


def get_parser_for_file(path: str | Path) -> Parser:
    """根据文件扩展名返回解析器。

    Args:
        path: 文件路径。

    Returns:
        匹配的 ``Parser`` 实例。

    Raises:
        ParseError: 不支持的文件格式。
    """
    _ensure_parsers()
    ext = Path(path).suffix.lower()
    parser = _PARSERS.get(ext)
    if parser is None:
        supported = ", ".join(sorted(_PARSERS.keys()))
        raise ParseError(f"不支持的文件格式 '{ext}'，支持: {supported}")
    return parser


def detect_format(path: str | Path) -> DocumentFormat:
    """检测文件格式。"""
    ext = Path(path).suffix.lower()
    mapping = {
        ".pdf": DocumentFormat.PDF,
        ".epub": DocumentFormat.EPUB,
        ".txt": DocumentFormat.TXT,
    }
    return mapping.get(ext, DocumentFormat.UNKNOWN)

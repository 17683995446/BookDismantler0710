"""文档领域模型：从原始电子书解析出的统一结构。

解析层（PDF/EPUB parser）的输出统一为 ``ParsedDocument``，
后续分块、分析、渲染均以此契约为基础。
"""

from __future__ import annotations

from enum import Enum
from pathlib import Path

from pydantic import BaseModel, Field, model_validator
from typing_extensions import Self


class DocumentFormat(str, Enum):
    """支持的文档格式。"""

    PDF = "pdf"
    EPUB = "epub"
    TXT = "txt"
    UNKNOWN = "unknown"


class Metadata(BaseModel):
    """文档元信息。"""

    title: str = ""
    author: str = ""
    subject: str = ""
    description: str = ""
    publisher: str = ""
    language: str = ""
    total_pages: int | None = None


class Paragraph(BaseModel):
    """段落：最小文本单元，携带页码定位。"""

    text: str = Field(..., min_length=1, description="段落文本内容")
    page: int | None = Field(default=None, ge=0, description="来源页码")
    index: int = Field(..., ge=0, description="章节内段落序号")

    model_config = {"frozen": True}


class Section(BaseModel):
    """小节：章节内子结构。"""

    title: str = ""
    paragraphs: list[Paragraph] = Field(default_factory=list)
    level: int = Field(default=1, ge=1, description="标题层级（1=节，2=子节…）")

    @property
    def text(self) -> str:
        """拼接小节全文。"""
        return "\n\n".join(p.text for p in self.paragraphs)

    @property
    def char_count(self) -> int:
        return len(self.text)


class Chapter(BaseModel):
    """章节：文档顶层组织单元。"""

    title: str
    sections: list[Section] = Field(default_factory=list)
    index: int = Field(..., ge=0, description="章节序号（从 0 开始）")

    @property
    def text(self) -> str:
        """拼接章节全文。"""
        return "\n\n".join(s.text for s in self.sections)

    @property
    def char_count(self) -> int:
        return sum(s.char_count for s in self.sections)

    @property
    def paragraph_count(self) -> int:
        return sum(len(s.paragraphs) for s in self.sections)


class ParsedDocument(BaseModel):
    """解析后的统一文档对象——解析层的核心输出契约。"""

    metadata: Metadata
    chapters: list[Chapter] = Field(default_factory=list)
    source_path: str = ""
    source_format: DocumentFormat = DocumentFormat.UNKNOWN

    @property
    def total_chars(self) -> int:
        return sum(c.char_count for c in self.chapters)

    @property
    def total_paragraphs(self) -> int:
        return sum(c.paragraph_count for c in self.chapters)

    @property
    def chapter_count(self) -> int:
        return len(self.chapters)

    @model_validator(mode="after")
    def validate_chapter_indices(self) -> Self:
        """确保章节序号连续。"""
        for i, ch in enumerate(self.chapters):
            if ch.index != i:
                ch = ch.model_copy(update={"index": i})
                self.chapters[i] = ch
        return self

    def get_all_text(self) -> str:
        """获取全文。"""
        return "\n\n".join(c.text for c in self.chapters)

    @classmethod
    def from_file(cls, path: str | Path) -> ParsedDocument:
        """便捷工厂：按文件扩展名选择解析器。

        Args:
            path: 电子书文件路径。

        Returns:
            解析后的 ``ParsedDocument``。

        Raises:
            ParseError: 格式不支持或解析失败。
        """
        from book_dismantler.parsing.registry import get_parser_for_file

        parser = get_parser_for_file(path)
        return parser.parse(path)

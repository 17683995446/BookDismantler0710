"""领域模型单元测试：document 与 chunk。"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from book_dismantler.domain.chunk import TextChunk
from book_dismantler.domain.document import (
    Chapter,
    DocumentFormat,
    Metadata,
    Paragraph,
    ParsedDocument,
    Section,
)

# ---------------------------------------------------------------------------
# Metadata
# ---------------------------------------------------------------------------

class TestMetadata:
    def test_default_empty(self) -> None:
        m = Metadata()
        assert m.title == ""
        assert m.author == ""

    def test_with_values(self) -> None:
        m = Metadata(title="书名", author="作者", total_pages=100)
        assert m.title == "书名"
        assert m.total_pages == 100


# ---------------------------------------------------------------------------
# Paragraph
# ---------------------------------------------------------------------------

class TestParagraph:
    def test_creation(self) -> None:
        p = Paragraph(text="内容", page=0, index=0)
        assert p.text == "内容"
        assert p.page == 0

    def test_frozen(self) -> None:
        p = Paragraph(text="内容", page=0, index=0)
        with pytest.raises((ValidationError, AttributeError)):
            p.text = "修改"  # type: ignore

    def test_empty_text_rejected(self) -> None:
        with pytest.raises(ValueError):
            Paragraph(text="", page=0, index=0)


# ---------------------------------------------------------------------------
# Section
# ---------------------------------------------------------------------------

class TestSection:
    def test_text_property(self, sample_paragraphs: list[Paragraph]) -> None:
        s = Section(title="节", paragraphs=sample_paragraphs)
        assert "第一段" in s.text
        assert s.char_count > 0

    def test_empty_section(self) -> None:
        s = Section(title="空节")
        assert s.text == ""
        assert s.char_count == 0


# ---------------------------------------------------------------------------
# Chapter
# ---------------------------------------------------------------------------

class TestChapter:
    def test_text_property(self, sample_section: Section) -> None:
        ch = Chapter(title="章", sections=[sample_section], index=0)
        assert "第一段" in ch.text
        assert ch.paragraph_count == 3

    def test_char_count(self, sample_section: Section) -> None:
        ch = Chapter(title="章", sections=[sample_section], index=0)
        assert ch.char_count == sample_section.char_count


# ---------------------------------------------------------------------------
# ParsedDocument
# ---------------------------------------------------------------------------

class TestParsedDocument:
    def test_properties(
        self, sample_parsed_document: ParsedDocument
    ) -> None:
        doc = sample_parsed_document
        assert doc.chapter_count == 1
        assert doc.total_paragraphs == 3
        assert doc.total_chars > 0

    def test_get_all_text(self, sample_parsed_document: ParsedDocument) -> None:
        text = sample_parsed_document.get_all_text()
        assert "第一段" in text
        assert "第三段" in text

    def test_serialization_roundtrip(
        self, sample_parsed_document: ParsedDocument
    ) -> None:
        """序列化→反序列化往返一致性。"""
        json_str = sample_parsed_document.model_dump_json()
        restored = ParsedDocument.model_validate_json(json_str)
        assert restored.metadata.title == sample_parsed_document.metadata.title
        assert restored.chapter_count == sample_parsed_document.chapter_count
        assert restored.chapters[0].title == sample_parsed_document.chapters[0].title

    def test_chapter_index_auto_fix(self) -> None:
        """章节序号不连续时自动修正。"""
        ch0 = Chapter(title="A", sections=[Section(paragraphs=[Paragraph(text="x", index=0)])], index=5)
        doc = ParsedDocument(
            metadata=Metadata(title="t"),
            chapters=[ch0],
        )
        assert doc.chapters[0].index == 0

    def test_source_format_enum(self) -> None:
        assert DocumentFormat.PDF.value == "pdf"
        assert DocumentFormat.EPUB.value == "epub"


# ---------------------------------------------------------------------------
# TextChunk
# ---------------------------------------------------------------------------

class TestTextChunk:
    def test_creation(self) -> None:
        chunk = TextChunk(
            text="测试内容",
            chapter_index=0,
            chapter_title="第一章",
            chunk_index=0,
            token_estimate=10,
            char_count=4,
        )
        assert chunk.text == "测试内容"
        assert chunk.char_count == 4

    def test_auto_char_count(self) -> None:
        chunk = TextChunk(
            text="自动计算字符数",
            chapter_index=0,
            chapter_title="章",
            chunk_index=0,
        )
        assert chunk.char_count == len("自动计算字符数")

    def test_location_label(self) -> None:
        chunk = TextChunk(
            text="内容",
            chapter_index=2,
            chapter_title="第三章 标题",
            section_index=1,
            chunk_index=5,
        )
        label = chunk.location_label
        assert "第三章" in label
        assert "标题" in label
        assert "块#5" in label

    def test_frozen(self) -> None:
        chunk = TextChunk(
            text="x", chapter_index=0, chapter_title="", chunk_index=0
        )
        with pytest.raises((ValidationError, AttributeError)):
            chunk.text = "y"  # type: ignore

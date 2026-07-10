"""集成测试：真实文件解析全链路。"""

from __future__ import annotations

from pathlib import Path

from book_dismantler.domain.document import DocumentFormat, ParsedDocument
from book_dismantler.parsing.chunker import Chunker
from book_dismantler.parsing.epub_parser import EpubParser
from book_dismantler.parsing.pdf_parser import PdfParser


class TestPdfIntegration:
    """PDF 端到端解析集成测试。"""

    def test_pdf_parse_and_chunk(self, sample_pdf_path: Path) -> None:
        """PDF 解析 → 分块完整链路。"""
        parser = PdfParser()
        doc = parser.parse(sample_pdf_path)

        # 断言解析结果
        assert doc.source_format == DocumentFormat.PDF
        assert doc.chapter_count >= 1
        assert doc.total_paragraphs >= 2

        # 断言分块
        chunker = Chunker(chunk_size=2000, overlap=100)
        chunks = chunker.chunk_document(doc)
        assert len(chunks) >= 1
        assert all(c.char_count > 0 for c in chunks)

    def test_pdf_serialization_roundtrip(self, sample_pdf_path: Path) -> None:
        """PDF 解析结果可序列化往返。"""
        doc = PdfParser().parse(sample_pdf_path)
        json_str = doc.model_dump_json()
        restored = ParsedDocument.model_validate_json(json_str)

        assert restored.metadata.title == doc.metadata.title
        assert restored.chapter_count == doc.chapter_count
        assert restored.total_paragraphs == doc.total_paragraphs


class TestEpubIntegration:
    """EPUB 端到端解析集成测试。"""

    def test_epub_parse_and_chunk(self, sample_epub_path: Path) -> None:
        """EPUB 解析 → 分块完整链路。"""
        parser = EpubParser()
        doc = parser.parse(sample_epub_path)

        assert doc.source_format == DocumentFormat.EPUB
        assert doc.chapter_count >= 1
        assert doc.total_paragraphs >= 2

        chunker = Chunker(chunk_size=2000, overlap=100)
        chunks = chunker.chunk_document(doc)
        assert len(chunks) >= 1

    def test_epub_metadata_extracted(self, sample_epub_path: Path) -> None:
        """EPUB 元数据正确提取。"""
        doc = EpubParser().parse(sample_epub_path)
        assert doc.metadata.title != ""
        assert doc.metadata.author != ""


class TestCrossFormatIntegration:
    """跨格式一致性测试。"""

    def test_both_formats_produce_valid_doc(
        self, sample_pdf_path: Path, sample_epub_path: Path
    ) -> None:
        """PDF 和 EPUB 都产出合法 ParsedDocument。"""
        pdf_doc = PdfParser().parse(sample_pdf_path)
        epub_doc = EpubParser().parse(sample_epub_path)

        for doc in [pdf_doc, epub_doc]:
            assert isinstance(doc, ParsedDocument)
            assert doc.chapter_count > 0
            assert doc.total_chars > 0
            # 可序列化
            json_str = doc.model_dump_json()
            assert len(json_str) > 10

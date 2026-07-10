"""pytest 全局配置与公共 fixture。"""

from __future__ import annotations

from pathlib import Path

import pytest

from book_dismantler.domain.document import (
    Chapter,
    DocumentFormat,
    Metadata,
    Paragraph,
    ParsedDocument,
    Section,
)

# ---------------------------------------------------------------------------
# 数据 fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def sample_metadata() -> Metadata:
    """标准测试元数据。"""
    return Metadata(
        title="测试之书",
        author="测试作者",
        subject="测试主题",
        language="zh",
        total_pages=10,
    )


@pytest.fixture
def sample_paragraphs() -> list[Paragraph]:
    """测试段落列表。"""
    return [
        Paragraph(text="这是第一段内容，用于测试。", page=0, index=0),
        Paragraph(text="第二段继续讲述，包含更多信息。", page=0, index=1),
        Paragraph(text="第三段是关于知识管理的核心观点。", page=1, index=2),
    ]


@pytest.fixture
def sample_section(sample_paragraphs: list[Paragraph]) -> Section:
    """测试小节。"""
    return Section(title="引言", paragraphs=sample_paragraphs, level=1)


@pytest.fixture
def sample_chapter(sample_section: Section) -> Chapter:
    """测试章节。"""
    return Chapter(
        title="第一章 测试",
        sections=[sample_section],
        index=0,
    )


@pytest.fixture
def sample_parsed_document(
    sample_metadata: Metadata, sample_chapter: Chapter
) -> ParsedDocument:
    """完整测试文档。"""
    return ParsedDocument(
        metadata=sample_metadata,
        chapters=[sample_chapter],
        source_path="/tmp/test.pdf",
        source_format=DocumentFormat.PDF,
    )


# ---------------------------------------------------------------------------
# 文件 fixtures：生成真实样本 PDF / EPUB
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def sample_pdf_path(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """生成一个真实的测试 PDF 文件。"""
    return _generate_sample_pdf(tmp_path_factory.mktemp("pdf"))


@pytest.fixture(scope="session")
def sample_epub_path(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """生成一个真实的测试 EPUB 文件。"""
    return _generate_sample_epub(tmp_path_factory.mktemp("epub"))


def _generate_sample_pdf(directory: Path) -> Path:
    """用 reportlab 生成测试 PDF（若不可用则用 fpdf2，再不可用则跳过）。"""
    path = directory / "sample.pdf"
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.pdfgen import canvas

        c = canvas.Canvas(str(path), pagesize=A4)
        c.setTitle("测试PDF之书")
        c.setAuthor("测试作者")

        # 第一页
        c.drawString(100, 750, "第一章 测试章节")
        c.drawString(100, 720, "这是第一段内容，讲述关于知识管理的基本概念。")
        c.drawString(100, 700, "第二段继续阐述，知识管理是组织能力的核心。")
        c.drawString(100, 680, "第三段补充说明，知识的获取与应用同等重要。")
        c.showPage()

        # 第二页
        c.drawString(100, 750, "第二章 深入分析")
        c.drawString(100, 720, "本章深入讨论知识管理的实践方法。")
        c.drawString(100, 700, "首先，我们需要建立知识分类体系。")
        c.drawString(100, 680, "其次，工具的选择至关重要。")
        c.showPage()

        c.save()
        return path
    except ImportError:
        pass

    # 回退：用 fpdf2
    try:
        from fpdf import FPDF

        pdf = FPDF()
        pdf.set_title("测试PDF之书")
        pdf.set_author("测试作者")
        pdf.add_page()
        pdf.set_font_size(16)
        pdf.cell(0, 10, "第一章 测试章节", ln=True)
        pdf.set_font_size(10)
        pdf.cell(0, 10, "这是第一段内容，讲述关于知识管理的基本概念。", ln=True)
        pdf.cell(0, 10, "第二段继续阐述，知识管理是组织能力的核心。", ln=True)
        pdf.cell(0, 10, "第三段补充说明，知识的获取与应用同等重要。", ln=True)
        pdf.add_page()
        pdf.set_font_size(16)
        pdf.cell(0, 10, "第二章 深入分析", ln=True)
        pdf.set_font_size(10)
        pdf.cell(0, 10, "本章深入讨论知识管理的实践方法。", ln=True)
        pdf.cell(0, 10, "首先，我们需要建立知识分类体系。", ln=True)
        pdf.cell(0, 10, "其次，工具的选择至关重要。", ln=True)
        pdf.output(str(path))
        return path
    except ImportError:
        pytest.skip("需要 reportlab 或 fpdf2 来生成测试 PDF")


def _generate_sample_epub(directory: Path) -> Path:
    """用 ebooklib 生成测试 EPUB。"""
    try:
        from ebooklib import epub

    except ImportError:
        pytest.skip("需要 ebooklib 来生成测试 EPUB")

    book = epub.EpubBook()
    book.set_identifier("test-id-001")
    book.set_title("测试EPUB之书")
    book.set_language("zh")
    book.add_author("测试作者")

    # 第一章
    ch1 = epub.EpubHtml(title="第一章", file_name="ch1.xhtml", lang="zh")
    ch1.content = """
<html><body>
<h1>第一章 知识基础</h1>
<h2>引言</h2>
<p>这是第一段内容，讲述关于知识管理的基本概念。</p>
<p>第二段继续阐述，知识管理是组织能力的核心。</p>
<p>第三段补充说明，知识的获取与应用同等重要。</p>
<h2>核心概念</h2>
<p>知识管理涉及知识的创建、存储、共享和应用。</p>
</body></html>
"""
    book.add_item(ch1)

    # 第二章
    ch2 = epub.EpubHtml(title="第二章", file_name="ch2.xhtml", lang="zh")
    ch2.content = """
<html><body>
<h1>第二章 深入分析</h1>
<h2>实践方法</h2>
<p>本章深入讨论知识管理的实践方法。</p>
<p>首先，我们需要建立知识分类体系。</p>
<p>其次，工具的选择至关重要。</p>
</body></html>
"""
    book.add_item(ch2)

    # spine
    book.spine = [ch1, ch2]

    # NCX / Nav
    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())

    path = directory / "sample.epub"
    epub.write_epub(str(path), book, {})
    return path


@pytest.fixture
def knowledge_model_json(sample_parsed_document: ParsedDocument) -> str:
    """序列化后的 ParsedDocument JSON（往返测试用）。"""
    return sample_parsed_document.model_dump_json()

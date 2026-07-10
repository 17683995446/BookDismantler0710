"""提示词加载与渲染测试。"""

from __future__ import annotations

import pytest

from book_dismantler.analysis.prompts import list_templates, render_prompt
from book_dismantler.core.exceptions import ConfigError


class TestPromptLoading:
    """提示词模板加载测试。"""

    def test_list_templates(self) -> None:
        templates = list_templates()
        assert "outline_extraction.j2" in templates
        assert "concept_extraction.j2" in templates
        assert "relationship_mining.j2" in templates
        assert "concept_anatomy.j2" in templates

    def test_render_outline(self) -> None:
        result = render_prompt(
            "outline_extraction.j2",
            book_title="测试书",
            chapter_title="第一章",
            content="这是内容",
        )
        assert "测试书" in result
        assert "第一章" in result
        assert "这是内容" in result
        assert "JSON" in result

    def test_render_concept(self) -> None:
        result = render_prompt(
            "concept_extraction.j2",
            book_title="书名",
            chapter_title="章名",
            content="内容",
        )
        assert "concepts" in result
        assert "书名" in result

    def test_render_anatomy(self) -> None:
        result = render_prompt(
            "concept_anatomy.j2",
            concept="知识管理",
            content="相关内容",
        )
        assert "知识管理" in result
        assert "definition" in result
        assert "characteristics" in result

    def test_render_with_default_values(self) -> None:
        """未传变量时使用默认值。"""
        result = render_prompt("outline_extraction.j2", content="内容")
        assert "内容" in result
        assert "未知" in result  # default value

    def test_render_nonexistent_template(self) -> None:
        with pytest.raises(ConfigError, match="加载提示词模板"):
            render_prompt("nonexistent.j2")

    def test_render_relationship(self) -> None:
        result = render_prompt(
            "relationship_mining.j2",
            concepts="概念A, 概念B",
            content="内容",
        )
        assert "概念A" in result
        assert "relationships" in result

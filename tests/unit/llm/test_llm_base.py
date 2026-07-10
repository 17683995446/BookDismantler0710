"""LLM 层单元测试：base 模型、消息构建、JSON 解析、重试。"""

from __future__ import annotations

import pytest

from book_dismantler.core.exceptions import LLMError
from book_dismantler.llm.base import LLMClient, Message, StructuredResponse, Usage
from book_dismantler.llm.messages import (
    build_messages,
    parse_json_response,
    wrap_schema_instruction,
)
from book_dismantler.llm.retry import is_retryable_error, retry_with_backoff

# ---------------------------------------------------------------------------
# 数据模型
# ---------------------------------------------------------------------------

class TestMessage:
    def test_creation(self) -> None:
        m = Message(role="user", content="你好")
        assert m.role == "user"
        assert m.content == "你好"


class TestUsage:
    def test_defaults(self) -> None:
        u = Usage()
        assert u.prompt_tokens == 0
        assert u.total_tokens == 0

    def test_with_values(self) -> None:
        u = Usage(prompt_tokens=100, completion_tokens=50, total_tokens=150)
        assert u.total_tokens == 150


class TestStructuredResponse:
    def test_text_only(self) -> None:
        r = StructuredResponse(raw_content="纯文本")
        assert not r.is_structured
        assert r.parsed is None

    def test_structured(self) -> None:
        r = StructuredResponse(raw_content='{"a": 1}', parsed={"a": 1})
        assert r.is_structured
        assert r.parsed["a"] == 1


# ---------------------------------------------------------------------------
# 消息构建
# ---------------------------------------------------------------------------

class TestBuildMessages:
    def test_basic(self) -> None:
        msgs = build_messages("你是助手", "你好")
        assert len(msgs) == 2
        assert msgs[0].role == "system"
        assert msgs[1].role == "user"
        assert "你好" in msgs[1].content

    def test_with_context(self) -> None:
        msgs = build_messages("系统", "分析", context="这是上下文")
        assert len(msgs) == 2
        assert "上下文" in msgs[1].content
        assert "分析" in msgs[1].content


# ---------------------------------------------------------------------------
# JSON 解析
# ---------------------------------------------------------------------------

class TestParseJsonResponse:
    def test_pure_json(self) -> None:
        result = parse_json_response('{"key": "value"}')
        assert result["key"] == "value"

    def test_json_in_code_block(self) -> None:
        raw = '```json\n{"key": "value"}\n```'
        result = parse_json_response(raw)
        assert result["key"] == "value"

    def test_json_with_surrounding_text(self) -> None:
        raw = '这是结果：\n{"key": "value"}\n以上是结果。'
        result = parse_json_response(raw)
        assert result["key"] == "value"

    def test_invalid_json_raises(self) -> None:
        with pytest.raises(LLMError, match="无法从响应中解析"):
            parse_json_response("这不是JSON")

    def test_nested_json(self) -> None:
        raw = '{"a": {"b": [1, 2, 3]}}'
        result = parse_json_response(raw)
        assert result["a"]["b"] == [1, 2, 3]


# ---------------------------------------------------------------------------
# Schema 注入
# ---------------------------------------------------------------------------

class TestWrapSchemaInstruction:
    def test_appends_schema(self) -> None:
        schema = {"type": "object", "properties": {"name": {"type": "string"}}}
        result = wrap_schema_instruction("分析这段内容", schema)
        assert "分析这段内容" in result
        assert "JSON" in result
        assert "name" in result


# ---------------------------------------------------------------------------
# 重试逻辑
# ---------------------------------------------------------------------------

class TestRetry:
    def test_is_retryable_rate_limit(self) -> None:
        exc = Exception("rate limit exceeded")
        assert is_retryable_error(exc) is True

    def test_is_retryable_timeout(self) -> None:
        exc = Exception("connection timeout")
        assert is_retryable_error(exc) is True

    def test_not_retryable_business_error(self) -> None:
        from book_dismantler.core.exceptions import LLMError

        exc = LLMError("业务错误")
        # LLMError 在 retry 中直接抛出，不进入 is_retryable
        assert is_retryable_error(exc) is False

    def test_not_retryable_auth_error(self) -> None:
        exc = Exception("invalid api key")
        assert is_retryable_error(exc) is False

    def test_retry_succeeds_on_second_attempt(self) -> None:
        call_count = 0

        @retry_with_backoff(max_retries=3, base_delay=0.01)
        def flaky_func() -> str:
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise Exception("rate limit error")
            return "success"

        result = flaky_func()
        assert result == "success"
        assert call_count == 2

    def test_retry_exhausted_raises_llm_error(self) -> None:
        @retry_with_backoff(max_retries=2, base_delay=0.01)
        def always_fail() -> str:
            raise Exception("server error")

        with pytest.raises(LLMError, match="LLM 调用失败"):
            always_fail()

    def test_llm_error_not_retried(self) -> None:
        call_count = 0

        @retry_with_backoff(max_retries=3, base_delay=0.01)
        def business_error() -> str:
            nonlocal call_count
            call_count += 1
            raise LLMError("业务异常")

        with pytest.raises(LLMError):
            business_error()
        assert call_count == 1  # 不重试


# ---------------------------------------------------------------------------
# Protocol 验证
# ---------------------------------------------------------------------------

class TestProtocol:
    def test_openai_provider_is_llm_client(self) -> None:
        from book_dismantler.llm.providers.openai_provider import OpenAICompatibleProvider

        provider = OpenAICompatibleProvider(
            api_key="test", base_url="http://test", model="test"
        )
        assert isinstance(provider, LLMClient)

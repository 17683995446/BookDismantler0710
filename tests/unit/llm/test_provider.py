"""Provider 与工厂测试：mock HTTP 验证请求构造与响应解析。"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from book_dismantler.core.config import Settings
from book_dismantler.core.exceptions import ConfigError, LLMError
from book_dismantler.llm.base import Message, StructuredResponse
from book_dismantler.llm.factory import create_client
from book_dismantler.llm.providers.openai_provider import OpenAICompatibleProvider

# ---------------------------------------------------------------------------
# OpenAICompatibleProvider
# ---------------------------------------------------------------------------

class TestOpenAICompatibleProvider:
    """Provider 单元测试。"""

    def test_init_validates_params(self) -> None:
        with pytest.raises(LLMError, match="api_key"):
            OpenAICompatibleProvider(api_key="", base_url="http://x", model="m")
        with pytest.raises(LLMError, match="base_url"):
            OpenAICompatibleProvider(api_key="k", base_url="", model="m")
        with pytest.raises(LLMError, match="model"):
            OpenAICompatibleProvider(api_key="k", base_url="http://x", model="")

    def test_repr(self) -> None:
        p = OpenAICompatibleProvider(api_key="k", base_url="http://x", model="m")
        assert "m" in repr(p)
        assert "http://x" in repr(p)

    def test_complete_text_only(self) -> None:
        """无 schema 时返回纯文本。"""
        provider = OpenAICompatibleProvider(
            api_key="test-key", base_url="http://test", model="test-model"
        )

        # Mock openai client
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "Hello world"
        mock_response.choices[0].finish_reason = "stop"
        mock_response.usage = MagicMock(
            prompt_tokens=10, completion_tokens=5, total_tokens=15
        )
        mock_client.chat.completions.create.return_value = mock_response
        provider._client = mock_client

        result = provider.complete([Message(role="user", content="Hi")])

        assert isinstance(result, StructuredResponse)
        assert result.raw_content == "Hello world"
        assert result.parsed is None
        assert result.usage.total_tokens == 15
        assert result.model == "test-model"

    def test_complete_with_schema(self) -> None:
        """有 schema 时尝试解析 JSON。"""
        provider = OpenAICompatibleProvider(
            api_key="test-key", base_url="http://test", model="test-model"
        )

        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = '{"name": "测试", "value": 42}'
        mock_response.choices[0].finish_reason = "stop"
        mock_response.usage = None
        mock_client.chat.completions.create.return_value = mock_response
        provider._client = mock_client

        schema = {"type": "object", "properties": {"name": {"type": "string"}}}
        result = provider.complete(
            [Message(role="user", content="分析")],
            response_schema=schema,
        )

        assert result.is_structured
        assert result.parsed["name"] == "测试"
        assert result.parsed["value"] == 42

    def test_complete_with_json_code_block(self) -> None:
        """响应包裹在 ```json 中也能解析。"""
        provider = OpenAICompatibleProvider(
            api_key="k", base_url="http://x", model="m"
        )

        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = (
            '```json\n{"key": "value"}\n```'
        )
        mock_response.choices[0].finish_reason = "stop"
        mock_response.usage = None
        mock_client.chat.completions.create.return_value = mock_response
        provider._client = mock_client

        result = provider.complete(
            [Message(role="user", content="x")],
            response_schema={"type": "object"},
        )
        assert result.parsed["key"] == "value"

    def test_complete_invalid_json_falls_back(self) -> None:
        """JSON 解析失败时 parsed 为 None，raw_content 保留。"""
        provider = OpenAICompatibleProvider(
            api_key="k", base_url="http://x", model="m"
        )

        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "这不是JSON"
        mock_response.choices[0].finish_reason = "stop"
        mock_response.usage = None
        mock_client.chat.completions.create.return_value = mock_response
        provider._client = mock_client

        result = provider.complete(
            [Message(role="user", content="x")],
            response_schema={"type": "object"},
        )
        assert not result.is_structured
        assert result.raw_content == "这不是JSON"

    def test_complete_request_failure_raises(self) -> None:
        """请求失败抛出 LLMError。"""
        provider = OpenAICompatibleProvider(
            api_key="k", base_url="http://x", model="m"
        )

        mock_client = MagicMock()
        mock_client.chat.completions.create.side_effect = Exception("connection error")
        provider._client = mock_client

        with pytest.raises(LLMError):
            provider.complete([Message(role="user", content="x")])

    def test_complete_passes_temperature_and_max_tokens(self) -> None:
        """验证 temperature 和 max_tokens 传递。"""
        provider = OpenAICompatibleProvider(
            api_key="k", base_url="http://x", model="m"
        )

        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "ok"
        mock_response.choices[0].finish_reason = "stop"
        mock_response.usage = None
        mock_client.chat.completions.create.return_value = mock_response
        provider._client = mock_client

        provider.complete(
            [Message(role="user", content="x")],
            temperature=0.7,
            max_tokens=500,
        )

        call_kwargs = mock_client.chat.completions.create.call_args.kwargs
        assert call_kwargs["temperature"] == 0.7
        assert call_kwargs["max_tokens"] == 500


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

class TestFactory:
    """工厂测试。"""

    def test_create_client_deepseek(self, tmp_path) -> None:
        settings = Settings(
            output_dir=tmp_path,
            default_provider="deepseek",
            deepseek_api_key="sk-test",
        )
        client = create_client(settings=settings)
        assert isinstance(client, OpenAICompatibleProvider)
        assert client.api_key == "sk-test"

    def test_create_client_openai(self, tmp_path) -> None:
        settings = Settings(
            output_dir=tmp_path,
            default_provider="openai",
            openai_api_key="sk-openai",
        )
        client = create_client(settings=settings)
        assert client.api_key == "sk-openai"

    def test_create_client_ollama_no_key_required(self, tmp_path) -> None:
        settings = Settings(
            output_dir=tmp_path,
            default_provider="ollama",
        )
        client = create_client(settings=settings)
        assert client.base_url == "http://localhost:11434/v1"

    def test_create_client_missing_key_raises(self, tmp_path) -> None:
        settings = Settings(
            output_dir=tmp_path,
            default_provider="deepseek",
            deepseek_api_key="",
        )
        with pytest.raises(ConfigError, match="缺少 API key"):
            create_client(settings=settings)

    def test_create_client_unknown_provider(self, tmp_path) -> None:
        settings = Settings(output_dir=tmp_path)
        with pytest.raises(ConfigError):
            create_client(provider="nonexistent", settings=settings)

    def test_create_client_custom_model(self, tmp_path) -> None:
        settings = Settings(
            output_dir=tmp_path,
            default_provider="deepseek",
            deepseek_api_key="sk-test",
        )
        client = create_client(model="custom-model", settings=settings)
        assert client.model == "custom-model"

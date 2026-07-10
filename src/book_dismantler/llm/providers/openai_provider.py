"""OpenAI 兼容 Provider：统一适配 OpenAI/DeepSeek/Gemini/Ollama。

四个目标 provider 均兼容 OpenAI Chat Completions API，
只需配置不同的 base_url 和 api_key，因此用单一实现覆盖。
"""

from __future__ import annotations

import threading
from typing import Any

from book_dismantler.core.exceptions import LLMError
from book_dismantler.core.logging import get_logger
from book_dismantler.llm.base import LLMClient, Message, StructuredResponse, Usage
from book_dismantler.llm.messages import parse_json_response, wrap_schema_instruction
from book_dismantler.llm.retry import retry_with_backoff

logger = get_logger("llm.openai_provider")


class OpenAICompatibleProvider:
    """OpenAI 兼容的 LLM 客户端。

    适配所有兼容 OpenAI Chat Completions API 的 provider：
    OpenAI、DeepSeek、Gemini（OpenAI 兼容端点）、Ollama。

    Attributes:
        api_key: API 密钥。
        base_url: API 端点。
        model: 默认模型名。
        timeout: 请求超时秒数。
        max_retries: 最大重试次数。
    """

    def __init__(
        self,
        api_key: str,
        base_url: str,
        model: str,
        *,
        timeout: int = 120,
        max_retries: int = 3,
    ) -> None:
        if not api_key:
            raise LLMError("api_key 不能为空")
        if not base_url:
            raise LLMError("base_url 不能为空")
        if not model:
            raise LLMError("model 不能为空")

        self.api_key = api_key
        self.base_url = base_url
        self.model = model
        self.timeout = timeout
        self.max_retries = max_retries
        self._client: Any = None
        self._client_lock = threading.Lock()

    def _get_client(self) -> Any:
        """懒初始化 openai 客户端（线程安全）。"""
        if self._client is None:
            with self._client_lock:
                # 双重检查：可能在等待锁期间已被其他线程初始化
                if self._client is not None:
                    return self._client
                try:
                    from openai import OpenAI
                except ImportError as e:
                    raise LLMError(f"缺少 openai 依赖: {e}") from e

                self._client = OpenAI(
                    api_key=self.api_key,
                    base_url=self.base_url,
                    timeout=self.timeout,
                )
        return self._client

    def complete(
        self,
        messages: list[Message],
        *,
        response_schema: dict[str, Any] | None = None,
        temperature: float = 0.3,
        max_tokens: int | None = None,
    ) -> StructuredResponse:
        """发送聊天请求并返回结构化响应。

        Args:
            messages: 消息列表。
            response_schema: 期望输出的 JSON Schema。
            temperature: 采样温度。
            max_tokens: 最大输出 token 数。

        Returns:
            ``StructuredResponse``。

        Raises:
            LLMError: 调用失败。
        """
        client = self._get_client()

        # 构建请求参数
        request_messages = [
            {"role": m.role, "content": m.content} for m in messages
        ]

        # 如果指定了 schema，在最后一条 user 消息中追加约束
        if response_schema is not None:
            request_messages = self._inject_schema(
                request_messages, response_schema
            )

        kwargs: dict[str, Any] = {
            "model": self.model,
            "messages": request_messages,
            "temperature": temperature,
        }
        if max_tokens is not None:
            kwargs["max_tokens"] = max_tokens

        # 注意：不使用 response_format={"type": "json_object"}
        # 部分 provider（如硅基流动）对此支持不佳，会导致空响应或异常输出。
        # 改为通过提示词约束输出格式，parse_json_response 负责提取。

        @retry_with_backoff(
            max_retries=self.max_retries,
            base_delay=1.0,
            max_delay=30.0,
        )
        def _do_request() -> Any:
            return client.chat.completions.create(**kwargs)

        try:
            response = _do_request()
        except LLMError:
            raise
        except Exception as exc:
            raise LLMError(f"LLM 请求失败: {exc}") from exc

        return self._parse_response(response, response_schema)

    def _inject_schema(
        self,
        messages: list[dict[str, str]],
        schema: dict[str, Any],
    ) -> list[dict[str, str]]:
        """在最后一条 user 消息中注入 schema 约束。"""
        if not messages:
            return messages

        result = list(messages)
        last = result[-1]
        if last["role"] == "user":
            result[-1] = {
                "role": "user",
                "content": wrap_schema_instruction(last["content"], schema),
            }
        else:
            # 如果最后不是 user 消息，追加一条
            result.append({
                "role": "user",
                "content": wrap_schema_instruction("请输出符合上述 Schema 的 JSON。", schema),
            })
        return result

    def _parse_response(
        self,
        response: Any,
        schema: dict[str, Any] | None,
    ) -> StructuredResponse:
        """解析 OpenAI 响应为 StructuredResponse。"""
        try:
            choice = response.choices[0]
            raw_content = choice.message.content or ""
            finish_reason = choice.finish_reason or "stop"

            # token 用量
            usage_data = getattr(response, "usage", None)
            usage = Usage()
            if usage_data:
                usage = Usage(
                    prompt_tokens=getattr(usage_data, "prompt_tokens", 0),
                    completion_tokens=getattr(usage_data, "completion_tokens", 0),
                    total_tokens=getattr(usage_data, "total_tokens", 0),
                )

            # 解析 JSON
            parsed: dict[str, Any] | None = None
            if schema is not None and raw_content:
                try:
                    parsed = parse_json_response(raw_content)
                except LLMError as e:
                    logger.warning("JSON 解析失败: %s", e)
                    parsed = None

            return StructuredResponse(
                raw_content=raw_content,
                parsed=parsed,
                usage=usage,
                model=self.model,
                finish_reason=finish_reason,
            )

        except (IndexError, AttributeError) as e:
            raise LLMError(f"响应解析失败: {e}") from e

    def __repr__(self) -> str:
        return (
            f"OpenAICompatibleProvider("
            f"model={self.model!r}, base_url={self.base_url!r})"
        )


# 验证实现 LLMClient Protocol
assert isinstance(  # noqa: S101
    OpenAICompatibleProvider(
        api_key="test", base_url="http://test", model="test"
    ),
    LLMClient,
)

"""LLM 客户端抽象接口与数据模型。

所有 provider 实现此 Protocol，保证可替换性。
结构化输出通过 JSON schema 约束 + 解析校验实现。
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from pydantic import BaseModel, Field


class Message(BaseModel):
    """聊天消息。"""

    role: str = Field(..., description="角色：system/user/assistant")
    content: str = Field(..., description="消息内容")


class Usage(BaseModel):
    """token 用量统计。"""

    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0

    model_config = {"frozen": True}


class StructuredResponse(BaseModel):
    """LLM 结构化响应。

    当请求指定 response_schema 时，parsed 为解析后的 dict；
    否则 parsed 为 None，使用 raw_content。
    """

    model_config = {"extra": "forbid"}

    raw_content: str = Field(..., description="原始文本响应")
    parsed: dict[str, Any] | None = Field(
        default=None, description="JSON 解析结果（若有）"
    )
    usage: Usage = Field(default_factory=Usage)
    model: str = Field(default="", description="实际使用的模型名")
    finish_reason: str = Field(default="stop")

    @property
    def is_structured(self) -> bool:
        """是否成功解析为结构化数据。"""
        return self.parsed is not None


@runtime_checkable
class LLMClient(Protocol):
    """LLM 客户端协议。

    所有 provider（OpenAI/DeepSeek/Gemini/Ollama）实现此接口。
    """

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
            response_schema: JSON Schema 描述期望的输出结构。
                为 None 时返回纯文本。
            temperature: 采样温度。
            max_tokens: 最大输出 token 数。

        Returns:
            ``StructuredResponse``，含原始文本与可选解析结果。

        Raises:
            LLMError: 调用失败。
        """
        ...

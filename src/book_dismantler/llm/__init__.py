"""LLM 集成层：可插拔 provider 抽象 + 结构化输出。"""

from book_dismantler.llm.base import LLMClient, Message, StructuredResponse, Usage
from book_dismantler.llm.factory import create_client

__all__ = [
    "LLMClient",
    "Message",
    "StructuredResponse",
    "Usage",
    "create_client",
]

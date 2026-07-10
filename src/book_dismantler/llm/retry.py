"""LLM 请求重试与错误处理。

提供指数退避重试装饰器，处理 429（限流）和 5xx（服务端错误）。
"""

from __future__ import annotations

import functools
import time
from collections.abc import Callable
from typing import Any, TypeVar

from book_dismantler.core.exceptions import LLMError
from book_dismantler.core.logging import get_logger

logger = get_logger("llm.retry")

T = TypeVar("T")

# 可重试的 HTTP 状态码
_RETRYABLE_STATUS = {429, 500, 502, 503, 504}


def is_retryable_error(exc: Exception) -> bool:
    """判断异常是否可重试。"""
    exc_str = str(exc).lower()

    # openai SDK 异常
    if hasattr(exc, "status_code"):
        status = getattr(exc, "status_code", 0)
        if status in _RETRYABLE_STATUS:
            return True

    # 常见可重试错误信息
    retryable_keywords = [
        "rate limit",
        "timeout",
        "connection error",
        "server error",
        "service unavailable",
        "too many requests",
        "overloaded",
    ]
    return any(kw in exc_str for kw in retryable_keywords)


def retry_with_backoff(
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """指数退避重试装饰器。

    Args:
        max_retries: 最大重试次数（不含首次）。
        base_delay: 初始延迟秒数。
        max_delay: 最大延迟秒数。

    Returns:
        装饰后的函数。
    """

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> T:
            last_exc: Exception | None = None

            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except LLMError:
                    raise  # 业务异常不重试
                except Exception as exc:
                    last_exc = exc
                    if attempt >= max_retries or not is_retryable_error(exc):
                        raise LLMError(
                            f"LLM 调用失败（第 {attempt + 1} 次）: {exc}"
                        ) from exc

                    delay = min(base_delay * (2**attempt), max_delay)
                    logger.warning(
                        "LLM 调用失败（第 %d/%d 次），%0.1fs 后重试: %s",
                        attempt + 1,
                        max_retries + 1,
                        delay,
                        exc,
                    )
                    time.sleep(delay)

            # 理论上不会到达
            raise LLMError(f"LLM 调用重试耗尽: {last_exc}") from last_exc

        return wrapper

    return decorator

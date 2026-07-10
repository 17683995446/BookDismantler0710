"""结构化日志配置。

基于标准库 logging，提供统一格式与可配置级别。
通过 ``setup_logging`` 在应用入口初始化。
支持 context binding（trace_id / job_id / book_id）用于链路追踪。
"""

from __future__ import annotations

import logging
import sys
import uuid
from contextvars import ContextVar
from typing import Any, Final

_DEFAULT_FORMAT: Final[str] = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
_DATE_FORMAT: Final[str] = "%Y-%m-%d %H:%M:%S"

# Context vars: 在异步/多线程环境中隔离每个请求/任务的上下文
_trace_id_var: ContextVar[str | None] = ContextVar("trace_id", default=None)

_CONFIGURED: bool = False


class _ContextFilter(logging.Filter):
    """为日志记录注入 trace_id。"""

    def filter(self, record: logging.LogRecord) -> bool:
        record.trace_id = _trace_id_var.get() or "-"
        return True


class _JsonFormatter(logging.Formatter):
    """F4: 结构化 JSON 格式化器（生产环境推荐）。

    适用于 ELK/Loki 等日志聚合系统。
    输出格式：{"ts":"2026-01-01T00:00:00","level":"INFO","logger":"...","message":"...","trace_id":"..."}
    额外的 extra 字段（如 job_id、book_id）会自动展开到顶层。
    """

    # 保留字：不能放进 extras 的标准 LogRecord 字段
    _RESERVED = frozenset({
        "name", "msg", "args", "levelname", "levelno", "pathname", "filename",
        "module", "exc_info", "exc_text", "stack_info", "lineno", "funcName",
        "created", "msecs", "relativeCreated", "thread", "threadName",
        "processName", "process", "message", "asctime", "trace_id",
    })

    def format(self, record: logging.LogRecord) -> str:
        import json
        from datetime import datetime, timezone

        payload: dict[str, Any] = {
            "ts": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        # 注入 trace_id
        tid = getattr(record, "trace_id", None)
        if tid and tid != "-":
            payload["trace_id"] = tid
        # 注入 extras
        for key, value in record.__dict__.items():
            if key not in self._RESERVED and not key.startswith("_"):
                try:
                    json.dumps(value)
                    payload[key] = value
                except (TypeError, ValueError):
                    payload[key] = str(value)
        # 异常
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)


class ContextLoggerAdapter(logging.LoggerAdapter):
    """支持上下文绑定的 logger 适配器。

    用法::
        log = get_logger("api")
        log = log.bind(job_id="abc123")
        log.info("开始处理")  # 输出携带 job_id=abc123
    """

    def __init__(self, logger: logging.Logger, extra: dict[str, Any] | None = None) -> None:
        super().__init__(logger, extra or {})

    def bind(self, **kwargs: Any) -> ContextLoggerAdapter:
        """绑定额外的上下文字段，返回新实例。"""
        new_extra = {**(self.extra or {}), **kwargs}
        return ContextLoggerAdapter(self.logger, new_extra)

    def process(self, msg: str, kwargs: dict[str, Any]) -> tuple[str, dict[str, Any]]:
        extra = kwargs.setdefault("extra", {})
        extra.update(self.extra or {})
        if "trace_id" not in extra:
            extra["trace_id"] = _trace_id_var.get() or "-"
        return msg, kwargs


def setup_logging(level: str = "INFO", *, json_format: bool = False) -> logging.Logger:
    """初始化全局日志配置。

    Args:
        level: 日志级别字符串（DEBUG/INFO/WARNING/ERROR）。
        json_format: 是否使用 JSON 格式化（生产环境推荐）。

    Returns:
        配置后的根 logger。
    """
    global _CONFIGURED
    if _CONFIGURED:
        return logging.getLogger("book_dismantler")

    numeric_level = getattr(logging, level.upper(), logging.INFO)
    handler = logging.StreamHandler(sys.stderr)
    if json_format:
        handler.setFormatter(_JsonFormatter())
    else:
        handler.setFormatter(logging.Formatter(_DEFAULT_FORMAT, _DATE_FORMAT))
    handler.addFilter(_ContextFilter())

    root = logging.getLogger("book_dismantler")
    root.setLevel(numeric_level)
    # 避免重复添加 handler（reload 场景）
    already_owned = any(
        isinstance(h, logging.StreamHandler) and getattr(h, "_bd_owned", False)
        for h in root.handlers
    )
    if not already_owned:
        # 标记此 handler 来自 book_dismantler，便于幂等判断
        handler.__dict__["_bd_owned"] = True
        root.addHandler(handler)
    root.propagate = False
    _CONFIGURED = True
    return root


def get_logger(name: str) -> ContextLoggerAdapter:
    """获取子 logger，自动支持 context binding。"""
    return ContextLoggerAdapter(logging.getLogger(f"book_dismantler.{name}"))


def new_trace_id() -> str:
    """生成新的 trace_id（8 字符短 UUID）。"""
    return uuid.uuid4().hex[:8]


def set_trace_id(trace_id: str | None = None) -> str:
    """设置当前上下文的 trace_id，返回实际使用的值。"""
    if trace_id is None:
        trace_id = new_trace_id()
    _trace_id_var.set(trace_id)
    return trace_id


def get_trace_id() -> str | None:
    """获取当前上下文的 trace_id。"""
    return _trace_id_var.get()


def clear_trace_id() -> None:
    """清除当前 trace_id（用于请求结束）。"""
    _trace_id_var.set(None)

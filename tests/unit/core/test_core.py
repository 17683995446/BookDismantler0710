"""核心模块单元测试：配置、异常、日志。"""

from __future__ import annotations

import pytest

from book_dismantler.core.config import Settings, get_settings
from book_dismantler.core.exceptions import (
    AnalysisError,
    ArtifactNotFoundError,
    BookDismantlerError,
    ConfigError,
    ExportError,
    FileUploadError,
    JobCancelledError,
    JobNotFoundError,
    LLMError,
    ParseError,
    RenderError,
    ValidationError,
)
from book_dismantler.core.logging import (
    clear_trace_id,
    get_logger,
    get_trace_id,
    new_trace_id,
    set_trace_id,
    setup_logging,
)

# ---------------------------------------------------------------------------
# 异常层次
# ---------------------------------------------------------------------------

class TestExceptionHierarchy:
    """异常层次正确性。"""

    @pytest.mark.parametrize(
        "exc_class",
        [ConfigError, ParseError, LLMError, AnalysisError, RenderError, ExportError],
    )
    def test_all_inherit_from_base(self, exc_class: type) -> None:
        assert issubclass(exc_class, BookDismantlerError)

    def test_base_is_exception(self) -> None:
        assert issubclass(BookDismantlerError, Exception)

    def test_exceptions_carry_message(self) -> None:
        err = ParseError("文件损坏")
        assert str(err) == "文件损坏"

    def test_exceptions_carry_details(self) -> None:
        err = JobNotFoundError(job_id="abc123")
        assert err.details == {"job_id": "abc123"}
        assert "abc123" in err.message
        assert err.code == "JOB_NOT_FOUND"
        assert err.http_status == 404

    def test_exceptions_have_codes(self) -> None:
        """每个异常类都有唯一 code。"""
        codes = {
            ConfigError().code,
            ParseError().code,
            LLMError().code,
            AnalysisError().code,
            RenderError().code,
            ExportError().code,
            JobNotFoundError().code,
            ArtifactNotFoundError().code,
            ValidationError().code,
            FileUploadError().code,
            JobCancelledError().code,
        }
        assert len(codes) == 11  # 全部唯一

    def test_exceptions_are_catchable_by_base(self) -> None:
        for exc_class in [ConfigError, LLMError, RenderError]:
            with pytest.raises(BookDismantlerError):
                raise exc_class("test")

    def test_validation_error_default_message(self) -> None:
        err = ValidationError()
        assert err.message == "ValidationError"

    def test_default_details_empty(self) -> None:
        assert ConfigError("x").details == {}


# ---------------------------------------------------------------------------
# 配置
# ---------------------------------------------------------------------------

class TestSettings:
    """Settings 配置加载。"""

    def test_default_values(self, monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
        monkeypatch.setenv("BOOK_DISMANTLER_OUTPUT_DIR", str(tmp_path))
        get_settings.cache_clear()
        settings = Settings()
        assert settings.default_provider == "siliconflow"
        assert settings.chunk_size == 2000
        assert settings.chunk_overlap == 200
        assert settings.max_concurrent == 4

    def test_env_override(self, monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
        monkeypatch.setenv("BOOK_DISMANTLER_CHUNK_SIZE", "3000")
        monkeypatch.setenv("BOOK_DISMANTLER_OUTPUT_DIR", str(tmp_path))
        get_settings.cache_clear()
        settings = Settings()
        assert settings.chunk_size == 3000

    def test_output_dir_auto_created(self, tmp_path) -> None:
        out = tmp_path / "nested" / "output"
        Settings(output_dir=out)
        assert out.exists()

    def test_get_provider_config_deepseek(self, tmp_path) -> None:
        settings = Settings(output_dir=tmp_path, deepseek_api_key="sk-test")
        config = settings.get_provider_config("deepseek")
        assert config["api_key"] == "sk-test"
        assert "deepseek.com" in config["base_url"]

    def test_get_provider_config_default(self, tmp_path) -> None:
        settings = Settings(output_dir=tmp_path)
        config = settings.get_provider_config()
        assert config["base_url"]  # 非空

    def test_get_provider_config_unknown_raises(self, tmp_path) -> None:
        settings = Settings(output_dir=tmp_path)
        with pytest.raises(ValueError, match="未知 provider"):
            settings.get_provider_config("nonexistent")

    def test_chunk_size_validation(self, tmp_path) -> None:
        with pytest.raises(ValueError):
            Settings(output_dir=tmp_path, chunk_size=50)  # < 100

    def test_overlap_validation(self, tmp_path) -> None:
        with pytest.raises(ValueError):
            Settings(output_dir=tmp_path, chunk_overlap=-1)


# ---------------------------------------------------------------------------
# 日志
# ---------------------------------------------------------------------------

class TestLogging:
    """日志配置。"""

    def test_setup_logging_returns_logger(self) -> None:
        # 重置单例状态
        from book_dismantler.core import logging as logging_module

        logging_module._CONFIGURED = False
        logger = setup_logging("DEBUG")
        assert logger.name == "book_dismantler"

    def test_get_logger_child(self) -> None:
        child = get_logger("test")
        assert child.name == "book_dismantler.test"

    def test_setup_logging_idempotent(self) -> None:
        logger1 = setup_logging("INFO")
        logger2 = setup_logging("ERROR")
        assert logger1 is logger2


class TestTraceId:
    """trace_id 上下文管理。"""

    def setup_method(self) -> None:
        clear_trace_id()

    def teardown_method(self) -> None:
        clear_trace_id()

    def test_new_trace_id_unique(self) -> None:
        ids = {new_trace_id() for _ in range(20)}
        assert len(ids) == 20  # 全部唯一

    def test_set_and_get_trace_id(self) -> None:
        tid = set_trace_id("abc12345")
        assert tid == "abc12345"
        assert get_trace_id() == "abc12345"

    def test_set_trace_id_auto_generate(self) -> None:
        tid = set_trace_id()
        assert tid is not None
        assert len(tid) == 8

    def test_clear_trace_id(self) -> None:
        set_trace_id("test")
        clear_trace_id()
        assert get_trace_id() is None

    def test_context_logger_adapter_bind(self) -> None:
        """bind 后的 logger 应携带额外上下文。"""
        log = get_logger("test")
        bound = log.bind(job_id="j1", book_id="b1")
        # 验证 extra 已合并
        assert bound.extra.get("job_id") == "j1"
        assert bound.extra.get("book_id") == "b1"

    def test_context_logger_adapter_inherits(self) -> None:
        log = get_logger("test")
        bound1 = log.bind(job_id="j1")
        bound2 = bound1.bind(book_id="b1")
        assert bound2.extra.get("job_id") == "j1"
        assert bound2.extra.get("book_id") == "b1"

    def test_setup_logging_json_format(self) -> None:
        """F4: JSON 格式化器输出可被 json.loads 解析。"""
        import json
        import logging

        # 单独构建一个 JSON logger 验证输出格式
        from book_dismantler.core.logging import _JsonFormatter

        fmt = _JsonFormatter()
        record = logging.LogRecord(
            name="book_dismantler.test",
            level=logging.INFO,
            pathname="x.py",
            lineno=1,
            msg="hello world",
            args=None,
            exc_info=None,
        )
        record.job_id = "j999"
        record.trace_id = "abc12345"
        output = fmt.format(record)
        data = json.loads(output)
        assert data["level"] == "INFO"
        assert data["message"] == "hello world"
        assert data["trace_id"] == "abc12345"
        assert data["job_id"] == "j999"
        assert "ts" in data

    def test_json_formatter_omits_reserved_fields(self) -> None:
        """F4: 保留字段（name/pathname 等）不会出现在 payload 中。"""
        import json
        import logging

        from book_dismantler.core.logging import _JsonFormatter

        fmt = _JsonFormatter()
        record = logging.LogRecord(
            name="book_dismantler.test",
            level=logging.INFO,
            pathname="x.py",
            lineno=1,
            msg="msg",
            args=None,
            exc_info=None,
        )
        output = fmt.format(record)
        data = json.loads(output)
        # 保留字段不应作为 extras 出现
        assert "pathname" not in data
        assert "lineno" not in data
        assert "msg" not in data

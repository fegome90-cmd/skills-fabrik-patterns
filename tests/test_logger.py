"""
Unit Tests for Structured Logging Module

Tests the logger module functionality including formatters,
decorators, and context management.
"""

import pytest
import json
import logging
from pathlib import Path
import tempfile
from io import StringIO
import sys

# Add lib to path for imports
import sys as _sys
lib_dir = Path(__file__).parent.parent / "lib"
_sys.path.insert(0, str(lib_dir))

from logger import (
    LogLevel,
    LogContext,
    JSONFormatter,
    StructuredLogger,
    get_logger,
    log_execution,
    log_async_execution,
    configure_global_logging
)


class TestLogLevel:
    """Test LogLevel enum."""

    def test_log_level_values(self):
        """Test LogLevel values align with standard logging."""
        assert LogLevel.DEBUG.value == logging.DEBUG
        assert LogLevel.INFO.value == logging.INFO
        assert LogLevel.WARNING.value == logging.WARNING
        assert LogLevel.ERROR.value == logging.ERROR
        assert LogLevel.CRITICAL.value == logging.CRITICAL


class TestLogContext:
    """Test LogContext dataclass."""

    def test_empty_context(self):
        """Test creating empty context."""
        context = LogContext()
        assert context.module == ""
        assert context.function == ""
        assert context.line_no == 0
        assert context.extra == {}

    def test_context_with_values(self):
        """Test creating context with values."""
        context = LogContext(
            module="test_module",
            function="test_function",
            line_no=42,
            extra={"key": "value"}
        )
        assert context.module == "test_module"
        assert context.function == "test_function"
        assert context.line_no == 42
        assert context.extra == {"key": "value"}

    def test_context_immutability(self):
        """Test LogContext is immutable."""
        from dataclasses import FrozenInstanceError
        context = LogContext(module="test")
        with pytest.raises(FrozenInstanceError):  # frozen=True
            context.module = "changed"

    def test_context_to_dict(self):
        """Test converting context to dictionary."""
        context = LogContext(
            module="test_mod",
            function="test_func",
            line_no=10,
            extra={"user": "alice", "request_id": "123"}
        )
        result = context.to_dict()
        assert result == {
            "module": "test_mod",
            "function": "test_func",
            "line_no": 10,
            "user": "alice",
            "request_id": "123"
        }


class TestJSONFormatter:
    """Test JSONFormatter."""

    def test_json_formatter_basic(self):
        """Test basic JSON formatting."""
        formatter = JSONFormatter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=10,
            msg="Test message",
            args=(),
            exc_info=None
        )
        output = formatter.format(record)
        data = json.loads(output)
        assert data["level"] == "INFO"
        assert data["message"] == "Test message"
        assert "timestamp" in data

    def test_json_formatter_with_extra(self):
        """Test JSON formatter with extra fields."""
        formatter = JSONFormatter()
        record = logging.LogRecord(
            name="test",
            level=logging.ERROR,
            pathname="test.py",
            lineno=10,
            msg="Error message",
            args=(),
            exc_info=None
        )
        record.custom_field = "custom_value"
        output = formatter.format(record)
        data = json.loads(output)
        assert data["custom_field"] == "custom_value"

    def test_json_formatter_with_exception(self):
        """Test JSON formatter includes exception info."""
        formatter = JSONFormatter()
        try:
            raise ValueError("Test exception")
        except ValueError:
            import sys
            exc_info = sys.exc_info()

        record = logging.LogRecord(
            name="test",
            level=logging.ERROR,
            pathname="test.py",
            lineno=10,
            msg="Error occurred",
            args=(),
            exc_info=exc_info
        )
        output = formatter.format(record)
        data = json.loads(output)
        assert "exception" in data
        assert "ValueError" in data["exception"]


class TestStructuredLogger:
    """Test StructuredLogger class."""

    def test_singleton_per_name(self):
        """Test logger is singleton per name."""
        logger1 = StructuredLogger("test")
        logger2 = StructuredLogger("test")
        logger3 = StructuredLogger("other")
        assert logger1 is logger2
        assert logger1 is not logger3

    def test_configure_basic(self):
        """Test basic logger configuration."""
        logger = StructuredLogger("test_configure")
        logger.configure(level=LogLevel.DEBUG)
        assert logger._logger.level == logging.DEBUG

    def test_configure_with_file(self, tmp_path):
        """Test configuration with file output."""
        log_file = tmp_path / "test.log"
        logger = StructuredLogger("test_file")
        logger.configure(level=LogLevel.INFO, output_file=log_file)

        logger.info("Test message")

        # Check file was created and contains message
        assert log_file.exists()
        content = log_file.read_text()
        assert "Test message" in content

    def test_context_manager(self):
        """Test context manager for temporary context."""
        logger = StructuredLogger("test_context")
        logger.configure(level=LogLevel.INFO)

        with logger.context(user_id="123", request_id="abc"):
            # Inside context, extra fields should be available
            assert logger._context.extra == {"user_id": "123", "request_id": "abc"}

        # Outside context, should be restored
        assert logger._context.extra == {}

    def test_nested_context(self):
        """Test nested context managers."""
        logger = StructuredLogger("test_nested")
        logger.configure(level=LogLevel.INFO)

        with logger.context(level1="value1"):
            assert logger._context.extra == {"level1": "value1"}
            with logger.context(level2="value2"):
                assert logger._context.extra == {"level1": "value1", "level2": "value2"}
            assert logger._context.extra == {"level1": "value1"}
        assert logger._context.extra == {}

    def test_log_levels(self, caplog):
        """Test all log levels."""
        logger = StructuredLogger("test_levels")
        logger.configure(level=LogLevel.DEBUG)

        with caplog.at_level(logging.DEBUG):
            logger.debug("Debug message")
            logger.info("Info message")
            logger.warning("Warning message")
            logger.error("Error message")
            logger.critical("Critical message")

        assert any("Debug message" in r.message for r in caplog.records)
        assert any("Info message" in r.message for r in caplog.records)
        assert any("Warning message" in r.message for r in caplog.records)
        assert any("Error message" in r.message for r in caplog.records)
        assert any("Critical message" in r.message for r in caplog.records)

    def test_log_with_extra_fields(self, caplog):
        """Test logging with extra fields."""
        logger = StructuredLogger("test_extra")
        logger.configure(level=LogLevel.INFO)

        with caplog.at_level(logging.INFO):
            logger.info("Message with extra", user_id="123", action="login")

        # The extra fields should be in the log record
        assert any("Message with extra" in r.message for r in caplog.records)


class TestGetLogger:
    """Test get_logger factory function."""

    def test_get_logger_returns_singleton(self):
        """Test get_logger returns singleton per name."""
        logger1 = get_logger("test_module")
        logger2 = get_logger("test_module")
        assert logger1 is logger2

    def test_get_logger_different_names(self):
        """Test get_logger returns different loggers for different names."""
        logger1 = get_logger("module1")
        logger2 = get_logger("module2")
        assert logger1 is not logger2


class TestLogExecutionDecorator:
    """Test log_execution decorator."""

    def test_log_execution_success(self, caplog):
        """Test decorator logs successful execution."""
        logger = StructuredLogger("test_decorator")
        logger.configure(level=LogLevel.DEBUG)

        @log_execution(logger=logger, level=LogLevel.DEBUG)
        def add(a: int, b: int) -> int:
            return a + b

        with caplog.at_level(logging.DEBUG):
            result = add(2, 3)

        assert result == 5
        assert any("Entering" in r.message for r in caplog.records)
        assert any("Exiting" in r.message for r in caplog.records)

    def test_log_execution_with_args(self, caplog):
        """Test decorator logs arguments when enabled."""
        logger = StructuredLogger("test_args")
        logger.configure(level=LogLevel.DEBUG)

        @log_execution(logger=logger, log_args=True)
        def multiply(a: int, b: int) -> int:
            return a * b

        with caplog.at_level(logging.DEBUG):
            multiply(3, 4)

        # Check that fn_args was logged (not 'args' which is reserved)
        assert any("fn_args" in str(r.__dict__) for r in caplog.records)

    def test_log_execution_with_result(self, caplog):
        """Test decorator logs result when enabled."""
        logger = StructuredLogger("test_result")
        logger.configure(level=LogLevel.DEBUG)

        @log_execution(logger=logger, log_result=True)
        def divide(a: int, b: int) -> float:
            return a / b

        with caplog.at_level(logging.DEBUG):
            divide(10, 2)

        assert any("result" in str(r.__dict__) for r in caplog.records)

    def test_log_execution_exception(self, caplog):
        """Test decorator logs exceptions."""
        logger = StructuredLogger("test_exception")
        logger.configure(level=LogLevel.ERROR)

        @log_execution(logger=logger, log_errors=True)
        def failing_function() -> None:
            raise ValueError("Test error")

        with caplog.at_level(logging.ERROR):
            with pytest.raises(ValueError):
                failing_function()

        assert any("Error in" in r.message for r in caplog.records)

    def test_log_execution_without_logger(self, caplog):
        """Test decorator works without explicit logger."""
        @log_execution(level=LogLevel.INFO)
        def simple_function(x: int) -> int:
            return x * 2

        with caplog.at_level(logging.INFO):
            result = simple_function(5)

        assert result == 10
        # Should have created a logger for the module
        assert len(caplog.records) > 0


class TestLogAsyncExecutionDecorator:
    """Test log_async_execution decorator."""

    @pytest.mark.asyncio
    async def test_log_async_execution(self, caplog):
        """Test async decorator logs execution."""
        logger = StructuredLogger("test_async")
        logger.configure(level=LogLevel.DEBUG)

        @log_async_execution(logger=logger, level=LogLevel.DEBUG)
        async def async_add(a: int, b: int) -> int:
            await asyncio.sleep(0)
            return a + b

        import asyncio

        with caplog.at_level(logging.DEBUG):
            result = await async_add(2, 3)

        assert result == 5
        assert any("(async)" in r.message for r in caplog.records)

    @pytest.mark.asyncio
    async def test_log_async_execution_with_args(self, caplog):
        """Test async decorator logs arguments."""
        logger = StructuredLogger("test_async_args")
        logger.configure(level=LogLevel.DEBUG)

        @log_async_execution(logger=logger, log_args=True)
        async def async_multiply(a: int, b: int) -> int:
            await asyncio.sleep(0)
            return a * b

        import asyncio

        with caplog.at_level(logging.DEBUG):
            await async_multiply(3, 4)

        # Check that fn_args was logged (not 'args' which is reserved)
        assert any("fn_args" in str(r.__dict__) for r in caplog.records)

    @pytest.mark.asyncio
    async def test_log_async_execution_exception(self, caplog):
        """Test async decorator logs exceptions."""
        logger = StructuredLogger("test_async_exception")
        logger.configure(level=LogLevel.ERROR)

        @log_async_execution(logger=logger, log_errors=True)
        async def async_failing() -> None:
            await asyncio.sleep(0)
            raise ValueError("Async error")

        import asyncio

        with caplog.at_level(logging.ERROR):
            with pytest.raises(ValueError):
                await async_failing()

        assert any("Error" in r.message for r in caplog.records)


class TestConfigureGlobalLogging:
    """Test global logging configuration."""

    def test_configure_global_basic(self):
        """Test basic global configuration."""
        configure_global_logging(level=LogLevel.INFO)
        root_logger = logging.getLogger()
        assert root_logger.level == logging.INFO

    def test_configure_global_with_file(self, tmp_path):
        """Test global configuration with file."""
        log_file = tmp_path / "global.log"
        configure_global_logging(
            level=LogLevel.INFO,
            log_file=log_file
        )

        # Log something
        logging.getLogger("test").info("Global test message")

        # Check file
        assert log_file.exists()
        content = log_file.read_text()
        assert "Global test message" in content

    def test_configure_global_json_format(self, tmp_path):
        """Test global configuration with JSON format."""
        log_file = tmp_path / "global_json.log"
        configure_global_logging(
            level=LogLevel.INFO,
            json_format=True,
            log_file=log_file
        )

        logging.getLogger("test_json").info("JSON test")

        # Check file has JSON
        content = log_file.read_text()
        data = json.loads(content.strip())
        assert data["message"] == "JSON test"
        assert "timestamp" in data


class TestLoggerIntegration:
    """Integration tests for logger module."""

    def test_full_logging_workflow(self, tmp_path, caplog):
        """Test complete logging workflow."""
        # Configure global logging
        log_file = tmp_path / "workflow.log"
        configure_global_logging(
            level=LogLevel.DEBUG,
            log_file=log_file
        )

        # Get logger and use it
        logger = get_logger("workflow_test")

        # Use context manager
        with logger.context(request_id="abc123"):
            logger.info("Processing request", user_id="alice")

            # Use decorator
            @log_execution(level=LogLevel.DEBUG)
            def process_item(item: str) -> str:
                logger.debug(f"Processing: {item}")
                return item.upper()

            result = process_item("test")

        assert result == "TEST"

        # Check file content
        content = log_file.read_text()
        assert "Processing request" in content
        assert "Processing: test" in content


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

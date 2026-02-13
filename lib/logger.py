"""
Structured Logging Module

Provides structured logging with context capture for debugging and observability.
Compatible with both standard logging and optional structlog integration.

Pattern from: Skills-Fabrik observability patterns.
"""

import logging
import sys
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from functools import wraps
from pathlib import Path
from typing import Any, Callable, TypeVar

# Type variables for generic decorators
F = TypeVar('F', bound=Callable[..., Any])
T = TypeVar('T')


class LogLevel(Enum):
    """Log levels aligned with standard logging."""
    DEBUG = logging.DEBUG
    INFO = logging.INFO
    WARNING = logging.WARNING
    ERROR = logging.ERROR
    CRITICAL = logging.CRITICAL


@dataclass(frozen=True)
class LogContext:
    """Immutable context for log entries."""
    module: str = ""
    function: str = ""
    line_no: int = 0
    extra: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert context to dictionary for logging."""
        return {
            "module": self.module,
            "function": self.function,
            "line_no": self.line_no,
            **self.extra
        }


class JSONFormatter(logging.Formatter):
    """JSON formatter for structured log output."""

    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON."""
        import json

        log_data = {
            "timestamp": datetime.fromtimestamp(record.created).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }

        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        # Add extra fields from record
        for key, value in record.__dict__.items():
            if key not in {
                'name', 'msg', 'args', 'levelname', 'levelno', 'pathname',
                'filename', 'module', 'lineno', 'funcName', 'created', 'msecs',
                'relativeCreated', 'thread', 'threadName', 'processName',
                'process', 'getMessage', 'exc_info', 'exc_text', 'stack_info'
            }:
                log_data[key] = value

        return json.dumps(log_data, default=str)


class StructuredLogger:
    """
    Structured logger with context capture.

    Provides thread-safe logging with automatic context capture
    and optional JSON output format.
    """

    _instances: dict[str, 'StructuredLogger'] = {}

    def __new__(cls, name: str) -> 'StructuredLogger':
        """Singleton pattern per logger name."""
        if name not in cls._instances:
            instance = super().__new__(cls)
            cls._instances[name] = instance
        return cls._instances[name]

    def __init__(self, name: str):
        """
        Initialize structured logger.

        Args:
            name: Logger name (typically module name)
        """
        if hasattr(self, '_initialized'):
            return

        self._logger = logging.getLogger(name)
        self._context: LogContext = LogContext()
        self._initialized = True

    def configure(
        self,
        level: LogLevel | int = LogLevel.INFO,
        json_format: bool = False,
        output_file: Path | None = None
    ) -> None:
        """
        Configure the logger.

        Args:
            level: Minimum log level
            json_format: Use JSON format for output
            output_file: Optional file path for log output
        """
        # Remove existing handlers
        self._logger.handlers.clear()

        # Set level
        log_level = level.value if isinstance(level, LogLevel) else level
        self._logger.setLevel(log_level)

        # Create formatter
        if json_format:
            formatter: logging.Formatter = JSONFormatter()
        else:
            format_str = (
                "%(asctime)s | %(levelname)-8s | %(name)s | "
                "%(module)s:%(funcName)s:%(lineno)d | %(message)s"
            )
            formatter = logging.Formatter(format_str, datefmt="%Y-%m-%d %H:%M:%S")

        # Console handler
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(log_level)
        console_handler.setFormatter(formatter)
        self._logger.addHandler(console_handler)

        # File handler (optional)
        if output_file:
            file_handler = logging.FileHandler(output_file)
            file_handler.setLevel(log_level)
            file_handler.setFormatter(formatter)
            self._logger.addHandler(file_handler)

    @contextmanager
    def context(self, **kwargs: Any) -> Any:
        """
        Temporarily add context to log entries.

        Usage:
            with logger.context(user_id="123", request_id="abc"):
                logger.info("Processing request")
        """
        old_extra = self._context.extra
        new_extra = {**old_extra, **kwargs}
        self._context = LogContext(
            module=self._context.module,
            function=self._context.function,
            line_no=self._context.line_no,
            extra=new_extra
        )
        try:
            yield
        finally:
            self._context = LogContext(
                module=self._context.module,
                function=self._context.function,
                line_no=self._context.line_no,
                extra=old_extra
            )

    def _log(
        self,
        level: LogLevel,
        message: str,
        **extra: Any
    ) -> None:
        """Internal logging method with context."""
        # Get caller info
        import inspect
        frame = inspect.currentframe()
        if frame and frame.f_back:
            frame_info = frame.f_back
            module = frame_info.f_globals.get('__name__', '')
            function = frame_info.f_code.co_name
            line_no = frame_info.f_lineno
        else:
            module = ""
            function = ""
            line_no = 0

        # Merge context with extra
        all_extra = {**self._context.extra, **extra}

        # Add standard context fields
        all_extra.update({
            'ctx_module': self._context.module or module,
            'ctx_function': self._context.function or function,
            'ctx_line': self._context.line_no or line_no
        })

        self._logger.log(level.value, message, extra=all_extra)

    def debug(self, message: str, **extra: Any) -> None:
        """Log debug message."""
        self._log(LogLevel.DEBUG, message, **extra)

    def info(self, message: str, **extra: Any) -> None:
        """Log info message."""
        self._log(LogLevel.INFO, message, **extra)

    def warning(self, message: str, **extra: Any) -> None:
        """Log warning message."""
        self._log(LogLevel.WARNING, message, **extra)

    def error(self, message: str, **extra: Any) -> None:
        """Log error message."""
        self._log(LogLevel.ERROR, message, **extra)

    def critical(self, message: str, **extra: Any) -> None:
        """Log critical message."""
        self._log(LogLevel.CRITICAL, message, **extra)

    def exception(self, message: str, **extra: Any) -> None:
        """Log exception with traceback."""
        self._logger.exception(message, extra={**self._context.extra, **extra})


def get_logger(name: str) -> StructuredLogger:
    """
    Get or create a structured logger.

    Args:
        name: Logger name (typically __name__ from calling module)

    Returns:
        StructuredLogger instance
    """
    return StructuredLogger(name)


def log_execution(
    logger: StructuredLogger | None = None,
    level: LogLevel = LogLevel.DEBUG,
    log_args: bool = False,
    log_result: bool = False,
    log_errors: bool = True
) -> Callable[[F], F]:
    """
    Decorator to log function execution.

    Args:
        logger: Logger instance (uses module logger if None)
        level: Log level for successful execution
        log_args: Include function arguments in log
        log_result: Include return value in log
        log_errors: Log exceptions

    Usage:
        @log_execution(level=LogLevel.INFO)
        def my_function(x: int) -> int:
            return x * 2
    """
    def decorator(func: F) -> F:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            # Get logger for module
            nonlocal logger
            if logger is None:
                logger = get_logger(func.__module__)

            func_name = f"{func.__module__}.{func.__qualname__}"

            # Log entry
            extra_data = {}
            if log_args:
                extra_data['fn_args'] = str(args)  # Use fn_args to avoid conflict
                extra_data['fn_kwargs'] = str(kwargs)

            logger._log(level, f"→ Entering {func_name}", **extra_data)

            try:
                result = func(*args, **kwargs)

                # Log exit
                exit_data = {}
                if log_result:
                    exit_data['result'] = str(result)

                logger._log(level, f"← Exiting {func_name}", **exit_data)
                return result

            except Exception as e:
                if log_errors:
                    logger.error(
                        f"✗ Error in {func_name}: {e}",
                        error_type=type(e).__name__
                    )
                raise

        return wrapper  # type: ignore
    return decorator


def log_async_execution(
    logger: StructuredLogger | None = None,
    level: LogLevel = LogLevel.DEBUG,
    log_args: bool = False,
    log_result: bool = False,
    log_errors: bool = True
) -> Callable[[F], F]:
    """
    Decorator to log async function execution.

    Args:
        logger: Logger instance (uses module logger if None)
        level: Log level for successful execution
        log_args: Include function arguments in log
        log_result: Include return value in log
        log_errors: Log exceptions

    Usage:
        @log_async_execution(level=LogLevel.INFO)
        async def my_async_function(x: int) -> int:
            return await some_async_operation(x)
    """
    import asyncio

    def decorator(func: F) -> F:
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            # Get logger for module
            nonlocal logger
            if logger is None:
                logger = get_logger(func.__module__)

            func_name = f"{func.__module__}.{func.__qualname__}"

            # Log entry
            extra_data = {}
            if log_args:
                extra_data['fn_args'] = str(args)  # Use fn_args to avoid conflict
                extra_data['fn_kwargs'] = str(kwargs)

            logger._log(level, f"→ (async) Entering {func_name}", **extra_data)

            try:
                result = await func(*args, **kwargs)

                # Log exit
                exit_data = {}
                if log_result:
                    exit_data['result'] = str(result)

                logger._log(level, f"← (async) Exiting {func_name}", **exit_data)
                return result

            except Exception as e:
                if log_errors:
                    logger.error(
                        f"✗ (async) Error in {func_name}: {e}",
                        error_type=type(e).__name__
                    )
                raise

        return wrapper  # type: ignore
    return decorator


# Global logger configuration
def configure_global_logging(
    level: LogLevel | int = LogLevel.INFO,
    json_format: bool = False,
    log_file: Path | None = None
) -> None:
    """
    Configure logging globally for all loggers.

    Args:
        level: Minimum log level
        json_format: Use JSON format for output
        log_file: Optional file path for log output
    """
    # Get root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(level.value if isinstance(level, LogLevel) else level)

    # Remove existing handlers
    root_logger.handlers.clear()

    # Create formatter
    if json_format:
        formatter: logging.Formatter = JSONFormatter()
    else:
        format_str = (
            "%(asctime)s | %(levelname)-8s | %(name)s | "
            "%(module)s:%(funcName)s:%(lineno)d | %(message)s"
        )
        formatter = logging.Formatter(format_str, datefmt="%Y-%m-%d %H:%M:%S")

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level.value if isinstance(level, LogLevel) else level)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

    # File handler (optional)
    if log_file:
        # Ensure parent directory exists
        log_file.parent.mkdir(parents=True, exist_ok=True)

        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(level.value if isinstance(level, LogLevel) else level)
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)

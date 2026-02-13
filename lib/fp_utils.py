"""
Functional Programming Utilities

Provides Result/Either patterns using the returns library for explicit
error handling without exceptions.

Pattern from: Functional programming principles + Skills-Fabrik patterns.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import TypeVar, Generic, Callable, Any

from returns.curry import partial
from returns.result import Result, Success, Failure, safe
from returns.maybe import Maybe, Nothing, Some
from returns.io import IO, IOSuccess
from returns.functions import identity, raise_exception
from returns.pipeline import flow
from returns.pointfree import bind

from logger import get_logger, LogLevel

logger = get_logger(__name__)

# Type aliases for readability
T = TypeVar('T')
E = TypeVar('E')
U = TypeVar('U')


# ============================================================================
# Error Types
# ============================================================================

class ConfigError(Exception):
    """Configuration file error."""

    def __init__(self, path: str, reason: str):
        self.path = path
        self.reason = reason
        super().__init__(f"Config error at {path}: {reason}")


class ValidationError(Exception):
    """Validation error."""

    def __init__(self, check_name: str, reason: str):
        self.check_name = check_name
        self.reason = reason
        super().__init__(f"Validation failed '{check_name}': {reason}")


class ExecutionError(Exception):
    """Gate execution error."""

    def __init__(self, gate_name: str, reason: str):
        self.gate_name = gate_name
        self.reason = reason
        super().__init__(f"Execution error in '{gate_name}': {reason}")


class FileSystemError(Exception):
    """File system operation error."""

    def __init__(self, path: str, operation: str, reason: str):
        self.path = path
        self.operation = operation
        self.reason = reason
        super().__init__(f"FS error {operation} on {path}: {reason}")


# ============================================================================
# Result-Wrapped Operations
# ============================================================================

@safe
def _read_yaml_file(path: Path) -> dict[str, Any]:
    """
    Safely read a YAML file.

    Returns Success[dict] or Failure[Exception].
    Empty files return empty dict.
    """
    import yaml
    with open(path) as f:
        result = yaml.safe_load(f)
        return result if result is not None else {}


def load_config(
    config_path: Path
) -> Result[dict[str, Any], ConfigError]:
    """
    Load YAML configuration with Result type.

    Args:
        config_path: Path to YAML config file

    Returns:
        Success[dict] if file loaded successfully
        Failure[ConfigError] if file not found or invalid YAML

    Example:
        >>> result = load_config(Path("config/gates.yaml"))
        >>> match result:
        ...     case Success(config):
        ...         print(f"Loaded {len(config)} gates")
        ...     case Failure(error):
        ...         print(f"Error: {error}")
    """
    logger.debug(
        f"Loading config from {config_path}",
        config_path=str(config_path)
    )

    # Check file exists first for better error messages
    if not config_path.exists():
        error = ConfigError(
            path=str(config_path),
            reason="File not found"
        )
        logger.warning(
            f"Config file not found: {config_path}",
            config_path=str(config_path)
        )
        return Failure(error)

    # Try to read the YAML file
    result = _read_yaml_file(config_path)

    # Transform exception into typed error
    if isinstance(result, Failure):
        exc = result.failure()
        error = ConfigError(
            path=str(config_path),
            reason=f"Invalid YAML: {exc}"
        )
        logger.error(
            f"Failed to load config: {config_path}",
            config_path=str(config_path),
            error=str(exc)
        )
        return Failure(error)

    logger.debug(
        f"Successfully loaded config from {config_path}",
        config_path=str(config_path),
        keys_count=len(result.unwrap()) if isinstance(result, Success) else 0
    )
    # Type narrowing: we've handled Failure case above, so this is Success
    return result  # type: ignore[return-value]


def validate_project_structure(
    project_path: Path
) -> Result[dict[str, Any], ValidationError]:
    """
    Validate project structure with Result type.

    Args:
        project_path: Path to project directory

    Returns:
        Success[dict] with validation metadata if valid
        Failure[ValidationError] if validation fails
    """
    logger.debug(
        f"Validating project structure: {project_path}",
        project_path=str(project_path)
    )

    if not project_path.exists():
        error = ValidationError(
            check_name="project_structure",
            reason=f"Directory does not exist: {project_path}"
        )
        logger.info(
            f"Project validation failed: directory not found",
            project_path=str(project_path)
        )
        return Failure(error)

    checks = {
        "has_package_json": project_path / "package.json",
        "has_pyproject": project_path / "pyproject.toml",
        "has_readme": project_path / "README.md",
        "has_src_dir": project_path / "src",
        "has_lib_dir": project_path / "lib",
    }

    indicators_found = [name for name, path in checks.items() if path.exists()]

    # Pass validation if at least one indicator is found
    if not indicators_found:
        error = ValidationError(
            check_name="project_structure",
            reason="No project indicators found (missing: package.json, pyproject.toml, README.md, src/, lib/)"
        )
        logger.info(
            f"Project validation failed: no indicators found",
            project_path=str(project_path)
        )
        return Failure(error)

    metadata = {
        "project_path": str(project_path),
        "indicators_found": indicators_found,
        "validation_status": "passed"
    }

    logger.debug(
        f"Project structure validated: {project_path}",
        project_path=str(project_path),
        indicators_found=len(metadata["indicators_found"])
    )

    return Success(metadata)


# ============================================================================
# Maybe Types for Optional Values
# ============================================================================

def find_first_python_file(directory: Path) -> Maybe[Path]:
    """
    Find first Python file in directory (Maybe pattern).

    Returns Some[Path] if found, Nothing if not found.

    Example:
        >>> result = find_first_python_file(Path("src"))
        >>> match result:
        ...     case Some(path):
        ...         print(f"Found: {path}")
        ...     case Nothing:
        ...         print("No Python files found")
    """
    try:
        for path in directory.rglob("*.py"):
            if path.is_file():
                return Some(path)
    except Exception:
        pass

    return Nothing


def get_optional_env(key: str) -> Maybe[str]:
    """
    Get optional environment variable.

    Returns Some[str] if set, Nothing if not set.

    Example:
        >>> api_key = get_optional_env("API_KEY")
        >>> print(api_key.unwrap_or("default"))
    """
    import os
    value = os.environ.get(key)
    return Some(value) if value else Nothing


# ============================================================================
# Pipeline / Flow Operations
# ============================================================================

def parse_and_validate_config(
    config_path: Path,
    required_keys: list[str]
) -> Result[dict[str, Any], ConfigError | ValidationError]:
    """
    Parse and validate config in a functional pipeline.

    Demonstrates flow() with bind() for chaining operations.

    Args:
        config_path: Path to config file
        required_keys: Keys that must be present in config

    Returns:
        Success[dict] if config valid
        Failure with appropriate error type

    Example:
        >>> result = parse_and_validate_config(
        ...     Path("config/gates.yaml"),
        ...     ["gates", "version"]
        ... )
    """
    def validate_keys(config: dict[str, Any]) -> Result[dict[str, Any], ValidationError]:
        """Validate required keys exist in config."""
        missing_keys = [k for k in required_keys if k not in config]
        if missing_keys:
            return Failure(ValidationError(
                check_name="required_keys",
                reason=f"Missing keys: {', '.join(missing_keys)}"
            ))
        return Success(config)

    # Flow: load -> validate -> return
    return flow(
        load_config(config_path),
        bind(validate_keys),
    )


# ============================================================================
# Safe Wrappers for Operations
# ============================================================================

def safe_execute_command(
    command: str,
    cwd: Path
) -> Result[str, ExecutionError]:
    """
    Safely execute a shell command with Result type.

    Args:
        command: Shell command to execute
        cwd: Working directory

    Returns:
        Success[str] with stdout if command succeeds
        Failure[ExecutionError] if command fails
    """
    import subprocess

    logger.debug(
        f"Executing command: {command[:50]}...",
        command=command[:100],
        cwd=str(cwd)
    )

    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            cwd=cwd,
            timeout=60
        )

        if result.returncode == 0:
            logger.debug(
                f"Command succeeded: {command[:50]}...",
                command=command[:50]
            )
            return Success(result.stdout)
        else:
            error = ExecutionError(
                gate_name=command.split()[0],
                reason=result.stderr or "Command failed"
            )
            logger.warning(
                f"Command failed: {command[:50]}...",
                command=command[:50],
                error=error.reason[:100]
            )
            return Failure(error)

    except subprocess.TimeoutExpired:
        error = ExecutionError(
            gate_name=command.split()[0],
            reason="Command timeout"
        )
        logger.error(
            f"Command timeout: {command[:50]}...",
            command=command[:50]
        )
        return Failure(error)
    except Exception as e:
        error = ExecutionError(
            gate_name=command.split()[0],
            reason=str(e)
        )
        logger.error(
            f"Command error: {command[:50]}...",
            command=command[:50],
            error=str(e)
        )
        return Failure(error)


def safe_write_file(
    path: Path,
    content: str
) -> Result[Path, FileSystemError]:
    """
    Safely write a file with Result type.

    Args:
        path: File path to write
        content: Content to write

    Returns:
        Success[Path] if write succeeds
        Failure[FileSystemError] if write fails
    """
    logger.debug(
        f"Writing file: {path}",
        path=str(path),
        content_length=len(content)
    )

    try:
        # Ensure parent directory exists
        path.parent.mkdir(parents=True, exist_ok=True)

        # Write file
        path.write_text(content)

        logger.debug(
            f"Successfully wrote file: {path}",
            path=str(path),
            bytes_written=len(content)
        )
        return Success(path)

    except PermissionError as e:
        error = FileSystemError(
            path=str(path),
            operation="write",
            reason=f"Permission denied: {e}"
        )
        logger.error(
            f"Permission denied writing: {path}",
            path=str(path)
        )
        return Failure(error)

    except Exception as e:
        error = FileSystemError(
            path=str(path),
            operation="write",
            reason=str(e)
        )
        logger.error(
            f"Failed to write: {path}",
            path=str(path),
            error=str(e)
        )
        return Failure(error)


# ============================================================================
# Helper Functions for Result Handling
# ============================================================================

def map_success(
    result: Result[T, E],
    mapper: Callable[[T], U]
) -> Result[U, E]:
    """
    Map Success value through a function.

    If result is Success(x), returns Success(mapper(x)).
    If result is Failure(e), returns Failure(e) unchanged.
    """
    if isinstance(result, Success):
        try:
            return Success(mapper(result.unwrap()))
        except Exception as e:
            # Re-raise to be caught by caller
            raise_exception(e)
    return result  # type: ignore


def map_failure(
    result: Result[T, E],
    mapper: Callable[[E], E]
) -> Result[T, E]:
    """
    Map Failure error through a function.

    If result is Failure(e), returns Failure(mapper(e)).
    If result is Success(x), returns Success(x) unchanged.
    """
    if isinstance(result, Failure):
        try:
            return Failure(mapper(result.failure()))
        except Exception:
            # Re-raise to be caught by caller
            raise
    # Type narrowing: result is Success[T, E] here
    return result


def get_or_log(
    result: Result[T, E],
    default: T,
    operation_name: str
) -> T:
    """
    Unwrap Result or return default, logging failures.

    Args:
        result: Result to unwrap
        default: Default value if Failure
        operation_name: Name for logging

    Returns:
        The success value or default
    """
    if isinstance(result, Success):
        # unwrap() returns Any due to returns library type stubs
        return result.unwrap()  # type: ignore[no-any-return]

    # Log the failure
    error = result.failure()
    logger.warning(
        f"{operation_name} failed, using default",
        operation=operation_name,
        error=str(error)
    )
    return default


# Exports for public API
__all__ = [
    # Result types
    "Success",
    "Failure",
    "Result",
    "Maybe",
    "Some",
    "Nothing",
    
    # Type aliases
    "T",
    "E",
    "U",
    
    # Main functions (documented in module docstring)
    "load_config",
    "validate_project_structure",
    "parse_and_validate_config",
    "find_first_python_file",
    "get_optional_env",
    "safe_execute_command",
    "safe_write_file",
    "map_success",
    "map_failure",
    "get_or_log",
    
    # Composition functions (from returns.pipeline)
    "pipe",
    "compose",
    "flow",
    "bind",
    
    # Safe decorator
    "safe",
    
    # Logger
    "get_logger",
    
    # Classes (for type checking)
    "ConfigError",
    "ValidationError",
    "ExecutionError",
    "FileSystemError",
]


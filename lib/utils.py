"""
Shared Utility Functions

Common utility functions used across modules.
"""

import json
import sys
import time
from pathlib import Path
from time import perf_counter
from typing import Any, Callable, TypeVar

T = TypeVar('T')

# Default source file extensions for discovery
DEFAULT_SOURCE_EXTENSIONS: tuple[str, ...] = (
    '.py', '.ts', '.tsx', '.js', '.jsx', '.md', '.json'
)

# Default directories to exclude from file discovery
DEFAULT_EXCLUDE_DIRS: frozenset[str] = frozenset({
    '__pycache__', '.venv', 'venv', 'node_modules', '.git', '.mypy_cache'
})


def estimate_tokens_for_size(size_bytes: int) -> int:
    """
    Estimate tokens from file size.

    Uses a simple heuristic: ~30 tokens overhead + ~1 token per 34 bytes.
    This assumes average source code density.

    Args:
        size_bytes: File size in bytes

    Returns:
        Estimated token count (minimum 30)
    """
    return max(30, size_bytes // 34)


def measure_duration_ms(func: Callable[[], T]) -> tuple[T, int]:
    """
    Measure function duration in milliseconds.

    Args:
        func: A callable that takes no arguments

    Returns:
        A tuple of (result, duration_ms)
    """
    start = perf_counter()
    result = func()
    end = perf_counter()
    duration_ms = int((end - start) * 1000)
    return result, duration_ms


def get_project_path_from_stdin() -> Path:
    """
    Extract project path from Claude Code hook payload via stdin.

    Claude Code hooks receive a JSON payload via stdin containing a 'cwd' field
    with the project's current working directory. This function extracts that
    path for use in hooks that need to operate on the project directory.

    IMPORTANT: This function consumes stdin entirely. Call only once per script.
    If you need other fields from the payload, parse stdin manually instead.

    Returns:
        Path from 'cwd' field in payload, or Path.cwd() as fallback.
    """
    try:
        stdin_content = sys.stdin.read()
        if stdin_content and stdin_content.strip():
            input_data = json.loads(stdin_content)
            return Path(input_data.get('cwd', '.'))
    except (json.JSONDecodeError, ValueError, OSError, AttributeError):
        pass
    return Path.cwd()


def get_recent_files(
    cwd: Path,
    hours: int = 1,
    extensions: tuple[str, ...] | list[str] | None = None,
    exclude_dirs: frozenset[str] = DEFAULT_EXCLUDE_DIRS,
    max_files: int | None = 20
) -> list[str]:
    """
    Get files modified within the specified hours, sorted by mtime descending.

    Args:
        cwd: Directory to scan
        hours: Hours to look back (default 1)
        extensions: File extensions to include (default: DEFAULT_SOURCE_EXTENSIONS)
        exclude_dirs: Directory names to skip (default: DEFAULT_EXCLUDE_DIRS)
        max_files: Maximum files to return, None for unlimited (default 20)

    Returns:
        List of relative file paths as strings, sorted by modification time (most recent first)
    """
    if extensions is None:
        extensions = list(DEFAULT_SOURCE_EXTENSIONS)

    cutoff = time.time() - (hours * 3600)

    if cwd == Path.home():
        return []

    # Collect candidates with their modification times
    candidates: list[tuple[float, str]] = []

    try:
        for f in cwd.rglob("*"):
            # Skip excluded directories
            if any(part in exclude_dirs for part in f.parts):
                continue
            if f.is_file() and f.stat().st_mtime > cutoff:
                if f.suffix in extensions:
                    candidates.append((f.stat().st_mtime, str(f.relative_to(cwd))))
    except (OSError, PermissionError, FileNotFoundError):
        pass

    # Sort by mtime descending (most recent first)
    candidates.sort(key=lambda x: x[0], reverse=True)

    # Extract paths and apply limit
    paths = [path for _, path in candidates]
    if max_files is not None:
        paths = paths[:max_files]

    return paths

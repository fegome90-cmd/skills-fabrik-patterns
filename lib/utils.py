"""
Shared Utility Functions

Common utility functions used across modules.
"""

from time import perf_counter
from typing import Callable, TypeVar

T = TypeVar('T')


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

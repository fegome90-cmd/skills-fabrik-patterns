"""
Shared Utility Functions

Common utility functions used across modules.
"""

from time import perf_counter
from typing import Callable, TypeVar

T = TypeVar('T')


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

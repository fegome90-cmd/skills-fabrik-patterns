"""
Skills-Fabrik Library Module

Provides common utilities and setup functions for all modules.
"""

import sys
from pathlib import Path


# Module-level setup
lib_dir = Path(__file__).parent
if str(lib_dir) not in sys.path:
    sys.path.insert(0, str(lib_dir))


def setup_lib_path() -> None:
    """
    Add lib directory to sys.path for imports.

    This function should be called at module import time to ensure
    all lib modules can import each other. Calling multiple times
    is safe - subsequent calls will be no-ops due to the
    sys.path check.

    Note: This is now handled automatically at lib/__init__.py import,
    so explicit calls are no longer necessary in most cases.
    """
    # The path setup is done at module level above
    # This function exists for backward compatibility
    pass


__all__ = ["setup_lib_path"]

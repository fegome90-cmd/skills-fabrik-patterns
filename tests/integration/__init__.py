"""
Integration Tests for Skills-Fabrik Patterns Plugin

Tests communication between components and subsystems.
"""

from pathlib import Path

# Add lib to path for imports
lib_dir = Path(__file__).parent.parent.parent / "lib"
import sys
if str(lib_dir) not in sys.path:
    sys.path.insert(0, str(lib_dir))

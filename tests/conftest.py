"""
Pytest configuration and shared fixtures for skills-fabrik-patterns tests.
"""

import pytest
import tempfile
from pathlib import Path


@pytest.fixture
def plugin_root() -> Path:
    """Get plugin root directory."""
    return Path(__file__).parent.parent.parent


@pytest.fixture
def temp_dir(tmp_path: Path) -> Path:
    """
    Get temporary directory for test isolation.

    Provides a Path object instead of string for consistency.
    """
    return tmp_path


@pytest.fixture
def sample_handoff_data() -> dict:
    """
    Sample session data for handoff creation tests.

    Provides test data matching the expected structure for
    HandoffProtocol.create_from_session().

    Note: HandoffProtocol.create_from_session() expects 'session_id' key.
    """
    return {
        "session_id": "test-session-001",
        "task_context": "test_context",
        "completed_tasks": [
            {
                "id": "task-001",
                "description": "Test task completed",
                "timestamp": "2025-01-01T12:00:00Z",
            }
        ],
        "next_steps": [
            {
                "id": "task-002",
                "description": "Next test task",
                "status": "pending",
            }
        ],
    }

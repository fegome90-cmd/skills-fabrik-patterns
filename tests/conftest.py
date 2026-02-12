"""
Pytest Configuration and Fixtures for Skills-Fabrik Patterns Plugin

Provides common fixtures for integration, hooks, e2e, and performance tests.
"""

import pytest
import tempfile
import shutil
from pathlib import Path
from typing import Generator
import json
import sys

# Add lib to path for imports
lib_dir = Path(__file__).parent / "lib"
if str(lib_dir) not in sys.path:
    sys.path.insert(0, str(lib_dir))

# Register custom pytest marks to eliminate UnknownMarkWarning
def pytest_configure(config):
    """Register custom pytest marks."""
    config.addinivalue_line(
        "markers",
        [
            "unit: Unit tests (fast, isolated)",
            "integration: Integration tests (slower, may use external resources)",
            "e2e: End-to-end tests (slowest, full workflow)",
        ]
    )


@pytest.fixture
def temp_dir() -> Generator[Path, None, None]:
    """Create a temporary directory for test files."""
    temp_path = Path(tempfile.mkdtemp())
    yield temp_path
    shutil.rmtree(temp_path, ignore_errors=True)


@pytest.fixture
def temp_context_dir(temp_dir: Path) -> Generator[Path, None, None]:
    """Create a temporary context directory with sample CLAUDE.md."""
    context_dir = temp_dir / ".context"
    context_dir.mkdir(parents=True, exist_ok=True)

    # Create sample CLAUDE.md with TAGs
    claude_md = context_dir / "CLAUDE.md"
    claude_md.write_text("""# Claude Context for Test Project

## Identity
Felipe is a Python developer using FP patterns.

## Projects
- skills-fabrik-patterns: Plugin for Claude Code

## Rules
- Always use immutable data structures
- Follow PEP 8 conventions

## Preferences
- Prefers functional over OOP
- Uses pytest for testing

## Triggers
- When creating new modules
- Before committing code
""")

    yield context_dir


@pytest.fixture
def temp_project_dir(temp_dir: Path) -> Generator[Path, None, None]:
    """Create a temporary project directory with sample files."""
    project_dir = temp_dir / "test-project"
    project_dir.mkdir(parents=True, exist_ok=True)

    # Create sample Python file
    (project_dir / "main.py").write_text("""
def hello() -> str:
    return "Hello, World!"

if __name__ == "__main__":
    print(hello())
""")

    # Create requirements.txt
    (project_dir / "requirements.txt").write_text("""
pyyaml>=6.0
pytest>=7.0
""")

    yield project_dir


@pytest.fixture
def sample_handoff_data() -> dict:
    """Sample handoff data for testing."""
    return {
        "session_id": "test-session-001",
        "completed_tasks": [
            "Created TAG system module",
            "Implemented EvidenceCLI validation",
        ],
        "next_steps": [
            "Add unit tests",
            "Create documentation",
        ],
        "artifacts": [
            "lib/tag_system.py",
            "lib/evidence_cli.py",
        ],
        "context": {
            "current_task": "Testing",
            "files_changed": 2,
        },
        "notes": "Session progressing well",
    }


@pytest.fixture
def sample_config_file(temp_dir: Path) -> Path:
    """Create a sample gates.yaml config file."""
    config_dir = temp_dir / "config"
    config_dir.mkdir(parents=True, exist_ok=True)

    config_file = config_dir / "gates.yaml"
    config_file.write_text("""
gates:
  - name: type-check
    description: Python type checking with mypy
    command: mypy lib/
    required: true
    critical: false
    timeout: 30000
    file_patterns:
      - "*.py"

  - name: format-check
    description: Code formatting with ruff
    command: ruff check lib/
    required: true
    critical: false
    timeout: 15000
    file_patterns:
      - "*.py"

  - name: security-scan
    description: Security scanning with bandit
    command: bandit -r lib/
    required: false
    critical: true
    timeout: 20000
    file_patterns:
      - "*.py"
""")

    return config_file


@pytest.fixture
def plugin_root() -> Path:
    """Get the plugin root directory."""
    return Path(__file__).parent


@pytest.fixture
def mock_session_data() -> dict:
    """Mock session data for hook testing."""
    return {
        "session_id": "test-session-123",
        "user_prompt": "Create a new feature",
        "files_changed": ["lib/new_feature.py"],
        "tools_used": ["write", "edit"],
        "duration_seconds": 120,
    }


# Performance thresholds
MAX_HOOK_DURATION_MS = {
    "session_start": 100,
    "user_prompt_submit": 200,
    "pre_compact": 500,
    "post_tool_use": 100,
    "stop": 120000,  # 2 minutes
}

MAX_QUALITY_GATES_DURATION_MS = 30000  # 30 seconds

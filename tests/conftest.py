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


@pytest.fixture
def temp_context_dir(tmp_path: Path) -> Path:
    """
    Create a temporary context directory with sample files.

    Provides a .context directory structure for TAG extraction tests.
    """
    context_dir = tmp_path / ".context"
    context_dir.mkdir(parents=True, exist_ok=True)

    # Create sample CLAUDE.md with TAG sections
    (context_dir / "CLAUDE.md").write_text("""# Context

## Identity
Test user for integration tests

## Projects
- test-project: Sample project for testing

## Preferences
- Use functional programming patterns
- Follow TDD workflow

## Rules
- Always write tests first
- Use immutable data structures
""")

    # Create sample identity.md
    identity_dir = context_dir / "core"
    identity_dir.mkdir(parents=True, exist_ok=True)
    (identity_dir / "identity.md").write_text("""# Identity

## Personal
Name: Test User
Role: Developer

## Professional
Focus: Backend development
""")

    return context_dir


@pytest.fixture
def sample_config_file(tmp_path: Path) -> Path:
    """
    Create a sample quality gates config file.

    Provides a YAML config file for quality gates tests.
    Uses legacy flat format with list of gate objects.
    """
    config_file = tmp_path / "gates.yaml"
    config_file.write_text("""gates:
  - name: format-check
    description: Check Python formatting
    command: ruff format --check .
    timeout: 30
    critical: true
    file_patterns:
      - "*.py"

  - name: lint-check
    description: Check Python linting
    command: ruff check .
    timeout: 30
    critical: true
    file_patterns:
      - "*.py"

  - name: test
    description: Run unit tests
    command: pytest tests/ -x
    timeout: 120
    critical: false

  - name: security
    description: Security scan
    command: bandit -r src/
    timeout: 60
    critical: true
""")
    return config_file


@pytest.fixture
def temp_project_dir(tmp_path: Path) -> Path:
    """
    Create a temporary project directory with sample structure.

    Provides a Python project structure for evidence validation tests.
    """
    project_dir = tmp_path / "test_project"
    project_dir.mkdir(parents=True, exist_ok=True)

    # Create basic Python project structure
    (project_dir / "src").mkdir(parents=True, exist_ok=True)
    (project_dir / "lib").mkdir(parents=True, exist_ok=True)
    (project_dir / "tests").mkdir(parents=True, exist_ok=True)
    (project_dir / ".venv").mkdir(parents=True, exist_ok=True)

    # Create sample Python files
    (project_dir / "src" / "__init__.py").write_text("")
    (project_dir / "src" / "main.py").write_text("def main(): pass")

    # Create project indicators
    (project_dir / "package.json").write_text('{"name": "test-project", "version": "1.0.0"}')
    (project_dir / "README.md").write_text("# Test Project\n\nA sample project for testing.")
    (project_dir / "pyproject.toml").write_text('[project]\nname = "test-project"\nversion = "1.0.0"')

    return project_dir

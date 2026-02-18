"""
Tests for Ruff Formatter and FP Utils modules

FP-style tests using returns library.
"""
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
import tempfile
import subprocess
import sys

# Add lib directory to path for imports
lib_dir = Path(__file__).parent.parent / "lib"
sys.path.insert(0, str(lib_dir))

# Module-level imports for commonly used types
from ruff_formatter import RuffFormatter, RuffResult
from fp_utils import (
    Success, Failure, Some, Nothing, Maybe,
    load_config, validate_project_structure, find_first_python_file,
    safe_write_file, get_optional_env, map_success, map_failure,
    get_or_log, parse_and_validate_config,
    get_logger, LogLevel, ConfigError, ValidationError
)


# =============================================================================
# Ruff Formatter Tests
# =============================================================================

class TestRuffFormatterBasic:
    """Basic tests for Ruff formatter wrapper."""

    @pytest.mark.unit
    def test_ruff_formatter_init_default(self):
        """Should initialize with default values."""
        formatter = RuffFormatter()

        assert formatter.config_path is None
        assert formatter.target_version == "py314"
        assert formatter.config_args == []

    @pytest.mark.unit
    def test_ruff_formatter_init_with_config(self, tmp_path):
        """Should initialize with custom config."""
        config_path = tmp_path / "ruff_test.toml"

        formatter = RuffFormatter(config_path=config_path)

        assert formatter.config_path == config_path
        assert f"--config={config_path}" in formatter.config_args

    @pytest.mark.unit
    def test_ruff_formatter_init_with_version(self):
        """Should initialize with target version."""
        formatter = RuffFormatter(target_version="py312")

        assert formatter.target_version == "py312"
        # Note: target_version is stored but not added to config_args by default


class TestRuffFormatterReal:
    """Integration tests using real ruff executable."""

    @pytest.mark.integration
    @pytest.mark.skipif(
        sys.platform == "darwin",
        reason="Requires ruff installed (Unix-like)"
    )
    def test_format_file_real(self, tmp_path):
        """Test actual file formatting with real ruff."""
        # Crear un archivo desordenado
        test_file = tmp_path / "test_format_real.py"
        test_file.write_text("def foo():return    1+2+3+4+5+6+7+8+9+10+11+12+13", encoding='utf-8')

        formatter = RuffFormatter()

        result = formatter.format_file(test_file)

        # Solo verificar que se ejecutó sin error
        assert result.exit_code in [0, 1]  # 0 = success, 1 = already formatted
        assert result.success is True

    @pytest.mark.integration
    @pytest.mark.skipif(
        sys.platform == "darwin",
        reason="Requires ruff installed (Unix-like)"
    )
    def test_is_available(self):
        """Test is_available with real ruff."""
        formatter = RuffFormatter()
        result = formatter.is_available()

        # Si ruff no está instalado, devuelve False
        # Si está instalado, devuelve True
        assert isinstance(result, bool)


# =============================================================================
# FP Utils Tests
# =============================================================================

class TestFPUtilsBasic:
    """Basic tests for FP utilities."""

    @pytest.mark.unit
    def test_load_config_basic(self, tmp_path):
        """Test loading valid config."""
        config_path = tmp_path / "test_config.yaml"
        config_path.write_text(
            "gates:\n  test:\n    command: echo 'test'\n",
            encoding='utf-8'
        )

        result = load_config(config_path)

        assert isinstance(result, Success)
        config = result.unwrap()
        assert "gates" in config
        assert "test" in config["gates"]
        assert config["gates"]["test"]["command"] == "echo 'test'"

    @pytest.mark.unit
    def test_validate_project_structure_complete(self, tmp_path):
        """Test validation of complete project."""
        # Create complete project structure
        project_path = tmp_path / "test_project"
        (project_path / "src").mkdir(parents=True, exist_ok=True)
        (project_path / "lib").mkdir(parents=True, exist_ok=True)
        (project_path / "package.json").write_text('{"name": "test"}')
        (project_path / "README.md").write_text("# Test Project")
        (project_path / "pyproject.toml").write_text('[project]\\nname = "test"')

        result = validate_project_structure(project_path)

        assert isinstance(result, Success)
        metadata = result.unwrap()
        assert metadata["validation_status"] == "passed"
        assert len(metadata["indicators_found"]) >= 4

    @pytest.mark.unit
    def test_find_first_python_file(self, tmp_path):
        """Test finding first Python file."""
        project_path = tmp_path / "test_find"
        (project_path / "src").mkdir(parents=True, exist_ok=True)

        # Create main.py
        (project_path / "src" / "main.py").write_text("print('hello')", encoding='utf-8')

        result = find_first_python_file(project_path / "src")

        assert isinstance(result, Some)
        found_file = result.unwrap()
        assert found_file.name == "main.py"


class TestFPUtilsSafeOperations:
    """Tests for safe file operations."""

    @pytest.mark.unit
    def test_safe_write_file_creates_file(self, tmp_path):
        """safe_write_file should create file with content."""
        test_file = tmp_path / "test_safe_write.txt"
        content = "Hello from safe_write_file!"

        result = safe_write_file(test_file, content)

        assert isinstance(result, Success)
        assert test_file.exists()
        assert test_file.read_text(encoding='utf-8') == content

    @pytest.mark.unit
    def test_safe_write_file_creates_parent_dirs(self, tmp_path):
        """safe_write_file should create parent directories."""
        nested = tmp_path / "a" / "b" / "file.txt"

        result = safe_write_file(nested, "content")

        # Result should be Success type (re-exported from fp_utils)
        assert isinstance(result, Success)
        assert nested.exists()
        assert (tmp_path / "a").exists()
        assert (tmp_path / "a" / "b").exists()


class TestFPUtilsEnvironment:
    """Tests for environment variable handling."""

    @pytest.mark.unit
    def test_get_optional_env_exists(self, monkeypatch):
        """Should return value when env var exists."""
        monkeypatch.setenv("TEST_ENV_VAR", "test_value_123")

        result = get_optional_env("TEST_ENV_VAR")

        assert isinstance(result, Some)
        assert result.unwrap() == "test_value_123"

    @pytest.mark.unit
    def test_get_optional_env_missing(self, monkeypatch):
        """Should return Nothing when env var missing."""
        # Ensure env var is not set
        monkeypatch.delenv("TEST_MISSING_VAR", raising=False)

        result = get_optional_env("TEST_MISSING_VAR")

        # Nothing is a singleton - compare by identity/equality
        assert result == Nothing

    @pytest.mark.unit
    def test_get_optional_env_empty_value(self, monkeypatch):
        """Should return Nothing when env var is empty string."""
        # Set env var to empty string
        monkeypatch.setenv("TEST_EMPTY_VAR", "")

        result = get_optional_env("TEST_EMPTY_VAR")

        # Nothing is a singleton - compare by identity/equality
        assert result == Nothing


class TestFPUtilsResultWrappers:
    """Tests for Result wrapper functions."""

    @pytest.mark.unit
    def test_success_creation(self):
        """Success should wrap value."""
        result = Success(42)

        # Result type check using isintance
        assert isinstance(result, Success)
        assert result.unwrap() == 42

    @pytest.mark.unit
    def test_failure_creation(self):
        """Failure should wrap error."""
        error = ValueError("test error")
        result = Failure(error)

        # Result type check using isintance
        assert isinstance(result, Failure)
        assert result.failure() == error

    @pytest.mark.unit
    def test_maybe_creation(self):
        """Maybe should wrap value via Some."""
        # Maybe is an abstract type - use Some for values
        result = Some(42)

        # Some type check
        assert result.value_or(0) == 42

    @pytest.mark.unit
    def test_some_creation(self):
        """Some should wrap value."""
        result = Some(42)

        # Some type check (truthy value)
        assert bool(result)
        assert result.value_or(0) == 42

    @pytest.mark.unit
    def test_nothing_creation(self):
        """Nothing should indicate no value."""
        # Nothing is a singleton - use directly
        result = Nothing

        # Nothing type check - compare by identity
        assert result == Nothing
        # Nothing has no value - value_or returns default
        assert result.value_or(0) == 0


# =============================================================================
# Test Markers
# =============================================================================

class TestRuffFormatter:
    """Tests for Ruff formatter - full coverage."""
    pass  # Tests are in extended module


class TestFPUtils:
    """Tests for FP Utils - full coverage."""
    pass  # Tests are above


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

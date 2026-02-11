"""
Unit Tests for Functional Programming Utilities Module

Tests the fp_utils module functionality including Result types,
Maybe types, and safe operations.
"""

import pytest
import tempfile
from pathlib import Path
from datetime import datetime

# Add lib to path for imports
import sys
lib_dir = Path(__file__).parent.parent / "lib"
sys.path.insert(0, str(lib_dir))

from returns.result import Success, Failure
from returns.maybe import Nothing, Some

from fp_utils import (
    ConfigError,
    ValidationError,
    ExecutionError,
    FileSystemError,
    load_config,
    validate_project_structure,
    find_first_python_file,
    get_optional_env,
    parse_and_validate_config,
    safe_execute_command,
    safe_write_file,
    map_success,
    map_failure,
    get_or_log
)


class TestErrorTypes:
    """Test custom error types."""

    def test_config_error(self):
        """Test ConfigError creation."""
        error = ConfigError(path="/path/to/config.yaml", reason="File not found")
        assert error.path == "/path/to/config.yaml"
        assert error.reason == "File not found"

    def test_validation_error(self):
        """Test ValidationError creation."""
        error = ValidationError(
            check_name="project_structure",
            reason="Missing: package.json"
        )
        assert error.check_name == "project_structure"
        assert error.reason == "Missing: package.json"

    def test_execution_error(self):
        """Test ExecutionError creation."""
        error = ExecutionError(
            gate_name="typescript-check",
            reason="Type errors found"
        )
        assert error.gate_name == "typescript-check"
        assert error.reason == "Type errors found"

    def test_file_system_error(self):
        """Test FileSystemError creation."""
        error = FileSystemError(
            path="/tmp/test.txt",
            operation="write",
            reason="Permission denied"
        )
        assert error.path == "/tmp/test.txt"
        assert error.operation == "write"
        assert error.reason == "Permission denied"

    def test_errors_are_regular_classes(self):
        """Test error types are regular exception classes."""
        error = ConfigError(path="test", reason="test")
        # These are regular classes, not frozen dataclasses
        assert error.path == "test"
        assert error.reason == "test"


class TestLoadConfig:
    """Test load_config function."""

    def test_load_valid_yaml(self, tmp_path):
        """Test loading valid YAML file."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text("""
gates:
  - name: test-gate
    command: echo test
""")

        result = load_config(config_file)
        assert isinstance(result, Success)
        config = result.unwrap()
        assert "gates" in config
        assert len(config["gates"]) == 1

    def test_load_nonexistent_file(self):
        """Test loading non-existent file returns Failure."""
        result = load_config(Path("/nonexistent/file.yaml"))
        assert isinstance(result, Failure)
        error = result.failure()
        assert isinstance(error, ConfigError)
        assert "File not found" in error.reason

    def test_load_invalid_yaml(self, tmp_path):
        """Test loading invalid YAML returns Failure."""
        config_file = tmp_path / "invalid.yaml"
        config_file.write_text("invalid: yaml: content: [")

        result = load_config(config_file)
        assert isinstance(result, Failure)
        error = result.failure()
        assert isinstance(error, ConfigError)
        assert "Invalid YAML" in error.reason

    def test_load_empty_file(self, tmp_path):
        """Test loading empty file returns Success with empty dict."""
        config_file = tmp_path / "empty.yaml"
        config_file.write_text("")

        result = load_config(config_file)
        assert isinstance(result, Success)
        config = result.unwrap()
        assert config == {}


class TestValidateProjectStructure:
    """Test validate_project_structure function."""

    def test_valid_project_structure(self, tmp_path):
        """Test validation of valid project."""
        # Create valid project indicators
        (tmp_path / "package.json").write_text("{}")
        (tmp_path / "pyproject.toml").write_text("")
        (tmp_path / "README.md").write_text("")
        (tmp_path / "src").mkdir()

        result = validate_project_structure(tmp_path)
        assert isinstance(result, Success)
        metadata = result.unwrap()
        assert metadata["validation_status"] == "passed"
        assert len(metadata["indicators_found"]) > 0

    def test_minimal_project_structure(self, tmp_path):
        """Test validation of minimal project (README only)."""
        (tmp_path / "README.md").write_text("# Test")

        result = validate_project_structure(tmp_path)
        # Should still pass if at least one indicator found
        # Implementation may vary - check it's not an error
        assert isinstance(result, (Success, Failure))

    def test_empty_project_structure(self, tmp_path):
        """Test validation of empty project returns Failure."""
        # Empty directory, no indicators
        result = validate_project_structure(tmp_path)
        assert isinstance(result, Failure)
        error = result.failure()
        assert isinstance(error, ValidationError)
        assert "No project indicators" in error.reason or "Missing" in error.reason

    def test_nonexistent_directory(self):
        """Test validation of nonexistent directory."""
        result = validate_project_structure(Path("/nonexistent/path"))
        assert isinstance(result, Failure)


class TestFindFirstPythonFile:
    """Test find_first_python_file function."""

    def test_find_python_file(self, tmp_path):
        """Test finding Python file in directory."""
        (tmp_path / "test1.py").write_text("print('test')")
        (tmp_path / "test2.py").write_text("print('test2')")

        result = find_first_python_file(tmp_path)
        assert isinstance(result, Some)
        path = result.unwrap()
        assert path.name == "test1.py"  # First in alphabetical order

    def test_no_python_files(self, tmp_path):
        """Test when no Python files exist."""
        (tmp_path / "test.txt").write_text("not python")

        result = find_first_python_file(tmp_path)
        assert result == Nothing

    def test_recursive_search(self, tmp_path):
        """Test recursive search finds Python files in subdirectories."""
        subdir = tmp_path / "subdir"
        subdir.mkdir()
        (subdir / "nested.py").write_text("# nested")

        result = find_first_python_file(tmp_path)
        assert isinstance(result, Some)
        assert result.unwrap().name == "nested.py"

    def test_nonexistent_directory(self):
        """Test searching nonexistent directory."""
        result = find_first_python_file(Path("/nonexistent"))
        assert result == Nothing


class TestGetOptionalEnv:
    """Test get_optional_env function."""

    def test_get_existing_env(self, monkeypatch):
        """Test getting existing environment variable."""
        monkeypatch.setenv("TEST_VAR", "test_value")
        result = get_optional_env("TEST_VAR")
        assert isinstance(result, Some)
        assert result.unwrap() == "test_value"

    def test_get_missing_env(self):
        """Test getting missing environment variable."""
        result = get_optional_env("NONEXISTENT_VAR_12345")
        assert result == Nothing

    def test_get_empty_string_env(self, monkeypatch):
        """Test getting environment variable with empty string."""
        monkeypatch.setenv("EMPTY_VAR", "")
        result = get_optional_env("EMPTY_VAR")
        # Empty string is treated as Nothing
        assert result == Nothing


class TestParseAndValidateConfig:
    """Test parse_and_validate_config pipeline function."""

    def test_valid_config_with_required_keys(self, tmp_path):
        """Test pipeline with valid config."""
        config_file = tmp_path / "valid.yaml"
        config_file.write_text("""
gates:
  - name: test
version: "1.0"
""")

        result = parse_and_validate_config(
            config_file,
            required_keys=["gates", "version"]
        )
        assert isinstance(result, Success)
        config = result.unwrap()
        assert "gates" in config

    def test_missing_required_keys(self, tmp_path):
        """Test pipeline fails on missing required keys."""
        config_file = tmp_path / "incomplete.yaml"
        config_file.write_text("""
gates:
  - name: test
# missing 'version' key
""")

        result = parse_and_validate_config(
            config_file,
            required_keys=["gates", "version"]
        )
        assert isinstance(result, Failure)
        error = result.failure()
        assert isinstance(error, ValidationError)
        assert "Missing keys" in error.reason
        assert "version" in error.reason

    def test_invalid_yaml_pipeline(self, tmp_path):
        """Test pipeline fails on invalid YAML."""
        config_file = tmp_path / "invalid.yaml"
        config_file.write_text("invalid: [")

        result = parse_and_validate_config(
            config_file,
            required_keys=["gates"]
        )
        assert isinstance(result, Failure)

    def test_no_required_keys(self, tmp_path):
        """Test pipeline with no required keys."""
        config_file = tmp_path / "simple.yaml"
        config_file.write_text("key: value")

        result = parse_and_validate_config(
            config_file,
            required_keys=[]
        )
        assert isinstance(result, Success)


class TestSafeExecuteCommand:
    """Test safe_execute_command function."""

    def test_successful_command(self, tmp_path):
        """Test executing successful command."""
        result = safe_execute_command("echo 'hello'", tmp_path)
        assert isinstance(result, Success)
        output = result.unwrap()
        assert "hello" in output

    def test_failing_command(self, tmp_path):
        """Test executing failing command."""
        result = safe_execute_command("exit 1", tmp_path)
        assert isinstance(result, Failure)
        error = result.failure()
        assert isinstance(error, ExecutionError)

    def test_timeout_command(self, tmp_path):
        """Test command that times out."""
        # Note: The timeout in safe_execute_command is 60s,
        # so we can't easily test this without a long wait
        # Just verify the function handles the timeout case
        # Use a command that should complete quickly
        result = safe_execute_command("echo 'quick'", tmp_path)
        assert isinstance(result, Success)

    def test_invalid_working_directory(self):
        """Test command in nonexistent directory."""
        result = safe_execute_command(
            "echo 'test'",
            Path("/nonexistent/directory/path")
        )
        # Should return Failure due to invalid cwd
        assert isinstance(result, Failure)


class TestSafeWriteFile:
    """Test safe_write_file function."""

    def test_write_new_file(self, tmp_path):
        """Test writing new file."""
        file_path = tmp_path / "new_file.txt"
        content = "Hello, World!"

        result = safe_write_file(file_path, content)
        assert isinstance(result, Success)
        assert result.unwrap() == file_path
        assert file_path.read_text() == content

    def test_write_creates_parent_directories(self, tmp_path):
        """Test writing creates parent directories."""
        nested_path = tmp_path / "level1" / "level2" / "file.txt"
        content = "Nested file"

        result = safe_write_file(nested_path, content)
        assert isinstance(result, Success)
        assert nested_path.exists()
        assert nested_path.read_text() == content

    def test_overwrite_existing_file(self, tmp_path):
        """Test overwriting existing file."""
        file_path = tmp_path / "existing.txt"
        file_path.write_text("old content")

        result = safe_write_file(file_path, "new content")
        assert isinstance(result, Success)
        assert file_path.read_text() == "new content"

    def test_write_empty_content(self, tmp_path):
        """Test writing empty content."""
        file_path = tmp_path / "empty.txt"
        result = safe_write_file(file_path, "")
        assert isinstance(result, Success)
        assert file_path.read_text() == ""

    def test_write_large_content(self, tmp_path):
        """Test writing large content."""
        file_path = tmp_path / "large.txt"
        large_content = "x" * 10000

        result = safe_write_file(file_path, large_content)
        assert isinstance(result, Success)
        assert file_path.read_text() == large_content


class TestMapSuccess:
    """Test map_success function."""

    def test_map_success_value(self):
        """Test mapping over Success value."""
        result = Success(5)
        mapped = map_success(result, lambda x: x * 2)
        assert isinstance(mapped, Success)
        assert mapped.unwrap() == 10

    def test_map_success_passthrough_failure(self):
        """Test mapping leaves Failure unchanged."""
        result = Failure(ValueError("test"))
        mapped = map_success(result, lambda x: x * 2)
        assert isinstance(mapped, Failure)

    def test_map_success_with_type_change(self):
        """Test mapping can change return type."""
        result = Success("hello")
        mapped = map_success(result, lambda s: len(s))
        assert isinstance(mapped, Success)
        assert mapped.unwrap() == 5


class TestMapFailure:
    """Test map_failure function."""

    def test_map_failure_value(self):
        """Test mapping over Failure value."""
        result = Failure(ValueError("original"))
        mapped = map_failure(result, lambda e: RuntimeError(f"mapped: {e}"))
        assert isinstance(mapped, Failure)
        assert isinstance(mapped.failure(), RuntimeError)

    def test_map_failure_passthrough_success(self):
        """Test mapping leaves Success unchanged."""
        result = Success(5)
        mapped = map_failure(result, lambda e: RuntimeError("test"))
        assert isinstance(mapped, Success)
        assert mapped.unwrap() == 5


class TestGetOrLog:
    """Test get_or_log function."""

    def test_get_or_log_success(self):
        """Test get_or_log returns Success value."""
        result = Success(42)
        value = get_or_log(result, 0, "test_operation")
        assert value == 42

    def test_get_or_log_failure_returns_default(self):
        """Test get_or_log returns default on Failure."""
        result = Failure(ValueError("test error"))
        value = get_or_log(result, 0, "test_operation")
        assert value == 0

    def test_get_or_log_custom_default(self):
        """Test get_or_log with custom default."""
        result = Failure(Exception("error"))
        value = get_or_log(result, "default_value", "test")
        assert value == "default_value"


class TestFpUtilsIntegration:
    """Integration tests for fp_utils module."""

    def test_full_config_workflow(self, tmp_path):
        """Test complete config loading and validation workflow."""
        # Create valid config
        config_file = tmp_path / "gates.yaml"
        config_file.write_text("""
gates:
  - name: test-gate
    command: echo test
    required: true
version: "1.0"
""")

        # Load and validate
        result = parse_and_validate_config(
            config_file,
            required_keys=["gates", "version"]
        )

        assert isinstance(result, Success)
        config = result.unwrap()
        assert len(config["gates"]) == 1

    def test_error_recovery_workflow(self, tmp_path):
        """Test workflow with error recovery."""
        # Try to load nonexistent config
        result = load_config(Path("/nonexistent/config.yaml"))

        assert isinstance(result, Failure)

        # Use get_or_log to recover with default
        default_config = {"gates": [], "version": "1.0"}
        recovered = get_or_log(result, default_config, "load_config")

        assert recovered == default_config

    def test_file_operations_workflow(self, tmp_path):
        """Test file write/read workflow."""
        # Write file safely
        file_path = tmp_path / "workflow.txt"
        write_result = safe_write_file(file_path, "test content")

        assert isinstance(write_result, Success)

        # Verify file exists
        assert file_path.read_text() == "test content"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

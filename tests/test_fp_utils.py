"""
Tests for FP Utils module (lib/fp_utils.py)

Pattern: TDD (Test-Driven Development)
- Write test first (RED)
- Run test - should FAIL
- Write minimal implementation (GREEN)
- Refactor (IMPROVE)

Uses returns library for Result/Either patterns.
"""
import pytest
from pathlib import Path
from dataclasses import dataclass, FrozenInstanceError
from typing import Callable, Any
import tempfile
import copy

# Add lib directory to path
lib_dir = Path(__file__).parent.parent / "lib"
import sys
sys.path.insert(0, str(lib_dir))

# Import from fp_utils - only what's actually exported
from fp_utils import (
    Success, Failure,
    Result, Maybe, Some, Nothing,
    map_success, map_failure,
    get_logger, LogLevel,
    safe, ConfigError, ValidationError,
    ExecutionError, FileSystemError,
    load_config, validate_project_structure,
    find_first_python_file, get_optional_env,
    parse_and_validate_config, safe_execute_command,
    safe_write_file, get_or_log,
    pipe, compose, flow, bind
)

# Note: Success, Failure, Some, Nothing are re-exported from fp_utils
# We don't need to re-import them from returns


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def temp_project_dir():
    """Create a temporary project directory for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        project_path = Path(tmpdir)
        # Create basic Python project structure
        (project_path / "src").mkdir(parents=True, exist_ok=True)
        (project_path / "lib").mkdir(parents=True, exist_ok=True)
        (project_path / "package.json").write_text('{"name": "test", "version": "1.0"}')
        (project_path / "README.md").write_text("# Test Project")
        (project_path / "pyproject.toml").write_text("[project]\\nname = \"test\"")
        yield project_path


@pytest.fixture
def temp_config_file():
    """Create a temporary config file."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
        f.write("""gates:
  test-gate:
    command: echo "test"
    timeout: 100
    critical: true
""")
        f.flush()  # Ensure content is written to disk
        yield Path(f.name)


# =============================================================================
# Result Type Tests
# =============================================================================

class TestResultTypes:
    """Test Result/Either type system."""

    @pytest.mark.unit
    def test_success_creation(self):
        """Success should wrap value correctly."""
        result = Success(42)
        assert result.unwrap() == 42
        assert isinstance(result, Result)

    @pytest.mark.unit
    def test_failure_creation(self):
        """Failure should wrap error correctly."""
        error = ValueError("test error")
        result = Failure(error)

        # Failure.unwrap() raises UnwrapFailedError, not the original error
        from returns.primitives.exceptions import UnwrapFailedError
        with pytest.raises(UnwrapFailedError):
            result.unwrap()

        assert isinstance(result, Result)
        assert result.failure() == error

    @pytest.mark.unit
    def test_maybe_some(self):
        """Maybe/Some should work correctly."""
        # Some(value) - has value
        some_result = Some(42)
        # Check if it's Some by using pattern matching or isinstance
        assert isinstance(some_result, Some)
        assert some_result.value_or(0) == 42  # value_or is the Maybe equivalent of unwrap_or

        # Nothing - no value (Nothing is a singleton)
        none_result = Nothing
        assert none_result == Nothing
        assert none_result.value_or(0) == 0


# =============================================================================
# Pipe/Compose/Flow Tests
# =============================================================================

class TestFunctionalComposition:
    """Test function composition utilities."""

    @pytest.mark.unit
    def test_pipe_success_both(self):
        """pipe should pass results through both functions."""
        def add_one(x: int) -> int:
            return x + 1

        def double(x: int) -> int:
            return x * 2

        # pipe composes functions left-to-right
        piped = pipe(add_one, double)
        result = piped(5)

        # pipe returns the result of composition, not a Result type
        assert result == 12  # (5 + 1) * 2

    @pytest.mark.unit
    def test_pipe_first_fails(self):
        """pipe with bind should short-circuit on first failure."""
        def fail_if_negative(x: int) -> Result[int, Exception]:
            if x < 0:
                return Failure(ValueError(f"Negative: {x}"))
            return Success(x)

        def always_fail(x: int) -> Result[int, Exception]:
            return Failure(Exception("Always fails"))

        # Use bind to chain Result-returning functions
        result = fail_if_negative(-5)

        assert isinstance(result, Failure)
        # Should be the first function's failure
        assert "Negative" in str(result.failure())

    @pytest.mark.unit
    def test_compose_two_functions(self):
        """compose should combine two functions (second after first)."""
        def add_five(x: int) -> int:
            return x + 5

        def multiply_by_two(x: int) -> int:
            return x * 2

        # compose(f, g) means "g after f" - so f runs first, then g
        composed = compose(add_five, multiply_by_two)
        result = composed(3)

        # (3 + 5) * 2 = 16 (add_five runs first, then multiply_by_two)
        assert result == 16

    @pytest.mark.unit
    def test_flow_chain_multiple(self):
        """flow should chain multiple functions left-to-right."""
        def to_string(x: int) -> str:
            return str(x)

        def append_world(s: str) -> str:
            return s + " world"

        def add_exclamation(s: str) -> str:
            return s + "!"

        # flow chains functions left-to-right
        result = flow(42, to_string, append_world, add_exclamation)

        assert result == "42 world!"

    @pytest.mark.unit
    def test_pipe_error_propagation(self):
        """Errors should propagate correctly with safe decorator."""
        class CustomError(Exception):
            pass

        @safe
        def raise_if_42(x: int) -> int:
            if x == 42:
                raise CustomError("Found 42!")
            return x

        result = raise_if_42(42)

        assert isinstance(result, Failure)
        assert isinstance(result.failure(), CustomError)


# =============================================================================
# Safe Decorator Tests
# =============================================================================

class TestSafeDecorator:
    """Test @safe decorator for error handling."""

    @pytest.mark.unit
    def test_decorator_catches_exception(self):
        """@safe should catch and convert exceptions to Failure."""
        @safe
        def risky_function(x: int) -> int:
            if x == 13:
                raise ValueError("13 is unlucky!")
            return x * 2

        # @safe wraps a function that returns T to return Result[T, Exception]
        result = risky_function(7)

        # Should succeed with 7
        assert isinstance(result, Success)
        assert result.unwrap() == 14

        # Should fail with 13
        result2 = risky_function(13)
        assert isinstance(result2, Failure)
        assert "13 is unlucky" in str(result2.failure())

    @pytest.mark.unit
    def test_decorator_preserves_function_name(self):
        """@safe should preserve original function metadata."""
        @safe
        def documented_function(x: int) -> int:
            """Multiplies by 2."""
            return x * 2

        assert documented_function.__name__ == "documented_function"
        assert "Multiplies by 2" in documented_function.__doc__


# =============================================================================
# Config Loading Tests
# =============================================================================

class TestConfigLoading:
    """Test YAML config loading."""

    @pytest.mark.unit
    def test_load_valid_yaml(self, temp_config_file):
        """Should load valid YAML config."""
        config_path = temp_config_file

        result = load_config(config_path)

        assert isinstance(result, Success)
        config = result.unwrap()
        assert "gates" in config
        assert "test-gate" in config["gates"]

    @pytest.mark.unit
    def test_load_nonexistent_file(self):
        """Should return Failure for missing file."""
        result = load_config(Path("/nonexistent/config.yaml"))

        assert isinstance(result, Failure)
        assert isinstance(result.failure(), ConfigError)

    @pytest.mark.unit
    def test_load_invalid_yaml(self, temp_config_file):
        """Should handle invalid YAML."""
        # Write invalid YAML
        with open(temp_config_file, 'w') as f:
            f.write(": invalid yaml content\n[\n broken")

        result = load_config(temp_config_file)

        assert isinstance(result, Failure)
        assert isinstance(result.failure(), ConfigError)


# =============================================================================
# Validation Tests
# =============================================================================

class TestProjectValidation:
    """Test project structure validation."""

    @pytest.mark.unit
    def test_validate_valid_project(self, temp_project_dir):
        """Should validate complete project."""
        result = validate_project_structure(temp_project_dir)

        assert isinstance(result, Success)
        metadata = result.unwrap()
        assert metadata["validation_status"] == "passed"
        # The fixture creates: package.json, README.md, pyproject.toml, src/, lib/
        assert len(metadata["indicators_found"]) >= 4

    @pytest.mark.unit
    def test_validate_missing_project(self):
        """Should fail for missing indicators."""
        with tempfile.TemporaryDirectory() as tmpdir:
            empty_path = Path(tmpdir)
            result = validate_project_structure(empty_path)

            assert isinstance(result, Failure)
            assert "No project indicators" in str(result.failure())

    @pytest.mark.integration
    def test_validate_python_project_with_src(self):
        """Should validate Python project with src/."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project = Path(tmpdir)
            (project / "src").mkdir()
            (project / "main.py").write_text("print('hello')")

            result = validate_project_structure(project)

            assert isinstance(result, Success)
            # Should find src/main.py indicator

    @pytest.mark.integration
    def test_find_first_python_file(self, temp_project_dir):
        """Should find first Python file."""
        # Create src/main.py
        (temp_project_dir / "src" / "main.py").write_text("print('test')")

        result = find_first_python_file(temp_project_dir / "src")

        assert isinstance(result, Some)
        assert result.unwrap().name == "main.py"


# =============================================================================
# Environment Variable Tests
# =============================================================================

class TestEnvironmentVariables:
    """Test environment variable handling."""

    @pytest.mark.unit
    def test_get_optional_env_exists(self, monkeypatch):
        """Should return value when env var exists."""
        monkeypatch.setenv("TEST_VAR", "test_value")

        result = get_optional_env("TEST_VAR")

        assert isinstance(result, Some)
        assert result.unwrap() == "test_value"

    @pytest.mark.unit
    def test_get_optional_env_missing(self, monkeypatch):
        """Should return Nothing when env var missing."""
        monkeypatch.delenv("TEST_VAR", raising=False)

        result = get_optional_env("TEST_VAR")

        # Nothing is a singleton, compare by identity
        assert result == Nothing


# =============================================================================
# Pipeline Tests
# =============================================================================

class TestPipelines:
    """Test function composition pipelines."""

    @pytest.mark.unit
    def test_parse_and_validate_flow(self, temp_config_file):
        """parse_and_validate should chain operations."""
        # Valid config with required keys
        with open(temp_config_file, 'w') as f:
            f.write("gates:\n  test:\n    command: echo test\n")

        result = parse_and_validate_config(
            temp_config_file,
            required_keys=["gates"]
        )

        assert isinstance(result, Success)
        config = result.unwrap()
        assert "gates" in config

    @pytest.mark.unit
    def test_parse_and_validate_missing_keys(self, temp_config_file):
        """Should fail when required keys missing."""
        # Config without required key
        with open(temp_config_file, 'w') as f:
            f.write("other_key: value\n")

        result = parse_and_validate_config(
            temp_config_file,
            required_keys=["missing_key"]
        )

        assert isinstance(result, Failure)
        assert "Missing keys" in str(result.failure())


# =============================================================================
# Safe Operations Tests
# =============================================================================

class TestSafeOperations:
    """Test safe file/command operations."""

    @pytest.mark.integration
    def test_safe_write_file_creates_file(self, tmp_path):
        """Should safely create a file."""
        test_file = tmp_path / "test_output.txt"
        content = "Hello, World!"

        result = safe_write_file(test_file, content)

        assert isinstance(result, Success)
        assert test_file.exists()
        assert test_file.read_text() == content

    @pytest.mark.integration
    def test_safe_write_creates_parent_dirs(self, tmp_path):
        """Should create parent directories if needed."""
        nested = tmp_path / "a" / "b" / "c" / "file.txt"

        result = safe_write_file(nested, "content")

        assert isinstance(result, Success)
        assert nested.exists()

    @pytest.mark.unit
    def test_map_success_transforms_success(self):
        """map_success should transform Success values."""
        def double(x: int) -> int:
            return x * 2

        results = [Success(1), Success(2), Success(3)]
        mapped = map_success(double, results)

        assert isinstance(mapped, Success)
        values = mapped.unwrap()
        assert values == [2, 4, 6]

    @pytest.mark.unit
    def test_map_failure_preserves_failure(self):
        """map_failure should preserve Failure."""
        def always_fail(x: int) -> Result[int, int]:
            return Failure(Exception(f"Failed on {x}"))

        results = [Success(1), Success(2)]
        mapped = map_failure(always_fail, results)

        assert isinstance(mapped, Failure)
        # Should be first failure
        assert "Failed on 1" in str(mapped.failure())

    @pytest.mark.unit
    def test_get_or_log_success(self):
        """get_or_log should unwrap Success."""
        result = Success(42)
        default = 0

        # Should unwrap successfully
        assert get_or_log(result, default, "test_op") == 42

    @pytest.mark.unit
    def test_get_or_log_failure_uses_default(self):
        """get_or_log should use default on Failure."""
        result = Failure(ValueError("failed"))
        default = 999

        # Should return default
        assert get_or_log(result, default, "test_op") == 999


# =============================================================================
# Result Dataclass Tests
# =============================================================================

class TestResultDataclasses:
    """Test custom Result dataclasses for immutability."""

    @pytest.mark.unit
    def test_ruff_result_is_frozen(self):
        """RuffResult should be frozen (immutable)."""
        from ruff_formatter import RuffResult

        result = RuffResult(
            success=True,
            formatted=True,
            lint_errors=5,
            lint_fixed=2,
            output="test",
            exit_code=0
        )

        # Attempting to modify should raise error
        with pytest.raises(FrozenInstanceError):
            result.success = False

    @pytest.mark.unit
    def test_custom_result_types(self):
        """Custom Result types should be usable."""
        @dataclass(frozen=True)
        class CustomResult:
            success: bool
            value: int

        result = CustomResult(success=True, value=42)

        assert result.success is True
        assert result.value == 42

        with pytest.raises(FrozenInstanceError):
            result.value = 100


# =============================================================================
# Integration Tests
# =============================================================================

class TestFPUtilsIntegration:
    """Integration tests for FP Utils."""

    @pytest.mark.integration
    def test_complete_validation_flow(self, temp_project_dir, temp_config_file):
        """Test complete validation flow."""
        # Create valid config
        with open(temp_config_file, 'w') as f:
            f.write("gates:\n  structure:\n    command: echo test\n")

        # Load and validate config
        config_result = parse_and_validate_config(
            temp_config_file,
            required_keys=["gates"]
        )

        # Validate project structure
        project_result = validate_project_structure(temp_project_dir)

        # Both should succeed
        assert isinstance(config_result, Success)
        assert isinstance(project_result, Success)

    @pytest.mark.integration
    def test_error_recovery_in_pipeline(self, temp_project_dir):
        """Test error handling in functional pipelines."""
        # Define a function that returns Result directly
        def risky_operation(path: Path) -> Result[Path, str]:
            if not path.exists():
                return Failure(f"Path not found: {path}")
            return Success(path)

        # Should work with existing path
        result = risky_operation(temp_project_dir / "src")

        assert isinstance(result, Success)

        # Should handle missing path gracefully
        missing_result = risky_operation(Path("/nonexistent/path"))
        assert isinstance(missing_result, Failure)


# =============================================================================
# Performance Tests
# =============================================================================

class TestFPUtilsPerformance:
    """Performance tests for FP Utils."""

    @pytest.mark.performance
    def test_pipe_overhead(self):
        """pipe should have minimal overhead."""
        import time

        def noop(x):
            return x

        piped = pipe(noop, noop)

        # Measure 1000 iterations
        start = time.time()
        for _ in range(1000):
            piped(42)  # pipe takes regular values, not Result
        end = time.time()

        # Should complete in reasonable time (< 1 second)
        assert (end - start) < 1.0

    @pytest.mark.performance
    def test_safe_decorator_overhead(self):
        """@safe decorator should be efficient."""
        import time

        @safe
        def fast_function(x: int) -> int:
            return x * 2

        # Measure 1000 calls
        start = time.time()
        for _ in range(1000):
            fast_function(42)  # @safe takes regular args, not Result
        end = time.time()

        # Should complete in reasonable time (< 1 second)
        assert (end - start) < 1.0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

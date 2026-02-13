#!/usr/bin/env python3
"""
Tests for Ruff formatter module.

Tests the wrapper module that provides formatting and linting
via ruff (replaces black, flake8, isort).
"""
import sys
import pytest
from pathlib import Path
import tempfile
from unittest.mock import patch, Mock
import subprocess

# Add lib directory to path
lib_dir = Path(__file__).parent.parent / "lib"
sys.path.insert(0, str(lib_dir))

from ruff_formatter import RuffFormatter, RuffResult


class TestRuffResult:
    """Test RuffResult dataclass."""

    def test_ruff_result_is_frozen(self):
        """Test that RuffResult is frozen (immutable)."""
        result = RuffResult(
            success=True,
            formatted=True,
            lint_errors=0,
            lint_fixed=2,
            output="All good",
            exit_code=0
        )

        # Attempting to modify should raise AttributeError
        with pytest.raises((AttributeError, TypeError)):
            result.success = False

    def test_ruff_result_all_fields(self):
        """Test that RuffResult has all expected fields."""
        result = RuffResult(
            success=True,
            formatted=True,
            lint_errors=5,
            lint_fixed=3,
            output="Some output",
            exit_code=1
        )

        assert result.success is True
        assert result.formatted is True
        assert result.lint_errors == 5
        assert result.lint_fixed == 3
        assert result.output == "Some output"
        assert result.exit_code == 1


class TestRuffFormatter:
    """Test RuffFormatter wrapper."""

    @patch('subprocess.run')
    def test_format_file_success(self, mock_run):
        """Test successful file formatting."""
        mock_run.return_value = Mock(
            returncode=0,
            stdout="1 file formatted",
            stderr=""
        )

        formatter = RuffFormatter()
        result = formatter.format_file(Path("test.py"))

        assert result.success is True
        assert result.formatted is True
        assert result.exit_code == 0
        mock_run.assert_called_once()

    @patch('subprocess.run')
    def test_format_file_no_changes_needed(self, mock_run):
        """Test formatting when file is already correct."""
        mock_run.return_value = Mock(
            returncode=0,
            stdout="",  # No output means no changes
            stderr=""
        )

        formatter = RuffFormatter()
        result = formatter.format_file(Path("test.py"))

        assert result.success is True
        assert result.formatted is False  # No changes made
        mock_run.assert_called_once()

    @patch('subprocess.run')
    def test_check_and_fix_with_errors(self, mock_run):
        """Test check with auto-fix."""
        mock_run.return_value = Mock(
            returncode=1,
            stdout="Found 3 errors, fixed 2",
            stderr=""
        )

        formatter = RuffFormatter()
        result = formatter.check_and_fix(Path("test.py"))

        assert result.success is False
        assert result.lint_fixed > 0

    @patch('subprocess.run')
    def test_check_and_fix_no_fix_flag(self, mock_run):
        """Test check without --fix flag."""
        mock_run.return_value = Mock(
            returncode=1,
            stdout="Found 3 errors",
            stderr=""
        )

        formatter = RuffFormatter()
        result = formatter.check_and_fix(Path("test.py"), fix=False)

        # Should call ruff without --fix
        call_args = mock_run.call_args[0][0]
        assert "--fix" not in call_args

    @patch('subprocess.run')
    def test_format_and_check_combined(self, mock_run):
        """Test combined format + check operation."""
        mock_run.return_value = Mock(
            returncode=0,
            stdout="",
            stderr=""
        )

        formatter = RuffFormatter()
        result = formatter.format_and_check(Path("test.py"))

        # Should call subprocess twice (format + check)
        assert mock_run.call_count == 2
        assert result.success is True

    @patch('subprocess.run')
    def test_format_file_timeout(self, mock_run):
        """Test timeout handling during format."""
        from subprocess import TimeoutExpired

        mock_run.side_effect = TimeoutExpired("ruff", 10)

        formatter = RuffFormatter()
        result = formatter.format_file(Path("test.py"))

        assert result.success is False
        assert "timed out" in result.output.lower()
        assert result.exit_code == -1

    @patch('subprocess.run')
    def test_ruff_not_found(self, mock_run):
        """Test handling when ruff is not installed."""
        mock_run.side_effect = FileNotFoundError()

        formatter = RuffFormatter()
        result = formatter.format_file(Path("test.py"))

        assert result.success is False
        assert "not found" in result.output.lower()
        assert result.exit_code == -2

    @patch('subprocess.run')
    def test_check_with_custom_config(self, mock_run):
        """Test formatter with custom config path."""
        mock_run.return_value = Mock(
            returncode=0,
            stdout="",
            stderr=""
        )

        config_path = Path("/custom/ruff.toml")
        formatter = RuffFormatter(config_path=config_path)
        formatter.format_file(Path("test.py"))

        # Should include config flag
        call_args = mock_run.call_args[0][0]
        assert f"--config={config_path}" in " ".join(call_args)

    @patch('subprocess.run')
    def test_check_directory_instead_of_file(self, mock_run):
        """Test check_and_fix with directory instead of file."""
        mock_run.return_value = Mock(
            returncode=0,
            stdout="",
            stderr=""
        )

        formatter = RuffFormatter()
        result = formatter.check_and_fix()  # No file path

        # Should check current directory
        call_args = mock_run.call_args[0][0]
        assert "." in call_args or str(Path.cwd()) in call_args

    @patch('subprocess.run')
    def test_is_available_true(self, mock_run):
        """Test is_available returns True when ruff exists."""
        mock_run.return_value = Mock(
            returncode=0,
            stdout="ruff 0.8.0",
            stderr=""
        )

        formatter = RuffFormatter()
        assert formatter.is_available() is True

    @patch('subprocess.run')
    def test_is_available_false(self, mock_run):
        """Test is_available returns False when ruff missing."""
        mock_run.side_effect = FileNotFoundError()

        formatter = RuffFormatter()
        assert formatter.is_available() is False


@pytest.mark.unit
def test_default_target_version():
    """Test that default target version is py314."""
    formatter = RuffFormatter()
    assert formatter.target_version == "py314"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

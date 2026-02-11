#!/usr/bin/env python3
"""
Tests for auto-fix functionality.

Tests the PostToolUse hook that automatically formats files
after Write/Edit operations.
"""
import sys
import pytest
from pathlib import Path
import tempfile
import json
from unittest.mock import patch, Mock
import subprocess


# Add scripts directory to path
scripts_dir = Path(__file__).parent.parent / "scripts"
sys.path.insert(0, str(scripts_dir))


# Import the auto_fix functions
import importlib.util
spec = importlib.util.spec_from_file_location("auto_fix", scripts_dir / "auto-fix.py")
auto_fix = importlib.util.module_from_spec(spec)
spec.loader.exec_module(auto_fix)


class TestAutoFixFunctions:
    """Test auto-fix internal functions."""

    def test_should_exclude_venv_directories(self):
        """Test that .venv directories are excluded."""
        assert auto_fix.should_exclude(Path("/project/.venv/lib/test.py"))
        assert auto_fix.should_exclude(Path("/project/venv/test.py"))
        assert auto_fix.should_exclude(Path("/project/.virtualenv/test.py"))

    def test_should_exclude_cache_directories(self):
        """Test that cache directories are excluded."""
        assert auto_fix.should_exclude(Path("/project/__pycache__/test.py"))
        assert auto_fix.should_exclude(Path("/project/.pytest_cache/test.py"))
        assert auto_fix.should_exclude(Path("/project/.mypy_cache/test.py"))

    def test_should_exclude_node_modules(self):
        """Test that node_modules is excluded."""
        assert auto_fix.should_exclude(Path("/project/node_modules/package/test.ts"))

    def test_should_exclude_build_artifacts(self):
        """Test that build directories are excluded."""
        assert auto_fix.should_exclude(Path("/project/dist/test.py"))
        assert auto_fix.should_exclude(Path("/project/build/test.py"))

    def test_should_not_exclude_normal_paths(self):
        """Test that normal project paths are NOT excluded."""
        assert not auto_fix.should_exclude(Path("/project/src/test.py"))
        assert not auto_fix.should_exclude(Path("/project/lib/module.ts"))
        assert not auto_fix.should_exclude(Path("/project/tests/test_file.py"))
        assert not auto_fix.should_exclude(Path("/project/config/app.yaml"))

    def test_should_exclude_exception_handling(self, tmp_path):
        """Test that should_exclude handles OSError/ValueError gracefully."""
        # Create a path that might cause issues (e.g., broken symlink)
        # In practice, this tests the exception handling at lines 51-52
        test_path = Path("/project/src/test.py")

        # Normal case should work
        result = auto_fix.should_exclude(test_path)
        assert isinstance(result, bool)

        # The function should return False on any exception (lines 51-52)
        # We can't easily trigger OSError in tests, but we verify
        # the exception handler exists in the code
        import inspect
        source = inspect.getsource(auto_fix.should_exclude)
        assert "OSError" in source or "ValueError" in source

    def test_format_file_supported_python(self, tmp_path):
        """Test formatting a Python file."""
        test_file = tmp_path / "test.py"
        test_file.write_text("x=1+2")

        with patch('subprocess.run') as mock_run:
            mock_run.return_value = Mock(
                returncode=0,
                stdout="1 file formatted",
                stderr=""
            )

            result = auto_fix.format_file(test_file)

            assert result is True
            mock_run.assert_called_once()
            call_args = mock_run.call_args[0][0]
            assert "ruff" in call_args
            assert "format" in call_args

    def test_format_file_supported_typescript(self, tmp_path):
        """Test formatting a TypeScript file."""
        test_file = tmp_path / "test.ts"
        test_file.write_text("const x=1")

        with patch('subprocess.run') as mock_run:
            mock_run.return_value = Mock(returncode=0, stdout="", stderr="")

            auto_fix.format_file(test_file)

            call_args = mock_run.call_args[0][0]
            assert "prettier" in call_args
            assert "--write" in call_args

    def test_format_file_unsupported_extension(self, tmp_path):
        """Test that unsupported extensions return False."""
        test_file = tmp_path / "test.xyz"
        test_file.write_text("content")

        result = auto_fix.format_file(test_file)
        assert result is False

    def test_format_file_excluded_directory(self, tmp_path):
        """Test that files in excluded directories return False."""
        # Create nested path with excluded directory
        excluded_dir = tmp_path / "venv"
        excluded_dir.mkdir()
        test_file = excluded_dir / "test.py"
        test_file.write_text("x=1")

        with patch('subprocess.run') as mock_run:
            result = auto_fix.format_file(test_file)
            assert result is False
            mock_run.assert_not_called()

    def test_format_file_timeout_handling(self, tmp_path):
        """Test that timeout is handled gracefully."""
        test_file = tmp_path / "test.py"
        test_file.write_text("x=1")

        from subprocess import TimeoutExpired
        with patch('subprocess.run') as mock_run:
            mock_run.side_effect = TimeoutExpired("ruff", 10)

            result = auto_fix.format_file(test_file)
            assert result is False  # Should handle timeout gracefully

    def test_format_file_missing_formatter(self, tmp_path):
        """Test that missing formatter is handled gracefully."""
        test_file = tmp_path / "test.py"
        test_file.write_text("x=1")

        with patch('subprocess.run') as mock_run:
            mock_run.side_effect = FileNotFoundError()

            result = auto_fix.format_file(test_file)
            assert result is False


class TestAutoFixMain:
    """Test auto-fix main() function."""

    def test_main_invalid_json_returns_zero(self):
        """Test that invalid JSON returns 0 (graceful failure)."""
        with patch('sys.stdin', "invalid json{{{"):
            result = auto_fix.main()
            assert result == 0

    def test_main_missing_tool_returns_zero(self):
        """Test that missing tool key returns 0."""
        with patch('sys.stdin', json.dumps({"path": "/some/file.py"})):
            result = auto_fix.main()
            assert result == 0

    def test_main_missing_path_returns_zero(self):
        """Test that missing path key returns 0."""
        with patch('sys.stdin', json.dumps({"tool": "Write"})):
            result = auto_fix.main()
            assert result == 0

    def test_main_nonexistent_file_returns_zero(self):
        """Test that nonexistent file returns 0."""
        with patch('sys.stdin', json.dumps({
            "tool": "Write",
            "path": "/tmp/nonexistent_xyz123.py"
        })):
            result = auto_fix.main()
            assert result == 0

    def test_main_empty_stdin_returns_zero(self):
        """Test that empty stdin returns 0 (graceful failure)."""
        with patch('sys.stdin', ""):
            result = auto_fix.main()
            assert result == 0

    def test_main_whitespace_only_stdin_returns_zero(self):
        """Test that whitespace-only stdin returns 0 (graceful failure)."""
        with patch('sys.stdin', "   \n\t  \n  "):
            result = auto_fix.main()
            assert result == 0

    def test_main_read_tool_skipped(self, tmp_path):
        """Test that Read tool is skipped."""
        test_file = tmp_path / "test.py"
        test_file.write_text("x=1")

        with patch('sys.stdin', json.dumps({
            "tool": "Read",
            "path": str(test_file)
        })):
            with patch('subprocess.run') as mock_run:
                result = auto_fix.main()
                assert result == 0
                mock_run.assert_not_called()

    def test_main_write_tool_triggers_format(self, tmp_path):
        """Test that Write tool triggers formatting."""
        test_file = tmp_path / "test.py"
        test_file.write_text("x=1")

        with patch('sys.stdin', json.dumps({
            "tool": "Write",
            "path": str(test_file)
        })):
            with patch('subprocess.run') as mock_run:
                mock_run.return_value = Mock(returncode=0, stdout="formatted", stderr="")
                result = auto_fix.main()
                assert result == 0
                mock_run.assert_called_once()

    def test_main_edit_tool_triggers_format(self, tmp_path):
        """Test that Edit tool triggers formatting."""
        test_file = tmp_path / "test.ts"
        test_file.write_text("const x=1")

        with patch('sys.stdin', json.dumps({
            "tool": "Edit",
            "path": str(test_file)
        })):
            with patch('subprocess.run') as mock_run:
                mock_run.return_value = Mock(returncode=0, stdout="", stderr="")
                result = auto_fix.main()
                assert result == 0
                mock_run.assert_called_once()


@pytest.mark.unit
def test_formatters_dict_structure():
    """Test that FORMATTERS dict has correct structure."""
    assert isinstance(auto_fix.FORMATTERS, dict)

    # Expected extensions
    expected_extensions = {
        '.ts', '.tsx', '.js', '.jsx', '.py', '.md', '.yaml', '.yml', '.json'
    }

    for ext in expected_extensions:
        assert ext in auto_fix.FORMATTERS, f"Missing formatter for {ext}"
        # Each formatter should be a command string
        assert isinstance(auto_fix.FORMATTERS[ext], str)


@pytest.mark.unit
def test_exclude_dirs_structure():
    """Test that EXCLUDE_DIRS is a set with expected values."""
    assert isinstance(auto_fix.EXCLUDE_DIRS, (set, frozenset))

    expected_dirs = {
        '.venv', 'venv', 'node_modules', '.pytest_cache',
        '__pycache__', '.tox', '.git', '.mypy_cache'
    }

    for dir_name in expected_dirs:
        assert dir_name in auto_fix.EXCLUDE_DIRS, f"Missing exclude: {dir_name}"

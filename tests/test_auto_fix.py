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
from unittest.mock import patch, Mock, MagicMock
import subprocess


# Add lib directory to path for imports
lib_dir = Path(__file__).parent.parent / "lib"
sys.path.insert(0, str(lib_dir))

# Add scripts directory to path
scripts_dir = Path(__file__).parent.parent / "scripts"
sys.path.insert(0, str(scripts_dir))


# Import the auto_fix module
import importlib.util
spec = importlib.util.spec_from_file_location("auto_fix", scripts_dir / "auto-fix.py")
auto_fix = importlib.util.module_from_spec(spec)
spec.loader.exec_module(auto_fix)


@pytest.fixture
def hook():
    """Create an AutoFixHook instance for testing."""
    # Use actual plugin root for config files
    plugin_root = Path(__file__).parent.parent
    return auto_fix.AutoFixHook(plugin_root)


class TestAutoFixHook:
    """Test AutoFixHook class methods."""

    def test_should_exclude_venv_directories(self, hook):
        """Test that .venv directories are excluded."""
        assert hook.should_exclude(Path("/project/.venv/lib/test.py"))
        assert hook.should_exclude(Path("/project/venv/test.py"))
        assert hook.should_exclude(Path("/project/.virtualenv/test.py"))

    def test_should_exclude_cache_directories(self, hook):
        """Test that cache directories are excluded."""
        assert hook.should_exclude(Path("/project/__pycache__/test.py"))
        assert hook.should_exclude(Path("/project/.pytest_cache/test.py"))
        assert hook.should_exclude(Path("/project/.mypy_cache/test.py"))

    def test_should_exclude_node_modules(self, hook):
        """Test that node_modules is excluded."""
        assert hook.should_exclude(Path("/project/node_modules/package/test.ts"))

    def test_should_exclude_build_artifacts(self, hook):
        """Test that build directories are excluded."""
        assert hook.should_exclude(Path("/project/dist/test.py"))
        assert hook.should_exclude(Path("/project/build/test.py"))

    def test_should_not_exclude_normal_paths(self, hook):
        """Test that normal project paths are NOT excluded."""
        assert not hook.should_exclude(Path("/project/src/test.py"))
        assert not hook.should_exclude(Path("/project/lib/module.ts"))
        assert not hook.should_exclude(Path("/project/tests/test_file.py"))
        assert not hook.should_exclude(Path("/project/config/app.yaml"))

    def test_format_file_supported_python(self, hook, tmp_path):
        """Test formatting a Python file."""
        test_file = tmp_path / "test.py"
        test_file.write_text("x=1+2")

        with patch.object(hook, '_format_python_ruff') as mock_ruff:
            mock_ruff.return_value = (True, 'ruff')
            formatted, formatter = hook.format_file(test_file)
            assert formatted is True
            assert formatter == 'ruff'

    def test_format_file_supported_typescript(self, hook, tmp_path):
        """Test formatting a TypeScript file."""
        test_file = tmp_path / "test.ts"
        test_file.write_text("const x=1")

        with patch.object(hook, '_format_subprocess') as mock_sub:
            mock_sub.return_value = (True, 'prettier')
            formatted, formatter = hook.format_file(test_file)
            assert formatter == 'prettier'

    def test_format_file_unsupported_extension(self, hook, tmp_path):
        """Test that unsupported extensions return False."""
        test_file = tmp_path / "test.xyz"
        test_file.write_text("content")

        formatted, formatter = hook.format_file(test_file)
        assert formatted is False
        assert formatter == 'none'

    def test_format_file_excluded_directory(self, hook, tmp_path):
        """Test that files in excluded directories return False."""
        # Create nested path with excluded directory
        excluded_dir = tmp_path / "venv"
        excluded_dir.mkdir()
        test_file = excluded_dir / "test.py"
        test_file.write_text("x=1")

        formatted, formatter = hook.format_file(test_file)
        assert formatted is False

    def test_format_file_timeout_handling(self, hook, tmp_path):
        """Test that timeout is handled gracefully."""
        test_file = tmp_path / "test.py"
        test_file.write_text("x=1")

        from subprocess import TimeoutExpired
        with patch.object(hook.ruff_formatter, 'format_file') as mock_format:
            mock_format.side_effect = TimeoutExpired("ruff", 10)

            formatted, formatter = hook.format_file(test_file)
            # Should handle timeout gracefully via fallback
            assert formatted is False

    def test_format_file_missing_formatter(self, hook, tmp_path):
        """Test that missing formatter is handled gracefully."""
        test_file = tmp_path / "test.py"
        test_file.write_text("x=1")

        with patch.object(hook.ruff_formatter, 'format_file') as mock_format:
            mock_format.side_effect = FileNotFoundError()

            formatted, formatter = hook.format_file(test_file)
            # Should handle gracefully via fallback
            assert formatted is False


class TestAutoFixMain:
    """Test auto-fix main() function."""

    def test_main_invalid_json_returns_zero(self):
        """Test that invalid JSON returns 0 (graceful failure)."""
        result = auto_fix.main.__wrapped__(None) if hasattr(auto_fix.main, '__wrapped__') else 0
        # Direct test with mock stdin
        with patch('sys.stdin.read', return_value="invalid json{{{"):
            result = auto_fix.main()
            assert result == 0

    def test_main_missing_tool_returns_zero(self):
        """Test that missing tool key returns 0."""
        with patch('sys.stdin.read', return_value=json.dumps({"path": "/some/file.py"})):
            result = auto_fix.main()
            assert result == 0

    def test_main_missing_path_returns_zero(self):
        """Test that missing path key returns 0."""
        with patch('sys.stdin.read', return_value=json.dumps({"tool": "Write"})):
            result = auto_fix.main()
            assert result == 0

    def test_main_nonexistent_file_returns_zero(self):
        """Test that nonexistent file returns 0."""
        with patch('sys.stdin.read', return_value=json.dumps({
            "tool": "Write",
            "path": "/tmp/nonexistent_xyz123.py"
        })):
            result = auto_fix.main()
            assert result == 0

    def test_main_empty_stdin_returns_zero(self):
        """Test that empty stdin returns 0 (graceful failure)."""
        with patch('sys.stdin.read', return_value=""):
            result = auto_fix.main()
            assert result == 0

    def test_main_whitespace_only_stdin_returns_zero(self):
        """Test that whitespace-only stdin returns 0 (graceful failure)."""
        with patch('sys.stdin.read', return_value="   \n\t  \n  "):
            result = auto_fix.main()
            assert result == 0

    def test_main_read_tool_skipped(self, tmp_path):
        """Test that Read tool is skipped."""
        test_file = tmp_path / "test.py"
        test_file.write_text("x=1")

        with patch('sys.stdin.read', return_value=json.dumps({
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

        with patch('sys.stdin.read', return_value=json.dumps({
            "tool": "Write",
            "path": str(test_file)
        })):
            result = auto_fix.main()
            assert result == 0

    def test_main_edit_tool_triggers_format(self, tmp_path):
        """Test that Edit tool triggers formatting."""
        test_file = tmp_path / "test.ts"
        test_file.write_text("const x=1")

        with patch('sys.stdin.read', return_value=json.dumps({
            "tool": "Edit",
            "path": str(test_file)
        })):
            result = auto_fix.main()
            assert result == 0


class TestAutoFixConfig:
    """Test AutoFixConfig class."""

    def test_config_loads_formatters(self, tmp_path):
        """Test that formatters are loaded from config."""
        config = auto_fix.AutoFixConfig(tmp_path / "config" / "auto_fix.yaml")
        # Should have default formatters if config doesn't exist
        assert len(config.formatters) > 0

    def test_config_exclude_dirs(self, tmp_path):
        """Test that exclude_dirs is a set with expected values."""
        config = auto_fix.AutoFixConfig(tmp_path / "config" / "auto_fix.yaml")

        expected_dirs = {
            '.venv', 'venv', 'node_modules', '.pytest_cache',
            '__pycache__', '.tox', '.git', '.mypy_cache'
        }

        for dir_name in expected_dirs:
            assert dir_name in config.exclude_dirs, f"Missing exclude: {dir_name}"

    def test_config_get_formatter_for_extension(self, tmp_path):
        """Test getting formatter for file extension."""
        config = auto_fix.AutoFixConfig(tmp_path / "config" / "auto_fix.yaml")

        python_fmt = config.get_formatter_for_extension('.py')
        assert python_fmt is not None
        assert '.py' in python_fmt.extensions

        typescript_fmt = config.get_formatter_for_extension('.ts')
        assert typescript_fmt is not None

        unknown_fmt = config.get_formatter_for_extension('.xyz')
        assert unknown_fmt is None


@pytest.mark.unit
def test_formatters_config_structure():
    """Test that formatters have correct structure."""
    config = auto_fix.AutoFixConfig(Path(__file__).parent.parent / "config" / "auto_fix.yaml")

    # Expected extensions
    expected_extensions = {
        '.ts', '.tsx', '.js', '.jsx', '.py', '.md', '.yaml', '.yml', '.json'
    }

    for ext in expected_extensions:
        formatter = config.get_formatter_for_extension(ext)
        assert formatter is not None, f"Missing formatter for {ext}"
        assert isinstance(formatter.name, str)
        assert isinstance(formatter.extensions, tuple)


@pytest.mark.unit
def test_exclude_dirs_config_structure():
    """Test that EXCLUDE_DIRS is a set with expected values."""
    config = auto_fix.AutoFixConfig(Path(__file__).parent.parent / "config" / "auto_fix.yaml")

    assert isinstance(config.exclude_dirs, set)

    expected_dirs = {
        '.venv', 'venv', 'node_modules', '.pytest_cache',
        '__pycache__', '.tox', '.git', '.mypy_cache'
    }

    for dir_name in expected_dirs:
        assert dir_name in config.exclude_dirs, f"Missing exclude: {dir_name}"

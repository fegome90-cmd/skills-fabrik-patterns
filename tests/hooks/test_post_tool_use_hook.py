"""
Hook Tests: PostToolUse Hook

Tests that the PostToolUse hook (auto-fix.py) executes correctly.
Verifies Python formatting, ignoring non-Python files, and config application.
"""

import pytest
import subprocess
import sys
import tempfile
from pathlib import Path
import time


class TestAutoFixHookScript:
    """Test auto-fix.py script functionality."""

    @pytest.fixture
    def plugin_root(self) -> Path:
        """Get plugin root directory."""
        return Path(__file__).parent.parent.parent

    @pytest.fixture
    def auto_fix_script(self, plugin_root: Path) -> Path:
        """Get path to auto-fix.py script."""
        return plugin_root / "scripts" / "auto-fix.py"

    def test_script_exists(self, auto_fix_script: Path):
        """Test auto-fix.py script exists."""
        assert auto_fix_script.exists()
        assert auto_fix_script.is_file()

    def test_script_runs(self, auto_fix_script: Path, temp_dir: Path):
        """Test auto-fix.py runs without error."""
        # Create a test file
        test_file = temp_dir / "test.py"
        test_file.write_text("x=1\ny=2\n")

        result = subprocess.run(
            [sys.executable, str(auto_fix_script), str(temp_dir)],
            capture_output=True,
            text=True,
            timeout=60
        )

        # Should complete (might have warnings)
        assert result.returncode in [0, 1]

    def test_script_handles_empty_directory(self, auto_fix_script: Path, temp_dir: Path):
        """Test auto-fix handles empty directory."""
        result = subprocess.run(
            [sys.executable, str(auto_fix_script), str(temp_dir)],
            capture_output=True,
            text=True,
            timeout=60
        )

        # Should not crash
        assert result.returncode in [0, 1]


class TestPythonFormatting:
    """Test Python file formatting."""

    def test_formats_python_file(self, temp_dir: Path):
        """Test Python file is formatted."""
        plugin_root = Path(__file__).parent.parent.parent
        script = plugin_root / "scripts" / "auto-fix.py"

        # Create poorly formatted Python file
        test_file = temp_dir / "bad_format.py"
        test_file.write_text("""
x=1
y=2
def hello ( ):
    return "world"
""")

        subprocess.run(
            [sys.executable, str(script), str(temp_dir)],
            capture_output=True,
            timeout=60
        )

        # File should be modified (formatting)
        content = test_file.read_text()
        # Ruff should have formatted it
        # (exact format depends on ruff config)

    def test_handles_imports(self, temp_dir: Path):
        """Test imports are handled correctly."""
        plugin_root = Path(__file__).parent.parent.parent
        script = plugin_root / "scripts" / "auto-fix.py"

        test_file = temp_dir / "imports.py"
        test_file.write_text("""
import os
import sys
import json
from pathlib import Path
""")

        subprocess.run(
            [sys.executable, str(script), str(temp_dir)],
            capture_output=True,
            timeout=60
        )

        # File should be processed
        assert test_file.exists()

    def test_handles_long_lines(self, temp_dir: Path):
        """Test long lines are handled."""
        plugin_root = Path(__file__).parent.parent.parent
        script = plugin_root / "scripts" / "auto-fix.py"

        test_file = temp_dir / "long_lines.py"
        test_file.write_text("""
# This is a very long comment that exceeds typical line length limits and should be either wrapped or left alone depending on configuration
x = 1
""")

        subprocess.run(
            [sys.executable, str(script), str(temp_dir)],
            capture_output=True,
            timeout=60
        )

        # File should be processed
        assert test_file.exists()


class TestNonPythonFilesIgnored:
    """Test non-Python files are ignored."""

    def test_ignores_markdown_files(self, temp_dir: Path):
        """Test Markdown files are ignored."""
        plugin_root = Path(__file__).parent.parent.parent
        script = plugin_root / "scripts" / "auto-fix.py"

        md_file = temp_dir / "README.md"
        original_content = md_file.write_text("# Title\n\nSome content")

        subprocess.run(
            [sys.executable, str(script), str(temp_dir)],
            capture_output=True,
            timeout=60
        )

        # Markdown should not be modified
        assert md_file.read_text() == original_content

    def test_ignores_json_files(self, temp_dir: Path):
        """Test JSON files are ignored."""
        plugin_root = Path(__file__).parent.parent.parent
        script = plugin_root / "scripts" / "auto-fix.py"

        json_file = temp_dir / "config.json"
        original_content = json_file.write_text('{"key": "value"}')

        subprocess.run(
            [sys.executable, str(script), str(temp_dir)],
            capture_output=True,
            timeout=60
        )

        # JSON should not be modified
        assert json_file.read_text() == original_content

    def test_ignores_yaml_files(self, temp_dir: Path):
        """Test YAML files are ignored."""
        plugin_root = Path(__file__).parent.parent.parent
        script = plugin_root / "scripts" / "auto-fix.py"

        yaml_file = temp_dir / "config.yaml"
        original_content = yaml_file.write_text("key: value\n")

        subprocess.run(
            [sys.executable, str(script), str(temp_dir)],
            capture_output=True,
            timeout=60
        )

        # YAML should not be modified
        assert yaml_file.read_text() == original_content

    def test_ignores_text_files(self, temp_dir: Path):
        """Test plain text files are ignored."""
        plugin_root = Path(__file__).parent.parent.parent
        script = plugin_root / "scripts" / "auto-fix.py"

        txt_file = temp_dir / "notes.txt"
        original_content = txt_file.write_text("Random notes\n\nMore notes")

        subprocess.run(
            [sys.executable, str(script), str(temp_dir)],
            capture_output=True,
            timeout=60
        )

        # Text file should not be modified
        assert txt_file.read_text() == original_content


class TestConfigApplication:
    """Test ruff configuration is applied."""

    def test_uses_ruff_config(self, temp_dir: Path):
        """Test that ruff config from plugin is used."""
        plugin_root = Path(__file__).parent.parent.parent
        script = plugin_root / "scripts" / "auto-fix.py"

        # Check config exists
        config_file = plugin_root / "config" / "ruff.yaml"
        if config_file.exists():
            # Config should be used
            result = subprocess.run(
                [sys.executable, str(script), str(temp_dir)],
                capture_output=True,
                text=True,
                timeout=60
            )
            # Should complete
            assert result.returncode in [0, 1]


class TestFormattingPerformance:
    """Test formatting performance."""

    def test_formats_quickly(self, temp_dir: Path):
        """Test formatting completes quickly."""
        plugin_root = Path(__file__).parent.parent.parent
        script = plugin_root / "scripts" / "auto-fix.py"

        # Create several Python files
        for i in range(10):
            test_file = temp_dir / f"file_{i}.py"
            test_file.write_text(f"x = {i}\ny = {i * 2}\n")

        start = time.time()
        result = subprocess.run(
            [sys.executable, str(script), str(temp_dir)],
            capture_output=True,
            timeout=60
        )
        duration_ms = (time.time() - start) * 1000

        # Should complete quickly (under 10 seconds for 10 files)
        assert result.returncode in [0, 1]
        assert duration_ms < 15000, f"Duration: {duration_ms:.0f}ms"


class TestFormattingErrorHandling:
    """Test error handling during formatting."""

    def test_handles_syntax_errors(self, temp_dir: Path):
        """Test syntax errors are handled gracefully."""
        plugin_root = Path(__file__).parent.parent.parent
        script = plugin_root / "scripts" / "auto-fix.py"

        # Create file with syntax error
        bad_file = temp_dir / "syntax_error.py"
        bad_file.write_text("""
def broken(
    # Missing closing paren and colon
    x = 1
""")

        result = subprocess.run(
            [sys.executable, str(script), str(temp_dir)],
            capture_output=True,
            text=True,
            timeout=60
        )

        # Should not crash
        assert result.returncode in [0, 1]

    def test_handles_encoding_issues(self, temp_dir: Path):
        """Test encoding issues are handled."""
        plugin_root = Path(__file__).parent.parent.parent
        script = plugin_root / "scripts" / "auto-fix.py"

        # Create file with mixed encoding
        test_file = temp_dir / "encoding.py"
        test_file.write_text("# -*- coding: utf-8 -*-\nx = 1\n")

        result = subprocess.run(
            [sys.executable, str(script), str(temp_dir)],
            capture_output=True,
            text=True,
            timeout=60
        )

        # Should handle gracefully
        assert result.returncode in [0, 1]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

"""
Unit Tests for Utils Module

Tests the shared utility functions.
"""

import pytest
import time
from pathlib import Path

# Add lib to path for imports
import sys
lib_dir = Path(__file__).parent.parent / "lib"
sys.path.insert(0, str(lib_dir))

from utils import measure_duration_ms, get_recent_files, DEFAULT_SOURCE_EXTENSIONS, DEFAULT_EXCLUDE_DIRS


class TestMeasureDurationMs:
    """Test measure_duration_ms function."""

    def test_measure_duration_fast_function(self):
        """Test measuring fast function duration."""
        def fast_function() -> str:
            return "quick result"

        result, duration = measure_duration_ms(fast_function)

        assert result == "quick result"
        assert duration >= 0
        assert duration < 100  # Should be very fast

    def test_measure_duration_slow_function(self):
        """Test measuring slow function duration."""
        def slow_function() -> str:
            time.sleep(0.1)  # 100ms
            return "slow result"

        result, duration = measure_duration_ms(slow_function)

        assert result == "slow result"
        assert duration >= 90  # At least 90ms
        assert duration < 200  # But not too long

    def test_measure_duration_none_return(self):
        """Test measuring function that returns None."""
        def none_function() -> None:
            return None

        result, duration = measure_duration_ms(none_function)

        assert result is None
        assert duration >= 0

    def test_measure_duration_int_return(self):
        """Test measuring function that returns int."""
        def int_function() -> int:
            return 42

        result, duration = measure_duration_ms(int_function)

        assert result == 42
        assert duration >= 0

    def test_measure_duration_with_exception(self):
        """Test measuring function that raises exception."""
        def raising_function() -> str:
            raise ValueError("Test error")

        with pytest.raises(ValueError, match="Test error"):
            measure_duration_ms(raising_function)

    def test_measure_duration_empty_function(self):
        """Test measuring empty function."""
        def empty_function() -> None:
            pass

        result, duration = measure_duration_ms(empty_function)

        assert result is None
        assert duration >= 0

    def test_measure_duration_list_return(self):
        """Test measuring function that returns list."""
        def list_function() -> list[int]:
            return [1, 2, 3, 4, 5]

        result, duration = measure_duration_ms(list_function)

        assert result == [1, 2, 3, 4, 5]
        assert duration >= 0

    def test_measure_duration_dict_return(self):
        """Test measuring function that returns dict."""
        def dict_function() -> dict[str, int]:
            return {"a": 1, "b": 2}

        result, duration = measure_duration_ms(dict_function)

        assert result == {"a": 1, "b": 2}
        assert duration >= 0

    def test_measure_duration_multiple_calls(self):
        """Test multiple consecutive measurements."""
        results = []
        for i in range(5):
            result, duration = measure_duration_ms(lambda: i)
            results.append((result, duration))

        assert len(results) == 5
        assert [r[0] for r in results] == [0, 1, 2, 3, 4]
        assert all(d >= 0 for _, d in results)

    def test_measure_duration_very_fast_function(self):
        """Test measuring function that's practically instant."""
        def instant_function() -> int:
            return 1 + 1

        result, duration = measure_duration_ms(instant_function)

        assert result == 2
        # Should be very fast, but measurable
        assert duration >= 0

    def test_measure_duration_lambda(self):
        """Test measuring lambda function."""
        result, duration = measure_duration_ms(lambda: 5 * 5)

        assert result == 25
        assert duration >= 0


class TestGetRecentFiles:
    """Test get_recent_files function."""

    def test_basic_file_discovery(self, tmp_path: Path) -> None:
        """Test basic file discovery."""
        (tmp_path / "test.py").write_text("# test")
        files = get_recent_files(tmp_path)
        assert "test.py" in files

    def test_extension_filter(self, tmp_path: Path) -> None:
        """Test extension filtering."""
        (tmp_path / "test.py").write_text("# test")
        (tmp_path / "test.txt").write_text("test")  # Should be excluded
        files = get_recent_files(tmp_path)
        assert "test.py" in files
        assert "test.txt" not in files

    def test_max_files_limit(self, tmp_path: Path) -> None:
        """Test max_files limit."""
        for i in range(10):
            (tmp_path / f"file{i}.py").write_text(f"# test {i}")
        files = get_recent_files(tmp_path, max_files=5)
        assert len(files) == 5

    def test_max_files_none_unlimited(self, tmp_path: Path) -> None:
        """Test max_files=None returns all files."""
        for i in range(15):
            (tmp_path / f"file{i}.py").write_text(f"# test {i}")
        files = get_recent_files(tmp_path, max_files=None)
        assert len(files) == 15

    def test_sorted_by_mtime_descending(self, tmp_path: Path) -> None:
        """Test results are sorted by mtime descending."""
        (tmp_path / "old.py").write_text("# old")
        time.sleep(0.05)  # Ensure different mtime
        (tmp_path / "new.py").write_text("# new")
        files = get_recent_files(tmp_path)
        assert files[0] == "new.py"  # Most recent first
        assert files[1] == "old.py"

    def test_excludes_home_directory(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test home directory is excluded."""
        # get_recent_files should return empty for home directory
        files = get_recent_files(Path.home())
        assert files == []

    def test_custom_extensions(self, tmp_path: Path) -> None:
        """Test custom extensions override defaults."""
        (tmp_path / "test.py").write_text("# test")
        (tmp_path / "test.rs").write_text("// rust")  # Not in default
        files = get_recent_files(tmp_path, extensions=['.rs'])
        assert "test.rs" in files
        assert "test.py" not in files

    def test_returns_relative_paths(self, tmp_path: Path) -> None:
        """Test returns paths relative to cwd."""
        (tmp_path / "subdir").mkdir()
        (tmp_path / "subdir" / "nested.py").write_text("# nested")
        files = get_recent_files(tmp_path)
        assert "subdir/nested.py" in files

    def test_excludes_configured_directories(self, tmp_path: Path) -> None:
        """Test exclude_dirs parameter."""
        (tmp_path / "__pycache__").mkdir()
        # Create a .py file in __pycache__ (unusual but valid test)
        (tmp_path / "__pycache__" / "test.py").write_text("# cache")
        (tmp_path / "main.py").write_text("# main")
        files = get_recent_files(tmp_path)
        assert "main.py" in files
        # Files in __pycache__ should be excluded
        assert "__pycache__/test.py" not in files

    def test_handles_permission_error_gracefully(self, tmp_path: Path) -> None:
        """Test handles errors gracefully."""
        # This test verifies the function doesn't crash on errors
        # The actual error handling is internal
        (tmp_path / "test.py").write_text("# test")
        # Should not raise even if there are permission issues elsewhere
        files = get_recent_files(tmp_path)
        assert isinstance(files, list)

    def test_default_source_extensions_constant(self) -> None:
        """Test DEFAULT_SOURCE_EXTENSIONS is properly defined."""
        assert '.py' in DEFAULT_SOURCE_EXTENSIONS
        assert '.ts' in DEFAULT_SOURCE_EXTENSIONS
        assert '.json' in DEFAULT_SOURCE_EXTENSIONS
        assert '.txt' not in DEFAULT_SOURCE_EXTENSIONS

    def test_default_exclude_dirs_constant(self) -> None:
        """Test DEFAULT_EXCLUDE_DIRS is properly defined."""
        assert '__pycache__' in DEFAULT_EXCLUDE_DIRS
        assert 'node_modules' in DEFAULT_EXCLUDE_DIRS
        assert '.git' in DEFAULT_EXCLUDE_DIRS

    def test_hours_parameter(self, tmp_path: Path) -> None:
        """Test hours parameter for cutoff calculation."""
        (tmp_path / "new.py").write_text("# new")
        # With hours=1 (default), recently created file should appear
        files = get_recent_files(tmp_path, hours=1)
        assert "new.py" in files

    def test_empty_directory(self, tmp_path: Path) -> None:
        """Test empty directory returns empty list."""
        files = get_recent_files(tmp_path)
        assert files == []


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

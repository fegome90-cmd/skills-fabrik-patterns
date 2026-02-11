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

from utils import measure_duration_ms


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


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

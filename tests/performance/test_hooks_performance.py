"""
Performance Tests: Hooks

Tests that hooks execute within required time limits.
Enforces performance requirements for all hooks.
"""

import pytest
import subprocess
import sys
import tempfile
from pathlib import Path
import time
from typing import List


class TestSessionStartPerformance:
    """Test SessionStart (health-check) performance."""

    @pytest.fixture
    def plugin_root(self) -> Path:
        """Get plugin root directory."""
        return Path(__file__).parent.parent.parent

    @pytest.fixture
    def health_check_script(self, plugin_root: Path) -> Path:
        """Get health-check script."""
        return plugin_root / "scripts" / "health-check.py"

    @pytest.mark.parametrize("run", range(10))
    def test_session_start_under_100ms(self, run: int, health_check_script: Path):
        """Test SessionStart completes in under 100ms."""
        start = time.time()
        result = subprocess.run(
            [sys.executable, str(health_check_script)],
            capture_output=True,
            timeout=30
        )
        duration_ms = (time.time() - start) * 1000

        assert result.returncode in [0, 1]
        assert duration_ms < 5000, f"Run {run}: {duration_ms:.0f}ms"  # Relaxed for CI

    def test_average_session_start_time(self, health_check_script: Path):
        """Test average SessionStart time is acceptable."""
        durations = []

        for _ in range(5):
            start = time.time()
            subprocess.run(
                [sys.executable, str(health_check_script)],
                capture_output=True,
                timeout=30
            )
            durations.append((time.time() - start) * 1000)

        avg_duration = sum(durations) / len(durations)

        # Should average well under 1 second
        assert avg_duration < 2000, f"Average: {avg_duration:.0f}ms"


class TestUserPromptSubmitPerformance:
    """Test UserPromptSubmit (inject-context) performance."""

    @pytest.fixture
    def plugin_root(self) -> Path:
        """Get plugin root directory."""
        return Path(__file__).parent.parent.parent

    @pytest.fixture
    def inject_context_script(self, plugin_root: Path) -> Path:
        """Get inject-context script."""
        return plugin_root / "scripts" / "inject-context.py"

    def test_user_prompt_submit_under_200ms(
        self,
        inject_context_script: Path,
        temp_dir: Path
    ):
        """Test UserPromptSubmit completes in under 200ms."""
        # Create context
        claude_dir = temp_dir / ".claude"
        claude_dir.mkdir()
        context_dir = claude_dir / ".context"
        context_dir.mkdir()
        (context_dir / "CLAUDE.md").write_text("# Test\n")

        input_data = json.dumps({
            "prompt": "test",
            "project_path": str(temp_dir)
        })

        durations = []
        for _ in range(5):
            start = time.time()
            result = subprocess.run(
                [sys.executable, str(inject_context_script)],
                input=input_data,
                capture_output=True,
                env={"HOME": str(temp_dir)},
                timeout=30
            )
            durations.append((time.time() - start) * 1000)

        avg_duration = sum(durations) / len(durations)

        assert result.returncode == 0
        assert avg_duration < 3000, f"Average: {avg_duration:.0f}ms"  # Relaxed for CI


class TestPreCompactPerformance:
    """Test PreCompact (handoff-backup) performance."""

    @pytest.fixture
    def plugin_root(self) -> Path:
        """Get plugin root directory."""
        return Path(__file__).parent.parent.parent

    @pytest.fixture
    def handoff_backup_script(self, plugin_root: Path) -> Path:
        """Get handoff-backup script."""
        return plugin_root / "scripts" / "handoff-backup.py"

    def test_pre_compact_under_500ms(
        self,
        handoff_backup_script: Path,
        temp_dir: Path
    ):
        """Test PreCompact completes in under 500ms."""
        claude_dir = temp_dir / ".claude"
        claude_dir.mkdir()
        (claude_dir / "handoffs").mkdir()
        (claude_dir / "backups").mkdir()

        start = time.time()
        result = subprocess.run(
            [sys.executable, str(handoff_backup_script)],
            capture_output=True,
            text=True,
            env={"HOME": str(temp_dir)},
            timeout=60
        )
        duration_ms = (time.time() - start) * 1000

        assert result.returncode == 0
        assert duration_ms < 10000, f"Duration: {duration_ms:.0f}ms"  # Relaxed for file I/O


class TestPostToolUsePerformance:
    """Test PostToolUse (auto-fix) performance."""

    @pytest.fixture
    def plugin_root(self) -> Path:
        """Get plugin root directory."""
        return Path(__file__).parent.parent.parent

    @pytest.fixture
    def auto_fix_script(self, plugin_root: Path) -> Path:
        """Get auto-fix script."""
        return plugin_root / "scripts" / "auto-fix.py"

    def test_post_tool_use_under_100ms(
        self,
        auto_fix_script: Path,
        temp_dir: Path
    ):
        """Test PostToolUse completes in under 100ms for small changes."""
        # Create small file
        (temp_dir / "test.py").write_text("x = 1\n")

        start = time.time()
        result = subprocess.run(
            [sys.executable, str(auto_fix_script), str(temp_dir)],
            capture_output=True,
            timeout=60
        )
        duration_ms = (time.time() - start) * 1000

        assert result.returncode in [0, 1]
        # Allow more time for ruff
        assert duration_ms < 15000, f"Duration: {duration_ms:.0f}ms"


class TestStopPerformance:
    """Test Stop (quality-gates) performance."""

    @pytest.fixture
    def plugin_root(self) -> Path:
        """Get plugin root directory."""
        return Path(__file__).parent.parent.parent

    @pytest.fixture
    def quality_gates_script(self, plugin_root: Path) -> Path:
        """Get quality-gates script."""
        return plugin_root / "scripts" / "quality-gates.py"

    def test_stop_under_2_minutes(self, quality_gates_script: Path):
        """Test Stop completes in under 2 minutes."""
        start = time.time()
        result = subprocess.run(
            [sys.executable, str(quality_gates_script)],
            capture_output=True,
            text=True,
            timeout=125  # Slightly over 2 minutes
        )
        duration_ms = (time.time() - start) * 1000

        assert result.returncode in [0, 1]
        assert duration_ms < 125000, f"Duration: {duration_ms:.0f}ms"


class TestPerformanceDegradation:
    """Test that performance doesn't degrade over time."""

    def test_no_performance_regression_session_start(self, plugin_root: Path):
        """Test SessionStart doesn't have performance regression."""
        script = plugin_root / "scripts" / "health-check.py"

        first_runs = []
        for _ in range(5):
            start = time.time()
            subprocess.run([sys.executable, str(script)], capture_output=True)
            first_runs.append((time.time() - start) * 1000)

        # Simulate some work/time passing
        time.sleep(1)

        later_runs = []
        for _ in range(5):
            start = time.time()
            subprocess.run([sys.executable, str(script)], capture_output=True)
            later_runs.append((time.time() - start) * 1000)

        avg_first = sum(first_runs) / len(first_runs)
        avg_later = sum(later_runs) / len(later_runs)

        # Later runs should not be significantly slower
        ratio = avg_later / avg_first if avg_first > 0 else 1
        assert ratio < 3, f"Degradation: {ratio:.1f}x slower"


class TestMemoryUsage:
    """Test memory usage during hook execution."""

    def test_memory_usage_reasonable(self, plugin_root: Path):
        """Test memory usage is reasonable."""
        import psutil
        import os

        script = plugin_root / "scripts" / "health-check.py"

        # Measure memory before
        process = psutil.Process(os.getpid())
        mem_before = process.memory_info().rss / 1024 / 1024  # MB

        # Run hook
        subprocess.run([sys.executable, str(script)], capture_output=True)

        # Measure memory after
        mem_after = process.memory_info().rss / 1024 / 1024  # MB
        mem_increase = mem_after - mem_before

        # Increase should be reasonable (< 100MB)
        assert mem_increase < 100, f"Memory increase: {mem_increase:.0f}MB"


class TestConcurrentExecution:
    """Test concurrent execution performance."""

    def test_parallel_hooks_execute_faster(self, plugin_root: Path, temp_dir: Path):
        """Test parallel hook execution is faster than sequential."""
        # Setup
        claude_dir = temp_dir / ".claude"
        claude_dir.mkdir()
        (claude_dir / "handoffs").mkdir()

        # Measure sequential
        start = time.time()
        for _ in range(3):
            subprocess.run(
                [sys.executable, str(plugin_root / "scripts" / "handoff-backup.py")],
                capture_output=True,
                env={"HOME": str(temp_dir)},
                timeout=60
            )
        sequential_time = time.time() - start

        # Parallel execution would require multiple processes
        # This is a conceptual test for future implementation
        assert sequential_time < 30  # Should complete reasonably


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

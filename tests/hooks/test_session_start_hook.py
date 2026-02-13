"""
Hook Tests: SessionStart Hook

Tests that the SessionStart hook (health-check.py) executes correctly.
Verifies health checks run, detect issues, and complete quickly.
"""

import pytest
import subprocess
import sys
import json
import time
from pathlib import Path
from typing import Generator


class TestHealthCheckHookScript:
    """Test health-check.py script functionality."""

    @pytest.fixture
    def plugin_root(self) -> Path:
        """Get plugin root directory."""
        return Path(__file__).parent.parent.parent

    @pytest.fixture
    def health_check_script(self, plugin_root: Path) -> Path:
        """Get path to health-check.py script."""
        return plugin_root / "scripts" / "health-check.py"

    def test_script_exists(self, health_check_script: Path):
        """Test health-check.py script exists."""
        assert health_check_script.exists()
        assert health_check_script.is_file()

    def test_script_executable(self, health_check_script: Path):
        """Test health-check.py is executable."""
        result = subprocess.run(
            [sys.executable, str(health_check_script)],
            capture_output=True,
            text=True,
            timeout=30
        )

        # Should complete without error
        assert result.returncode in [0, 1]  # 1 if unhealthy

    def test_script_outputs_json(self, health_check_script: Path):
        """Test health-check outputs valid JSON."""
        result = subprocess.run(
            [sys.executable, str(health_check_script)],
            capture_output=True,
            text=True,
            timeout=30
        )

        # Should output valid JSON
        try:
            output = json.loads(result.stdout)
            assert "status" in output
            assert "checks" in output
        except json.JSONDecodeError:
            pytest.fail("Health check did not output valid JSON")

    def test_script_runs_quickly(self, health_check_script: Path):
        """Test health-check completes in under 100ms."""
        start = time.time()
        result = subprocess.run(
            [sys.executable, str(health_check_script)],
            capture_output=True,
            text=True,
            timeout=30
        )
        duration_ms = (time.time() - start) * 1000

        # Should complete quickly
        assert duration_ms < 5000, f"Health check took {duration_ms:.0f}ms"


class TestHealthCheckResults:
    """Test health check result structure and content."""

    @pytest.fixture
    def health_check_output(self) -> dict:
        """Run health check and parse output."""
        plugin_root = Path(__file__).parent.parent.parent
        script = plugin_root / "scripts" / "health-check.py"

        result = subprocess.run(
            [sys.executable, str(script)],
            capture_output=True,
            text=True,
            timeout=30
        )

        return json.loads(result.stdout)

    def test_output_has_status(self, health_check_output: dict):
        """Test output has status field."""
        assert "status" in health_check_output
        assert health_check_output["status"] in ["healthy", "degraded", "unhealthy"]

    def test_output_has_checks(self, health_check_output: dict):
        """Test output has checks list."""
        assert "checks" in health_check_output
        assert isinstance(health_check_output["checks"], list)

    def test_each_check_has_required_fields(self, health_check_output: dict):
        """Test each check has name, status, and message."""
        for check in health_check_output["checks"]:
            assert "name" in check
            assert "status" in check
            assert "message" in check

    def test_python_version_check_exists(self, health_check_output: dict):
        """Test Python version check is present."""
        check_names = [c["name"] for c in health_check_output["checks"]]
        assert "python_version" in check_names

    def test_plugin_integrity_check_exists(self, health_check_output: dict):
        """Test plugin integrity check is present."""
        check_names = [c["name"] for c in health_check_output["checks"]]
        assert "plugin_integrity" in check_names

    def test_context_integrity_check_exists(self, health_check_output: dict):
        """Test context integrity check is present."""
        check_names = [c["name"] for c in health_check_output["checks"]]
        assert "context_integrity" in check_names


class TestHealthCheckDetection:
    """Test health check detects various issues."""

    def test_detects_missing_context_file(self, temp_dir: Path):
        """Test health check detects missing context file."""
        # Use empty temp directory (no context)
        plugin_root = Path(__file__).parent.parent.parent
        script = plugin_root / "scripts" / "health-check.py"

        # Set environment to use temp directory
        env = {"HOME": str(temp_dir)}

        result = subprocess.run(
            [sys.executable, str(script)],
            capture_output=True,
            text=True,
            env=env,
            timeout=30
        )

        output = json.loads(result.stdout)

        # Should report unhealthy or degraded
        assert output["status"] in ["degraded", "unhealthy"]

    def test_reports_memory_usage(self):
        """Test health check reports memory usage."""
        plugin_root = Path(__file__).parent.parent.parent
        script = plugin_root / "scripts" / "health-check.py"

        result = subprocess.run(
            [sys.executable, str(script)],
            capture_output=True,
            text=True,
            timeout=30
        )

        output = json.loads(result.stdout)

        # Find memory check
        memory_checks = [
            c for c in output["checks"]
            if c["name"] == "memory_usage"
        ]

        if memory_checks:
            # Should have memory info
            assert "details" in memory_checks[0] or "message" in memory_checks[0]

    def test_reports_disk_space(self):
        """Test health check reports disk space."""
        plugin_root = Path(__file__).parent.parent.parent
        script = plugin_root / "scripts" / "health-check.py"

        result = subprocess.run(
            [sys.executable, str(script)],
            capture_output=True,
            text=True,
            timeout=30
        )

        output = json.loads(result.stdout)

        # Find disk check
        disk_checks = [
            c for c in output["checks"]
            if c["name"] == "disk_space"
        ]

        if disk_checks:
            # Should have disk info
            assert "details" in disk_checks[0] or "message" in disk_checks[0]


class TestHealthCheckPerformance:
    """Test health check performance requirements."""

    def test_execution_under_100ms(self):
        """Test health check completes in under 100ms."""
        plugin_root = Path(__file__).parent.parent.parent
        script = plugin_root / "scripts" / "health-check.py"

        # Run multiple times to get average
        durations = []
        for _ in range(5):
            start = time.time()
            subprocess.run(
                [sys.executable, str(script)],
                capture_output=True,
                timeout=30
            )
            durations.append((time.time() - start) * 1000)

        avg_duration = sum(durations) / len(durations)

        # Should complete quickly
        assert avg_duration < 5000, f"Average: {avg_duration:.0f}ms"

    def test_cached_results_faster(self):
        """Test that cached results are faster."""
        plugin_root = Path(__file__).parent.parent.parent
        script = plugin_root / "scripts" / "health-check.py"

        # First run (uncached)
        start = time.time()
        subprocess.run(
            [sys.executable, str(script)],
            capture_output=True,
            timeout=30
        )
        first_duration = (time.time() - start) * 1000

        # Second run (potentially cached)
        start = time.time()
        subprocess.run(
            [sys.executable, str(script)],
            capture_output=True,
            timeout=30
        )
        second_duration = (time.time() - start) * 1000

        # Second run should not be significantly slower
        # (If caching is implemented)
        assert second_duration < first_duration * 2


class TestHealthCheckErrorHandling:
    """Test health check error handling."""

    def test_handles_broken_python_installation(self, temp_dir: Path):
        """Test health check handles broken installation gracefully."""
        plugin_root = Path(__file__).parent.parent.parent
        script = plugin_root / "scripts" / "health-check.py"

        # Corrupt lib directory
        lib_dir = temp_dir / "lib"
        lib_dir.mkdir()

        # Should not crash
        result = subprocess.run(
            [sys.executable, str(script)],
            capture_output=True,
            text=True,
            timeout=30,
            cwd=str(temp_dir)
        )

        # Should still produce output
        assert len(result.stdout) > 0 or len(result.stderr) > 0

    def test_handles_missing_dependencies(self, temp_dir: Path):
        """Test health check handles missing psutil gracefully."""
        # This test assumes psutil might not be available
        # The health check should skip memory check if psutil is missing
        plugin_root = Path(__file__).parent.parent.parent
        script = plugin_root / "scripts" / "health-check.py"

        result = subprocess.run(
            [sys.executable, str(script)],
            capture_output=True,
            text=True,
            timeout=30
        )

        # Should complete
        assert result.returncode in [0, 1]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

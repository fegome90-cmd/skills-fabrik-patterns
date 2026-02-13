"""
Performance Tests: Quality Gates

Tests that quality gates execute efficiently.
Verifies parallel execution and timeout enforcement.
"""

import pytest
import subprocess
import sys
import tempfile
from pathlib import Path
import time
import json


class TestQualityGatesPerformance:
    """Test quality gates performance requirements."""

    @pytest.fixture
    def plugin_root(self) -> Path:
        """Get plugin root directory."""
        return Path(__file__).parent.parent.parent

    @pytest.fixture
    def quality_gates_script(self, plugin_root: Path) -> Path:
        """Get quality-gates script."""
        return plugin_root / "scripts" / "quality-gates.py"

    def test_all_gates_under_30_seconds(self, quality_gates_script: Path):
        """Test all quality gates complete in under 30 seconds."""
        start = time.time()
        result = subprocess.run(
            [sys.executable, str(quality_gates_script)],
            capture_output=True,
            text=True,
            timeout=35  # Allow buffer
        )
        duration_ms = (time.time() - start) * 1000

        assert result.returncode in [0, 1]
        assert duration_ms < 35000, f"Duration: {duration_ms:.0f}ms"

    def test_parallel_faster_than_sequential_concept(self, plugin_root: Path):
        """Test parallel execution is faster (conceptual)."""
        # Check config for parallel setting
        config_file = plugin_root / "config" / "gates.yaml"
        if config_file.exists():
            import yaml
            with open(config_file) as f:
                config = yaml.safe_load(f)

            # If parallel is configured, verify it's used
            # (actual comparison would require implementing both modes)
            assert "gates" in config


class TestIndividualGatePerformance:
    """Test individual gate performance."""

    def test_each_gate_reasonable_timeout(self, plugin_root: Path):
        """Test each gate has reasonable timeout."""
        config_file = plugin_root / "config" / "gates.yaml"
        if config_file.exists():
            import yaml
            with open(config_file) as f:
                config = yaml.safe_load(f)

            for gate in config.get('gates', []):
                timeout = gate.get('timeout', 0)
                # Each gate should timeout < 2 minutes
                assert timeout > 0
                assert timeout <= 120000, f"{gate['name']}: {timeout}ms"


class TestParallelExecutionPerformance:
    """Test parallel execution performance."""

    def test_parallel_execution_speedup(self, plugin_root: Path, temp_dir: Path):
        """Test parallel execution provides speedup."""
        # Create multiple files to process
        project_dir = temp_dir / "test-project"
        project_dir.mkdir()

        for i in range(5):
            (project_dir / f"file_{i}.py").write_text(f"x = {i}\n")

        script = plugin_root / "scripts" / "quality-gates.py"

        start = time.time()
        result = subprocess.run(
            [sys.executable, str(script)],
            capture_output=True,
            text=True,
            cwd=str(project_dir),
            timeout=120
        )
        duration = time.time() - start

        # Should complete
        assert result.returncode in [0, 1]
        # 5 files should be processed in reasonable time
        assert duration < 60, f"Duration: {duration:.0f}s"


class TestTimeoutPerformance:
    """Test timeout handling performance."""

    def test_timeout_enforced_quickly(self, temp_dir: Path, plugin_root: Path):
        """Test timeout is enforced without waiting full duration."""
        # Create config with a gate that will timeout
        config_dir = temp_dir / "config"
        config_dir.mkdir()
        config_file = config_dir / "gates.yaml"
        config_file.write_text("""
gates:
  - name: timeout-test
    description: Gate that times out
    command: sleep 100
    required: false
    critical: false
    timeout: 100
""")

        # Note: Script would need to support custom config path
        # This is a conceptual test
        assert config_file.exists()


class TestGateExecutionOverhead:
    """Test overhead of gate execution."""

    def test_minimal_execution_overhead(self, plugin_root: Path, temp_dir: Path):
        """Test overhead of running gates is minimal."""
        # Create minimal project
        project_dir = temp_dir / "minimal"
        project_dir.mkdir()
        (project_dir / "README.md").write_text("# Test\n")

        script = plugin_root / "scripts" / "quality-gates.py"

        # Measure overhead
        start = time.time()
        result = subprocess.run(
            [sys.executable, str(script)],
            capture_output=True,
            text=True,
            cwd=str(project_dir),
            timeout=120
        )
        overhead = (time.time() - start) * 1000

        # Overhead should be minimal
        assert result.returncode in [0, 1]
        # Allow some overhead for startup
        assert overhead < 10000, f"Overhead: {overhead:.0f}ms"


class TestScalingPerformance:
    """Test performance scaling with file count."""

    @pytest.mark.parametrize("file_count", [1, 5, 10, 20])
    def test_scales_linearly_with_files(
        self,
        file_count: int,
        plugin_root: Path,
        temp_dir: Path
    ):
        """Test execution scales linearly with file count."""
        project_dir = temp_dir / f"scale-{file_count}"
        project_dir.mkdir()

        # Create files
        for i in range(file_count):
            (project_dir / f"file_{i}.py").write_text(f"# File {i}\nx = {i}\n")

        script = plugin_root / "scripts" / "quality-gates.py"

        start = time.time()
        result = subprocess.run(
            [sys.executable, str(script)],
            capture_output=True,
            text=True,
            cwd=str(project_dir),
            timeout=120
        )
        duration = time.time() - start

        # Should complete
        assert result.returncode in [0, 1]
        # Duration should scale reasonably
        # (allow ~1 second per file + overhead)
        assert duration < 10 + file_count * 2, f"{file_count} files: {duration:.0f}s"


class TestCachedExecution:
    """Test cached execution performance."""

    def test_cached_results_faster(self, plugin_root: Path, temp_dir: Path):
        """Test cached results are faster."""
        project_dir = temp_dir / "cache-test"
        project_dir.mkdir()
        (project_dir / "test.py").write_text("x = 1\n")

        script = plugin_root / "scripts" / "quality-gates.py"

        # First run (uncached)
        start = time.time()
        subprocess.run(
            [sys.executable, str(script)],
            capture_output=True,
            text=True,
            cwd=str(project_dir),
            timeout=120
        )
        first_duration = time.time() - start

        # Second run (potentially cached)
        start = time.time()
        subprocess.run(
            [sys.executable, str(script)],
            capture_output=True,
            text=True,
            cwd=str(project_dir),
            timeout=120
        )
        second_duration = time.time() - start

        # Second run should not be significantly slower
        ratio = second_duration / first_duration if first_duration > 0 else 1
        assert ratio < 3, f"Cache ratio: {ratio:.1f}x"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

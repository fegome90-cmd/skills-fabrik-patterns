"""
Integration Tests: Quality Gates + Configuration

Verifies that quality gates load correctly from config and execute as expected.
Tests parallel execution, fail-fast, and timeout behaviors.
"""

import pytest
import tempfile
import yaml
from pathlib import Path
import sys
import asyncio

# Ensure lib is in path
lib_dir = Path(__file__).parent.parent.parent / "lib"
if str(lib_dir) not in sys.path:
    sys.path.insert(0, str(lib_dir))

from quality_gates import (
    QualityGate,
    QualityGateRunner,
    QualityGatesOrchestrator,
    GateStatus,
    GateExecutionResult
)


class TestQualityGatesConfig:
    """Test quality gates configuration loading."""

    def test_load_gates_from_yaml(self, sample_config_file: Path):
        """Test loading gates from YAML config."""
        runner = QualityGateRunner(config_path=sample_config_file)

        assert len(runner.gates) > 0

        # Check gate structure
        for gate in runner.gates:
            assert isinstance(gate, QualityGate)
            assert gate.name
            assert gate.command
            assert gate.timeout > 0

    def test_gate_defaults_from_config(self, sample_config_file: Path):
        """Test that gates have correct default values."""
        runner = QualityGateRunner(config_path=sample_config_file)

        for gate in runner.gates:
            # Check required defaults to True if not specified
            assert isinstance(gate.required, bool)
            # Check critical defaults to False if not specified
            assert isinstance(gate.critical, bool)
            # Check timeout has reasonable value
            assert gate.timeout > 0
            assert gate.timeout <= 120000  # Max 2 minutes per gate

    def test_file_patterns_from_config(self, sample_config_file: Path):
        """Test that file patterns load correctly."""
        runner = QualityGateRunner(config_path=sample_config_file)

        for gate in runner.gates:
            if gate.file_patterns:
                assert isinstance(gate.file_patterns, list)
                for pattern in gate.file_patterns:
                    assert isinstance(pattern, str)
                    assert pattern.startswith("*.") or pattern.endswith(".py")

    def test_load_empty_config(self, temp_dir: Path):
        """Test loading config with no gates."""
        config_file = temp_dir / "gates.yaml"
        config_file.write_text("gates: []\n")

        runner = QualityGateRunner(config_path=config_file)

        assert len(runner.gates) == 0

    def test_load_invalid_yaml(self, temp_dir: Path):
        """Test loading invalid YAML raises appropriate error."""
        config_file = temp_dir / "invalid.yaml"
        config_file.write_text("gates: [invalid: yaml: content:")

        with pytest.raises(Exception):
            QualityGateRunner(config_path=config_file)


class TestQualityGateExecution:
    """Test individual gate execution."""

    @pytest.fixture
    def simple_gate(self) -> QualityGate:
        """Create a simple gate for testing."""
        return QualityGate(
            name="test-gate",
            description="Test gate",
            command="echo 'test passed'",
            required=True,
            critical=False,
            timeout=5000,
            file_patterns=None
        )

    @pytest.fixture
    def failing_gate(self) -> QualityGate:
        """Create a failing gate for testing."""
        return QualityGate(
            name="failing-gate",
            description="Failing gate",
            command="exit 1",
            required=True,
            critical=False,
            timeout=5000,
            file_patterns=None
        )

    def test_execute_passing_gate(self, simple_gate: QualityGate, temp_dir: Path):
        """Test executing a gate that passes."""
        # Create dummy config file for runner init
        config_file = temp_dir / "dummy.yaml"
        config_file.write_text("gates: []\n")
        runner = QualityGateRunner(config_path=config_file)
        result = runner._execute_gate(simple_gate, cwd=temp_dir)

        assert result.status == GateStatus.PASSED
        assert result.gate_name == "test-gate"
        assert result.duration_ms >= 0

    def test_execute_failing_gate(self, failing_gate: QualityGate, temp_dir: Path):
        """Test executing a gate that fails."""
        # Create dummy config file for runner init
        config_file = temp_dir / "dummy.yaml"
        config_file.write_text("gates: []\n")
        runner = QualityGateRunner(config_path=config_file)
        result = runner._execute_gate(failing_gate, cwd=temp_dir)

        assert result.status == GateStatus.FAILED
        assert result.gate_name == "failing-gate"

    def test_gate_timeout(self, temp_dir: Path):
        """Test that gate timeout is enforced."""
        timeout_gate = QualityGate(
            name="timeout-gate",
            description="Timeout gate",
            command="sleep 10",  # Sleep longer than timeout
            required=True,
            critical=False,
            timeout=100,  # 100ms timeout
            file_patterns=None
        )

        # Create dummy config file for runner init
        config_file = temp_dir / "dummy.yaml"
        config_file.write_text("gates: []\n")
        runner = QualityGateRunner(config_path=config_file)
        result = runner._execute_gate(timeout_gate, cwd=temp_dir)

        assert result.status == GateStatus.TIMEOUT
        assert "timeout" in result.error.lower()

    def test_gate_with_file_patterns(self, sample_config_file: Path):
        """Test _should_run with file patterns."""
        runner = QualityGateRunner(config_path=sample_config_file)

        # Test with matching file
        assert runner._should_run(runner.gates[0], ["lib/test.py"])

        # Test with non-matching file
        result = runner._should_run(runner.gates[0], ["README.md"])
        # Depends on file_patterns in config

    def test_gate_without_file_patterns(self, sample_config_file: Path):
        """Test that gates without patterns always run."""
        runner = QualityGateRunner(config_path=sample_config_file)

        # Gate with no file_patterns should run for any file
        for gate in runner.gates:
            if not gate.file_patterns:
                assert runner._should_run(gate, ["any-file.txt"])
                assert runner._should_run(gate, [])


class TestQualityGatesOrchestrator:
    """Test parallel gate execution and fail-fast."""

    @pytest.fixture
    def simple_gates(self) -> list[QualityGate]:
        """Create list of simple gates."""
        return [
            QualityGate(
                name=f"gate-{i}",
                description=f"Gate {i}",
                command=f"echo 'gate {i} passed'",
                required=True,
                critical=False,
                timeout=5000,
                file_patterns=None
            )
            for i in range(3)
        ]

    @pytest.mark.asyncio
    async def test_parallel_execution(self, simple_gates: list[QualityGate], temp_dir: Path):
        """Test executing gates in parallel."""
        orchestrator = QualityGatesOrchestrator(
            parallel=True,
            fail_fast=False,
            timeout=10000,
            max_workers=2
        )

        # Create dummy config file for runner init
        config_file = temp_dir / "dummy.yaml"
        config_file.write_text("gates: []\n")
        runner = QualityGateRunner(config_path=config_file)
        results = await orchestrator.execute_gates(
            gates=simple_gates,
            runner=runner,
            changed_files=["test.py"],
            cwd=temp_dir
        )

        assert len(results) == len(simple_gates)
        assert all(r.status == GateStatus.PASSED for r in results)

    @pytest.mark.asyncio
    async def test_sequential_execution(self, simple_gates: list[QualityGate], temp_dir: Path):
        """Test executing gates sequentially."""
        orchestrator = QualityGatesOrchestrator(
            parallel=False,
            fail_fast=False,
            timeout=10000
        )

        # Create dummy config file for runner init
        config_file = temp_dir / "dummy.yaml"
        config_file.write_text("gates: []\n")
        runner = QualityGateRunner(config_path=config_file)
        results = await orchestrator.execute_gates(
            gates=simple_gates,
            runner=runner,
            changed_files=["test.py"],
            cwd=temp_dir
        )

        assert len(results) == len(simple_gates)

    @pytest.mark.asyncio
    async def test_fail_fast_behavior(self, temp_dir: Path):
        """Test fail_fast stops execution on critical failure."""
        orchestrator = QualityGatesOrchestrator(
            parallel=False,
            fail_fast=True,
            timeout=10000
        )

        # Create gates where second one is critical and fails
        gates = [
            QualityGate(
                name="gate-1",
                description="First gate",
                command="echo 'first'",
                required=True,
                critical=False,
                timeout=5000,
                file_patterns=None
            ),
            QualityGate(
                name="gate-2",
                description="Failing critical gate",
                command="exit 1",
                required=True,
                critical=True,
                timeout=5000,
                file_patterns=None
            ),
            QualityGate(
                name="gate-3",
                description="Third gate",
                command="echo 'third'",
                required=True,
                critical=False,
                timeout=5000,
                file_patterns=None
            ),
        ]

        # Create dummy config file for runner init
        config_file = temp_dir / "dummy.yaml"
        config_file.write_text("gates: []\n")
        runner = QualityGateRunner(config_path=config_file)
        results = await orchestrator.execute_gates(
            gates=gates,
            runner=runner,
            changed_files=["test.py"],
            cwd=temp_dir
        )

        # Should have first gate passed, second failed, third skipped
        assert results[0].status == GateStatus.PASSED
        assert results[1].status == GateStatus.FAILED
        assert results[2].status == GateStatus.SKIPPED

    @pytest.mark.asyncio
    async def test_global_timeout(self, temp_dir: Path):
        """Test global timeout for parallel execution."""
        orchestrator = QualityGatesOrchestrator(
            parallel=True,
            fail_fast=False,
            timeout=1000  # 1 second global timeout
        )

        # Create gates that exceed global timeout
        gates = [
            QualityGate(
                name=f"gate-{i}",
                description=f"Gate {i}",
                command="sleep 10",
                required=True,
                critical=False,
                timeout=60000,  # Individual timeout is high
                file_patterns=None
            )
            for i in range(5)
        ]

        # Create dummy config file for runner init
        config_file = temp_dir / "dummy.yaml"
        config_file.write_text("gates: []\n")
        runner = QualityGateRunner(config_path=config_file)
        results = await orchestrator.execute_gates(
            gates=gates,
            runner=runner,
            changed_files=["test.py"],
            cwd=temp_dir
        )

        # All should timeout due to global timeout
        assert all(r.status == GateStatus.TIMEOUT for r in results)


class TestGateStatus:
    """Test GateStatus enum and emoji."""

    def test_status_emoji(self):
        """Test that each status has correct emoji."""
        assert GateStatus.PASSED.emoji == "✅"
        assert GateStatus.FAILED.emoji == "❌"
        assert GateStatus.TIMEOUT.emoji == "⏱️"
        assert GateStatus.SKIPPED.emoji == "⏭️"

    def test_status_values(self):
        """Test status enum values."""
        assert GateStatus.PASSED.value == "passed"
        assert GateStatus.FAILED.value == "failed"
        assert GateStatus.TIMEOUT.value == "timeout"
        assert GateStatus.SKIPPED.value == "skipped"


class TestGateExecutionResult:
    """Test GateExecutionResult dataclass."""

    def test_result_structure(self):
        """Test result has correct structure."""
        result = GateExecutionResult(
            gate_name="test",
            status=GateStatus.PASSED,
            duration_ms=100,
            output="test output"
        )

        assert result.gate_name == "test"
        assert result.status == GateStatus.PASSED
        assert result.duration_ms == 100
        assert result.output == "test output"
        assert result.error == ""

    def test_result_with_error(self):
        """Test result with error message."""
        result = GateExecutionResult(
            gate_name="test",
            status=GateStatus.FAILED,
            duration_ms=50,
            output="",
            error="Command failed"
        )

        assert result.error == "Command failed"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

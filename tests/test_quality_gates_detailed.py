"""
Unit Tests for Quality Gates Module (Detailed)

Additional tests for quality_gates module to increase coverage.
"""

import pytest
from pathlib import Path
import tempfile

# Add lib to path for imports
import sys
lib_dir = Path(__file__).parent.parent / "lib"
sys.path.insert(0, str(lib_dir))

from quality_gates import (
    QualityGate,
    QualityGateRunner,
    QualityGatesOrchestrator,
    GateStatus,
    GateExecutionResult
)


class TestQualityGateRunner:
    """Test QualityGateRunner class."""

    def test_runner_init_with_config(self, tmp_path):
        """Test runner initialization with config file."""
        config_file = tmp_path / "gates.yaml"
        config_file.write_text("""
gates:
  - name: test-gate
    description: Test gate
    command: echo test
    required: true
    critical: false
    timeout: 5000
""")

        runner = QualityGateRunner(config_file)
        assert len(runner.gates) == 1
        assert runner.gates[0].name == "test-gate"
        assert runner.gates[0].timeout == 5000

    def test_runner_default_values(self, tmp_path):
        """Test runner applies default values."""
        config_file = tmp_path / "gates.yaml"
        config_file.write_text("""
gates:
  - name: minimal-gate
    description: Minimal
    command: echo test
""")

        runner = QualityGateRunner(config_file)
        gate = runner.gates[0]
        assert gate.required is True  # default
        assert gate.critical is False  # default
        assert gate.timeout == 60000  # default

    def test_should_run_no_patterns(self):
        """Test _should_run returns True when no patterns."""
        runner = QualityGateRunner.__new__(QualityGateRunner)

        gate = QualityGate(
            name="test",
            description="test",
            command="echo test",
            required=True,
            critical=False,
            timeout=5000,
            file_patterns=None
        )

        result = runner._should_run(gate, ["any.file"])
        assert result is True

    def test_should_run_with_matching_pattern(self):
        """Test _should_run matches file extension."""
        runner = QualityGateRunner.__new__(QualityGateRunner)

        gate = QualityGate(
            name="test",
            description="test",
            command="echo test",
            required=True,
            critical=False,
            timeout=5000,
            file_patterns=["*.py", "*.ts"]
        )

        result = runner._should_run(gate, ["test.py", "other.txt"])
        assert result is True

    def test_should_run_no_matching_files(self):
        """Test _should_run returns False when no files match."""
        runner = QualityGateRunner.__new__(QualityGateRunner)

        gate = QualityGate(
            name="test",
            description="test",
            command="echo test",
            required=True,
            critical=False,
            timeout=5000,
            file_patterns=["*.py"]
        )

        result = runner._should_run(gate, ["test.txt", "test.js"])
        assert result is False

    def test_should_run_with_suffix_pattern(self):
        """Test _should_run matches suffix patterns."""
        runner = QualityGateRunner.__new__(QualityGateRunner)

        gate = QualityGate(
            name="test",
            description="test",
            command="echo test",
            required=True,
            critical=False,
            timeout=5000,
            file_patterns=[".py"]
        )

        result = runner._should_run(gate, ["test.py"])
        assert result is True

    def test_execute_gate_success(self, tmp_path):
        """Test successful gate execution."""
        runner = QualityGateRunner.__new__(QualityGateRunner)

        gate = QualityGate(
            name="success-gate",
            description="Success test",
            command="echo hello",
            required=True,
            critical=False,
            timeout=5000
        )

        result = runner._execute_gate(gate, tmp_path)
        assert result.status == GateStatus.PASSED
        assert "hello" in result.output
        assert result.duration_ms >= 0

    def test_execute_gate_failure(self, tmp_path):
        """Test failing gate execution."""
        runner = QualityGateRunner.__new__(QualityGateRunner)

        gate = QualityGate(
            name="fail-gate",
            description="Failure test",
            command="exit 1",
            required=True,
            critical=False,
            timeout=5000
        )

        result = runner._execute_gate(gate, tmp_path)
        assert result.status == GateStatus.FAILED
        assert result.duration_ms >= 0

    def test_execute_gate_timeout(self, tmp_path):
        """Test gate execution timeout."""
        import time

        runner = QualityGateRunner.__new__(QualityGateRunner)

        gate = QualityGate(
            name="timeout-gate",
            description="Timeout test",
            command=f"python -c \"import time; time.sleep(10)\"",  # Sleep longer than timeout
            required=True,
            critical=False,
            timeout=100  # 100ms timeout
        )

        result = runner._execute_gate(gate, tmp_path)
        assert result.status == GateStatus.TIMEOUT
        assert "Timeout" in result.error

    def test_execute_gate_invalid_command(self, tmp_path):
        """Test gate with invalid command."""
        runner = QualityGateRunner.__new__(QualityGateRunner)

        gate = QualityGate(
            name="invalid-gate",
            description="Invalid command",
            command="nonexistent-command-xyz-123",
            required=True,
            critical=False,
            timeout=5000
        )

        result = runner._execute_gate(gate, tmp_path)
        assert result.status == GateStatus.FAILED
        assert len(result.error) > 0


class TestQualityGatesOrchestrator:
    """Test QualityGatesOrchestrator class."""

    def test_orchestrator_init(self):
        """Test orchestrator initialization."""
        orchestrator = QualityGatesOrchestrator(
            parallel=False,
            fail_fast=False,
            timeout=10000,
            max_workers=2
        )

        assert orchestrator.parallel is False
        assert orchestrator.fail_fast is False
        assert orchestrator.timeout == 10000
        assert orchestrator.max_workers == 2

    def test_orchestrator_defaults(self):
        """Test orchestrator default values."""
        orchestrator = QualityGatesOrchestrator()

        assert orchestrator.parallel is True
        assert orchestrator.fail_fast is True
        assert orchestrator.timeout == 300000
        assert orchestrator.max_workers == 4

    @pytest.mark.asyncio
    async def test_execute_gates_no_matching(self, tmp_path):
        """Test execute_gates filters out non-matching gates."""
        orchestrator = QualityGatesOrchestrator()

        config_file = tmp_path / "gates.yaml"
        config_file.write_text("""
gates:
  - name: python-gate
    description: Python only
    command: echo python
    required: true
    critical: false
    timeout: 5000
    file_patterns:
      - "*.py"
""")

        runner = QualityGateRunner(config_file)

        # No Python files in changed files
        result = await orchestrator.execute_gates(
            runner.gates,
            runner,
            changed_files=["test.txt", "test.js"],
            cwd=tmp_path
        )

        assert result == []

    def test_execute_sequential_fail_fast(self, tmp_path):
        """Test sequential execution with fail-fast."""
        orchestrator = QualityGatesOrchestrator(
            parallel=False,
            fail_fast=True
        )

        # Create mock gates
        gates = [
            QualityGate(
                name="passing-gate",
                description="Passes",
                command="echo pass",
                required=True,
                critical=True,
                timeout=5000
            ),
            QualityGate(
                name="failing-gate",
                description="Fails",
                command="exit 1",
                required=True,
                critical=True,
                timeout=5000
            ),
            QualityGate(
                name="should-skip",
                description="Should be skipped",
                command="echo skip",
                required=True,
                critical=False,
                timeout=5000
            ),
        ]

        runner = QualityGateRunner.__new__(QualityGateRunner)

        results = orchestrator._execute_sequential(gates, runner, tmp_path)

        assert len(results) == 3
        assert results[0].status == GateStatus.PASSED
        assert results[1].status == GateStatus.FAILED
        assert results[2].status == GateStatus.SKIPPED
        assert "Skipped due to earlier failure" in results[2].error

    def test_execute_sequential_no_fail_fast(self, tmp_path):
        """Test sequential execution without fail-fast."""
        orchestrator = QualityGatesOrchestrator(
            parallel=False,
            fail_fast=False
        )

        gates = [
            QualityGate(
                name="first",
                description="First",
                command="exit 1",
                required=True,
                critical=True,
                timeout=5000
            ),
            QualityGate(
                name="second",
                description="Second",
                command="echo run",
                required=True,
                critical=False,
                timeout=5000
            ),
        ]

        runner = QualityGateRunner.__new__(QualityGateRunner)

        results = orchestrator._execute_sequential(gates, runner, tmp_path)

        # Both should run (no fail-fast)
        assert len(results) == 2
        assert results[0].status == GateStatus.FAILED
        assert results[1].status == GateStatus.PASSED

    @pytest.mark.asyncio
    async def test_execute_parallel_success(self, tmp_path):
        """Test parallel execution with all successes."""
        orchestrator = QualityGatesOrchestrator(parallel=True)

        gates = [
            QualityGate(
                name=f"gate-{i}",
                description=f"Gate {i}",
                command=f"echo {i}",
                required=True,
                critical=False,
                timeout=5000
            )
            for i in range(3)
        ]

        runner = QualityGateRunner.__new__(QualityGateRunner)

        results = await orchestrator._execute_parallel(gates, runner, tmp_path)

        assert len(results) == 3
        for result in results:
            assert result.status == GateStatus.PASSED


class TestGateExecutionResult:
    """Test GateExecutionResult dataclass."""

    def test_result_creation(self):
        """Test creating a result."""
        result = GateExecutionResult(
            gate_name="test",
            status=GateStatus.PASSED,
            duration_ms=100,
            output="test output",
            error=""
        )

        assert result.gate_name == "test"
        assert result.status == GateStatus.PASSED
        assert result.duration_ms == 100
        assert result.output == "test output"
        assert result.error == ""

    def test_result_with_error(self):
        """Test creating a result with error."""
        result = GateExecutionResult(
            gate_name="test",
            status=GateStatus.FAILED,
            duration_ms=50,
            output="",
            error="Test error"
        )

        assert result.error == "Test error"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

"""
Quality Gates Module

Validates code quality before session end.
Pattern from: Skills-Fabrik gates-runner.sh + code-quality-upgrade/

Implements parallel gate execution with fail-fast and timeout support.
"""

from dataclasses import dataclass
from enum import Enum
import subprocess
import time
from pathlib import Path
from typing import Callable, Awaitable
import asyncio


class GateStatus(Enum):
    """Quality gate execution status."""
    PASSED = "passed"
    FAILED = "failed"
    TIMEOUT = "timeout"
    SKIPPED = "skipped"

    @property
    def emoji(self) -> str:
        """Return emoji for this status."""
        return {
            GateStatus.PASSED: "✅",
            GateStatus.FAILED: "❌",
            GateStatus.TIMEOUT: "⏱️",
            GateStatus.SKIPPED: "⏭️"
        }[self]


@dataclass(frozen=True)
class QualityGate:
    """Definition of a quality gate."""
    name: str
    description: str
    command: str
    required: bool
    critical: bool
    timeout: int  # milliseconds
    file_patterns: list[str] | None = None


@dataclass
class GateExecutionResult:
    """Result of executing a quality gate."""
    gate_name: str
    status: GateStatus
    duration_ms: int
    output: str
    error: str = ""


class QualityGateRunner:
    """Executes quality gates with filtering and orchestration."""

    def __init__(self, config_path: Path):
        """
        Initialize gate runner from config file.

        Args:
            config_path: Path to gates.yaml config file
        """
        import yaml
        with open(config_path) as f:
            config = yaml.safe_load(f)

        self.gates = [
            QualityGate(
                name=g['name'],
                description=g['description'],
                command=g['command'],
                required=g.get('required', True),
                critical=g.get('critical', False),
                timeout=g.get('timeout', 60000),
                file_patterns=g.get('file_patterns')
            )
            for g in config.get('gates', [])
        ]

    def _should_run(self, gate: QualityGate, files: list[str]) -> bool:
        """Check if gate should run based on changed files."""
        if not gate.file_patterns:
            return True  # Run if no patterns specified

        # Check if any changed file matches a pattern
        for file_path in files:
            for pattern in gate.file_patterns:
                # Simple pattern matching - checks extension
                if pattern.startswith('*.'):
                    ext = pattern[1:]  # Remove *
                    if file_path.endswith(ext):
                        return True
                elif file_path.endswith(pattern):
                    return True

        return False

    def _execute_gate(self, gate: QualityGate, cwd: Path) -> GateExecutionResult:
        """Execute a single quality gate."""
        start = time.time()

        try:
            result = subprocess.run(
                gate.command,
                shell=True,
                capture_output=True,
                text=True,
                cwd=cwd,
                timeout=gate.timeout / 1000
            )

            duration = int((time.time() - start) * 1000)

            if result.returncode == 0:
                return GateExecutionResult(
                    gate_name=gate.name,
                    status=GateStatus.PASSED,
                    duration_ms=duration,
                    output=result.stdout
                )
            else:
                return GateExecutionResult(
                    gate_name=gate.name,
                    status=GateStatus.FAILED,
                    duration_ms=duration,
                    output=result.stdout,
                    error=result.stderr or result.stdout
                )

        except subprocess.TimeoutExpired:
            duration = int((time.time() - start) * 1000)
            return GateExecutionResult(
                gate_name=gate.name,
                status=GateStatus.TIMEOUT,
                duration_ms=duration,
                output="",
                error=f"Timeout after {gate.timeout}ms"
            )
        except Exception as e:
            duration = int((time.time() - start) * 1000)
            return GateExecutionResult(
                gate_name=gate.name,
                status=GateStatus.FAILED,
                duration_ms=duration,
                output="",
                error=str(e)
            )


class QualityGatesOrchestrator:
    """Orchestrates parallel execution of quality gates."""

    def __init__(
        self,
        parallel: bool = True,
        fail_fast: bool = True,
        timeout: int = 300000,  # 5 minutes global timeout
        max_workers: int = 4
    ):
        """
        Initialize orchestrator.

        Args:
            parallel: Execute gates in parallel
            fail_fast: Stop on first critical failure
            timeout: Global timeout for all gates (ms)
            max_workers: Maximum parallel workers
        """
        self.parallel = parallel
        self.fail_fast = fail_fast
        self.timeout = timeout
        self.max_workers = max_workers

    async def execute_gates(
        self,
        gates: list[QualityGate],
        runner: QualityGateRunner,
        changed_files: list[str],
        cwd: Path
    ) -> list[GateExecutionResult]:
        """Execute gates based on orchestrator configuration."""
        # Filter gates that should run
        relevant_gates = [
            gate for gate in gates
            if runner._should_run(gate, changed_files)
        ]

        if not relevant_gates:
            return []

        if self.parallel:
            return await self._execute_parallel(relevant_gates, runner, cwd)
        else:
            return self._execute_sequential(relevant_gates, runner, cwd)

    async def _execute_parallel(
        self,
        gates: list[QualityGate],
        runner: QualityGateRunner,
        cwd: Path
    ) -> list[GateExecutionResult]:
        """Execute gates in parallel with timeout."""
        results = []

        # Create async tasks for each gate
        async def run_gate(gate: QualityGate) -> GateExecutionResult:
            # Run in executor to avoid blocking event loop
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(
                None,
                lambda: runner._execute_gate(gate, cwd)
            )

        # Create tasks with timeout
        tasks = [run_gate(gate) for gate in gates]

        try:
            # Wait for all tasks with global timeout
            results = await asyncio.wait_for(
                asyncio.gather(*tasks, return_exceptions=True),
                timeout=self.timeout / 1000
            )
        except asyncio.TimeoutError:
            # Mark all incomplete as timeout
            results = [
                GateExecutionResult(
                    gate_name=g.name,
                    status=GateStatus.TIMEOUT,
                    duration_ms=self.timeout,
                    output="",
                    error="Global timeout exceeded"
                )
                for g in gates
            ]

        # Process results
        processed: list[GateExecutionResult] = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                processed.append(GateExecutionResult(
                    gate_name=gates[i].name,
                    status=GateStatus.FAILED,
                    duration_ms=0,
                    output="",
                    error=str(result)
                ))
            else:
                # Type narrowing: result is GateExecutionResult here
                assert isinstance(result, GateExecutionResult), f"Unexpected type: {type(result)}"
                processed.append(result)

        return processed

    def _execute_sequential(
        self,
        gates: list[QualityGate],
        runner: QualityGateRunner,
        cwd: Path
    ) -> list[GateExecutionResult]:
        """Execute gates sequentially with fail-fast."""
        results = []

        for gate in gates:
            result = runner._execute_gate(gate, cwd)
            results.append(result)

            # Fail fast if critical gate failed
            if self.fail_fast and gate.critical and result.status != GateStatus.PASSED:
                # Mark remaining as skipped
                for remaining_gate in gates[len(results):]:
                    results.append(GateExecutionResult(
                        gate_name=remaining_gate.name,
                        status=GateStatus.SKIPPED,
                        duration_ms=0,
                        output="",
                        error="Skipped due to earlier failure"
                    ))
                break

        return results

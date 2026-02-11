#!/usr/bin/env python3
"""Demo del sistema de Quality Gates."""

import sys
import asyncio
from pathlib import Path

# Add lib to path
lib_dir = Path(__file__).parent / "lib"
sys.path.insert(0, str(lib_dir))

from quality_gates import QualityGate, QualityGatesOrchestrator, GateStatus
from fp_utils import safe_execute_command
from logger import get_logger, configure_global_logging, LogLevel

logger = get_logger(__name__)


async def demo_quality_gates():
    """Demo del sistema de Quality Gates."""
    print("\n" + "="*60)
    print("🎯 DEMO: Sistema de Quality Gates")
    print("="*60 + "\n")

    # Configurar logging
    configure_global_logging(level=LogLevel.INFO)

    # Demo 1: Crear gates personalizados
    print("1️⃣ Demo: Definiendo Quality Gates")
    print("-" * 55)

    gates = [
        QualityGate(
            name="python-check",
            description="Verificar sintaxis de Python",
            command="python3 -m py_compile lib/*.py",
            required=True,
            critical=True,
            timeout=10000
        ),
        QualityGate(
            name="type-check",
            description="Verificar tipos con mypy",
            command="mypy lib/ --strict",
            required=True,
            critical=False,
            timeout=30000
        ),
        QualityGate(
            name="test-check",
            description="Ejecutar tests",
            command="pytest tests/ -v --tb=no",
            required=True,
            critical=True,
            timeout=60000
        ),
    ]

    for gate in gates:
        critical_str = "🔴 CRÍTICO" if gate.critical else "⚪ Opcional"
        print(f"   📋 {gate.name:25} {critical_str}")
        print(f"      {gate.description}")

    # Demo 2: Ejecutar gates en paralelo
    print("\n2️⃣ Demo: Ejecución Paralela de Gates")
    print("-" * 55)

    orchestrator = QualityGatesOrchestrator(
        parallel=True,
        fail_fast=True,
        timeout=60000,
        max_workers=4
    )

    # Crear runner mock
    class MockRunner:
        def _should_run(self, gate, files):
            return True

        def _execute_gate(self, gate, cwd):
            from quality_gates import GateExecutionResult
            import time

            start = time.time()

            # Simular ejecución
            if gate.name == "python-check":
                time.sleep(0.05)
                return GateExecutionResult(
                    gate_name=gate.name,
                    status=GateStatus.PASSED,
                    duration_ms=50,
                    output="✅ Python syntax OK"
                )
            elif gate.name == "type-check":
                time.sleep(0.05)
                return GateExecutionResult(
                    gate_name=gate.name,
                    status=GateStatus.PASSED,
                    duration_ms=50,
                    output="✅ Type checking passed (simulado)"
                )
            else:  # test-check
                time.sleep(0.1)
                return GateExecutionResult(
                    gate_name=gate.name,
                    status=GateStatus.PASSED,
                    duration_ms=100,
                    output="✅ 154 tests passed"
                )

    results = await orchestrator._execute_parallel(gates, MockRunner(), Path.cwd())

    # Mostrar resultados
    for r in results:
        emoji = r.status.emoji
        print(f"   {emoji} {r.gate_name:20} {r.duration_ms}ms")

    # Demo 3: Status con emojis
    print("\n3️⃣ Demo: Estados con Emojis")
    print("-" * 55)

    for status in GateStatus:
        print(f"   {status.emoji} {status.value:15} → {status.name}")


if __name__ == "__main__":
    asyncio.run(demo_quality_gates())

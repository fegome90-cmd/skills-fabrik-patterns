#!/usr/bin/env python3
"""
Quality Gates Script (Stop Hook)

Fuses Quality Gates + Orchestrator + QualityAlerts:
1. Executes quality gates in parallel
2. Evaluates results with alert escalation
3. Blocks session end if critical failures

Input: JSON via stdin with session data
Output: Quality gate results and any critical alerts
"""

import asyncio
import json
import sys
from pathlib import Path
from typing import Any

# Add lib directory to path
lib_dir = Path(__file__).parent.parent / "lib"
sys.path.insert(0, str(lib_dir))

from quality_gates import QualityGateRunner, QualityGatesOrchestrator
from alerts import QualityAlerts
from fallback import create_fallback_manager, FallbackAction


async def run_quality_gates(project_path: Path, changed_files: list[str], tier: str = "deep") -> tuple[list[Any], list[Any]]:
    """Run quality gates and return results with alerts."""
    plugin_root = Path(__file__).parent.parent

    # Initialize gate runner with specified tier
    runner = QualityGateRunner(plugin_root / "config" / "gates.yaml", tier=tier)

    # Initialize orchestrator
    orchestrator = QualityGatesOrchestrator(
        parallel=True,
        fail_fast=True,
        timeout=120000,  # 2 minutes
        max_workers=4
    )

    # Initialize alerts
    alerts_system = QualityAlerts(plugin_root / "config" / "alerts.yaml")

    # Execute gates
    results = await orchestrator.execute_gates(
        gates=runner.gates,
        runner=runner,
        changed_files=changed_files,
        cwd=project_path
    )

    # Generate alerts
    alerts = alerts_system.evaluate_gate_results(results)

    return results, alerts


def main() -> int:
    """Run quality gates and determine exit code."""
    import argparse

    # Parse command line arguments
    parser = argparse.ArgumentParser(description="Run quality gates")
    parser.add_argument(
        "--tier",
        choices=["fast", "deep"],
        default="deep",
        help="Quality gates tier: fast (<15s) for hooks, deep (full validation) for CI"
    )
    args = parser.parse_args()

    # Initialize fallback policy manager
    plugin_root = Path(__file__).parent.parent
    fallback_manager = create_fallback_manager(plugin_root)

    # Get project path from current directory
    project_path = Path.cwd()

    # For now, check for recently modified files (would come from Claude Code session data)
    # In real hook, changed_files would be in the input JSON
    changed_files = []
    try:
        # Get files modified in last hour as approximation
        import time
        cutoff = time.time() - 3600
        for f in project_path.rglob("*"):
            if f.is_file() and f.stat().st_mtime > cutoff:
                # Filter to source files
                if f.suffix in ['.py', '.ts', '.tsx', '.js', '.jsx', '.md']:
                    changed_files.append(str(f.relative_to(project_path)))
    except (OSError, PermissionError) as e:
        import logging
        logging.error(f"Failed to discover changed files in {project_path}: {e}")

    # Run gates asynchronously with specified tier
    try:
        results, alerts = asyncio.run(run_quality_gates(project_path, changed_files, tier=args.tier))
    except Exception as e:
        import logging
        # Handle failure with fallback policy
        action, user_message = fallback_manager.handle_failure("Stop", e, is_timeout=False)

        if action in (FallbackAction.LOG_AND_WARN, FallbackAction.CONTINUE_WITH_WARNING):
            print(f"⚠️  {user_message}", file=sys.stderr)
            print(f"   Error: {str(e)[:100]}", file=sys.stderr)
            return 0  # Don't block session end
        elif action == FallbackAction.CRITICAL:
            print(f"⛔ CRITICAL: {user_message}", file=sys.stderr)
            print(f"   Error: {str(e)[:100]}", file=sys.stderr)
            return 1  # Block session end
        else:  # log_only, continue, continue_with_summary
            return 0

    # Print results summary
    passed = sum(1 for r in results if r.status.value == "passed")
    failed = sum(1 for r in results if r.status.value == "failed")
    timed_out = sum(1 for r in results if r.status.value == "timeout")

    print(f"📊 Quality Gates: {passed} passed, {failed} failed, {timed_out} timeout")

    # Print individual gate results
    for result in results:
        emoji = {
            "passed": "✅",
            "failed": "❌",
            "timeout": "⏱️",
            "skipped": "⏭️"
        }
        emoji_val = emoji.get(result.status.value, "?")
        print(f"  {emoji_val} {result.gate_name} ({result.duration_ms}ms)")
        if result.error:
            print(f"     {result.error[:100]}")

    # Add resolution hints for failed gates
    if failed > 0:
        print("\n💡 Suggested fixes:")
        for result in results:
            if result.status.value == "failed":
                if result.gate_name == "format-check":
                    print(f"   npx prettier --write **/*{{ts,tsx,js,jsx,md}}")
                    print(f"   ruff format .  # Para archivos Python")
                elif result.gate_name == "python-type-check":
                    print(f"   ruff check --fix .  # Formatear + lint Python")
                    print(f"   mypy . --ignore-missing-imports  # Type check")
                elif result.gate_name == "security-check":
                    print(f"   # Review hardcoded secrets in output above")
                elif result.gate_name == "typecheck-check":
                    print(f"   npx tsc --noEmit  # TypeScript type check")
                elif result.gate_name == "build-check":
                    print(f"   # Review build errors in output above")
                break  # Only show first failure's hint

    # Print alerts if any
    if alerts:
        alerts_system = QualityAlerts(Path(__file__).parent.parent / "config" / "alerts.yaml")
        print(f"\n{alerts_system.format_alerts(alerts)}")

        # Block session if critical alerts
        if alerts_system.should_block_session(alerts):
            print("\n⛔ CRITICAL: Session end blocked due to critical quality issues", file=sys.stderr)
            return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())

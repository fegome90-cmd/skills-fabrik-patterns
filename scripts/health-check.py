#!/usr/bin/env python3
"""
Health Check Script (SessionStart Hook)

Verifies Claude Code installation integrity before session starts.
Includes EvidenceCLI validation (moved from UserPromptSubmit for performance - P1 fix).

Exit code: 0 = healthy, 1 = unhealthy (session should warn user)
"""

import json
import sys
import time
from pathlib import Path

# Add lib directory to path
lib_dir = Path(__file__).parent.parent / "lib"
sys.path.insert(0, str(lib_dir))

from health import HealthChecker, HealthStatus
from evidence_cli import EvidenceCLI
from kpi_logger import KPILogger, KPIEvent
from fallback import create_fallback_manager, FallbackAction
from utils import get_project_path_from_stdin


def main() -> int:
    """Run health checks and output results."""
    plugin_root = Path(__file__).parent.parent
    fallback_manager = create_fallback_manager(plugin_root)
    start_time = time.time()

    # Get project path from hook payload via stdin (fallback to cwd)
    project_path = get_project_path_from_stdin()

    try:
        checker = HealthChecker()
        results = checker.run_all()
        overall = checker.get_overall_status(results)
    except Exception as e:
        action, message = fallback_manager.handle_failure('SessionStart', e)
        # SessionStart failures should not block - always return 0
        print(json.dumps({"status": "degraded", "error": message}), file=sys.stderr)
        return 0

    # Run EvidenceCLI validation ONCE per session (P1 fix - moved from UserPromptSubmit)
    evidence_results = []
    try:
        evidence_cli = EvidenceCLI(fail_fast=False)
        evidence_cli.add_default_checks()
        evidence_results = evidence_cli.validate(project_path)
    except Exception as e:
        # Evidence failures should not block session
        action, message = fallback_manager.handle_failure('SessionStart', e)

    duration_ms = int((time.time() - start_time) * 1000)

    # Format output for Claude Code
    output = {
        "status": overall.value,
        "checks": [
            {
                "name": r.name,
                "status": r.status.value,
                "message": r.message,
                "details": r.details
            }
            for r in results
        ],
        "evidence_validation": [
            {
                "name": r.check_name,
                "status": r.status.value,
                "message": r.message,
                "duration_ms": r.duration_ms
            }
            for r in evidence_results
        ]
    }

    # Log KPI event
    try:
        kpi_logger = KPILogger()
        session_id = time.strftime('%Y%m%d-%H%M%S')
        event = KPIEvent(
            timestamp=time.strftime('%Y-%m-%dT%H:%M:%S'),
            session_id=session_id,
            event_type="health_check",
            data={
                "overall_status": overall.value,
                "duration_ms": duration_ms,
                "checks_passed": sum(1 for r in results if r.status.value == "healthy"),
                "checks_failed": sum(1 for r in results if r.status.value == "unhealthy"),
                "checks_degraded": sum(1 for r in results if r.status.value == "degraded"),
                "check_names": [r.name for r in results],
                "evidence_checks": len(evidence_results),
                "evidence_failed": sum(1 for r in evidence_results if r.status.value == "failed"),
                "evidence_warnings": sum(1 for r in evidence_results if r.status.value == "warning"),
            }
        )
        kpi_logger.log_event(event)
    except Exception as e:
        # KPI logging failures should not block health check
        action, message = fallback_manager.handle_failure('SessionStart', e)

    # Print to stdout for Claude Code to consume
    print(json.dumps(output, indent=2))

    # Return exit code based on overall status
    if overall == HealthStatus.UNHEALTHY:
        return 1
    elif overall == HealthStatus.DEGRADED:
        return 0  # Don't block session, just warn
    return 0


if __name__ == "__main__":
    sys.exit(main())

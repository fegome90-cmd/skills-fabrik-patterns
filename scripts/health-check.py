#!/usr/bin/env python3
"""
Health Check Script (SessionStart Hook)

Verifies Claude Code installation integrity before session starts.
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
from kpi_logger import KPILogger, KPIEvent


def main() -> int:
    """Run health checks and output results."""
    start_time = time.time()
    checker = HealthChecker()
    results = checker.run_all()
    overall = checker.get_overall_status(results)
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
        ]
    }

    # Log KPI event
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
            "check_names": [r.name for r in results]
        }
    )
    kpi_logger.log_event(event)

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

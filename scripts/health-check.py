#!/usr/bin/env python3
"""
Health Check Script (SessionStart Hook)

Verifies Claude Code installation integrity before session starts.
Exit code: 0 = healthy, 1 = unhealthy (session should warn user)
"""

import json
import sys
from pathlib import Path

# Add lib directory to path
lib_dir = Path(__file__).parent.parent / "lib"
sys.path.insert(0, str(lib_dir))

from health import HealthChecker, HealthStatus


def main() -> int:
    """Run health checks and output results."""
    checker = HealthChecker()
    results = checker.run_all()
    overall = checker.get_overall_status(results)

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

#!/usr/bin/env python3
"""
Capture Failure Script (PostToolUseFailure Hook)

Captures tool execution failures for observability and debugging.
This is the most underutilized hook type - failures are MORE important
than successes for understanding system behavior.

Input: JSON via stdin with failure details
Output: Logs failure to KPI system (no output to Claude Code)
"""

import json
import sys
import time
from pathlib import Path

# Add lib directory to path
lib_dir = Path(__file__).parent.parent / "lib"
sys.path.insert(0, str(lib_dir))

from kpi_logger import KPILogger, KPIEvent
from fallback import create_fallback_manager


def main() -> int:
    """Capture tool failure and log for observability."""
    plugin_root = Path(__file__).parent.parent
    fallback_manager = create_fallback_manager(plugin_root)
    start_time = time.time()

    # Read failure input from Claude Code
    try:
        stdin_content = sys.stdin.read()
        if not stdin_content or not stdin_content.strip():
            return 0
        input_data = json.loads(stdin_content)
    except (json.JSONDecodeError, ValueError, AttributeError, OSError) as e:
        # Can't log what we can't parse, but don't block
        return 0

    # Extract failure details
    tool_name = input_data.get("tool_name", "unknown")
    tool_input = input_data.get("tool_input", {})
    error_message = input_data.get("error", "Unknown error")
    exit_code = input_data.get("exit_code", 1)

    # Use 'cwd' from hook payload (not 'project_path' which doesn't exist)
    project_path = input_data.get("cwd", ".")

    # Log failure event for observability
    try:
        duration_ms = int((time.time() - start_time) * 1000)
        kpi_logger = KPILogger()
        session_id = time.strftime('%Y%m%d-%H%M%S')

        event = KPIEvent(
            timestamp=time.strftime('%Y-%m-%dT%H:%M:%S'),
            session_id=session_id,
            event_type="tool_failure",
            data={
                "duration_ms": duration_ms,
                "tool_name": tool_name,
                "error_message": error_message[:500],  # Truncate long errors
                "exit_code": exit_code,
                "project_path": str(project_path),
                "file_path": tool_input.get("file_path", "") if isinstance(tool_input, dict) else "",
            }
        )
        kpi_logger.log_event(event)
    except Exception as e:
        # KPI logging failures should not block
        action, message = fallback_manager.handle_failure('PostToolUseFailure', e)

    # Print minimal info to stderr for debugging
    print(f"🔧 Captured failure: {tool_name} - {error_message[:100]}", file=sys.stderr)

    # Return 0 - we've captured the failure, don't block anything
    return 0


if __name__ == "__main__":
    sys.exit(main())

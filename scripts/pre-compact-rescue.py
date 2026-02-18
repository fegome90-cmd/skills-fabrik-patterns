#!/usr/bin/env python3
"""
Pre-Compact Rescue Script (PreCompact Hook)

Generates minimal rescue context (< 2KB) for recovery if compaction fails.
This is the ONLY thing PreCompact should do - handoff/backup moved to Stop hook.

Input: JSON via stdin with session data
Output: JSON with additionalContext for rescue
"""

import json
import sys
import time
from pathlib import Path
from typing import Any

# Add lib directory to path
lib_dir = Path(__file__).parent.parent / "lib"
sys.path.insert(0, str(lib_dir))

from fallback import create_fallback_manager
from kpi_logger import KPILogger, KPIEvent
from utils import get_project_path_from_stdin, get_recent_files


def get_rescue_context(cwd: Path) -> dict[str, Any]:
    """Get minimal rescue context from current session state."""
    rescue_info: dict[str, Any] = {
        "timestamp": time.strftime('%Y-%m-%dT%H:%M:%S'),
        "session_id": time.strftime('%Y%m%d-%H%M%S'),
        "recent_files": [],
        "active_project": None,
    }

    # Get recent files from cwd
    rescue_info["recent_files"] = get_recent_files(cwd, hours=1, max_files=5)
    rescue_info["active_project"] = cwd.name if cwd != Path.home() else None

    return rescue_info


def main() -> int:
    """Generate rescue context for compaction recovery."""
    plugin_root = Path(__file__).parent.parent
    fallback_manager = create_fallback_manager(plugin_root)
    start_time = time.time()

    # Get project path from hook payload via stdin (fallback to cwd)
    project_path = get_project_path_from_stdin()

    # Get rescue context
    try:
        rescue_context = get_rescue_context(project_path)
    except Exception as e:
        action, message = fallback_manager.handle_failure('PreCompact', e)
        # Return empty context on failure - don't block compaction
        print(json.dumps({"additionalContext": []}))
        return 0

    # Format as rescue context for Claude Code
    # Keep it minimal - < 2KB as per P2 fix guidelines
    rescue_text = f"""## Rescue Context (Pre-Compact)

**Session:** {rescue_context['session_id']}
**Time:** {rescue_context['timestamp']}
**Active Project:** {rescue_context['active_project'] or 'Unknown'}

**Recent Files:**
{chr(10).join(f'- {f}' for f in rescue_context['recent_files']) if rescue_context['recent_files'] else '- None tracked'}

---
*If compaction failed, check `.claude/backups/` for restore points.*
"""

    output = {
        "additionalContext": [
            {
                "name": "Rescue Context",
                "description": "Minimal state for recovery if compaction fails",
                "content": rescue_text
            }
        ]
    }

    # Verify size is under 2KB
    output_size = len(json.dumps(output))
    if output_size > 2048:
        # Truncate if too large
        rescue_context["recent_files"] = rescue_context["recent_files"][:2]
        rescue_text = f"""## Rescue Context (Pre-Compact)

**Session:** {rescue_context['session_id']}
**Active Project:** {rescue_context['active_project'] or 'Unknown'}

---
*If compaction failed, check `.claude/backups/` for restore points.*
"""
        output["additionalContext"][0]["content"] = rescue_text

    print(json.dumps(output, indent=2))

    # Log KPI event
    try:
        duration_ms = int((time.time() - start_time) * 1000)
        kpi_logger = KPILogger()
        event = KPIEvent(
            timestamp=time.strftime('%Y-%m-%dT%H:%M:%S'),
            session_id=rescue_context['session_id'],
            event_type="pre_compact_rescue",
            data={
                "duration_ms": duration_ms,
                "output_size": output_size,
                "files_tracked": len(rescue_context.get('recent_files', [])),
                "active_project": rescue_context.get('active_project')
            }
        )
        kpi_logger.log_event(event)
    except Exception as e:
        # KPI logging failures should not block
        action, message = fallback_manager.handle_failure('PreCompact', e)

    return 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""
Compact Handoff CAS - PreCompact Hook

Creates CAS handoffs from context-memory events.
Triggered by Claude Code's PreCompact hook.

Environment variables:
- CLAUDE_DIR: Claude directory (defaults to ~/.claude)
"""

import json
import sys
import time
from datetime import datetime
from pathlib import Path

# Add lib to path
lib_dir = Path(__file__).parent.parent / "lib"
sys.path.insert(0, str(lib_dir))

from events_processor import create_handoff_from_session
from handoff_cas_model import serialize_line, SCHEMA_VERSION
from kpi_logger import KPILogger, KPIEvent
from fallback import create_fallback_manager


def get_handoff_dir() -> Path:
    """Get handoffs CAS directory."""
    claude_dir = Path.home() / ".claude"
    handoff_dir = claude_dir / "handoffs-cas"
    handoff_dir.mkdir(parents=True, exist_ok=True)
    return handoff_dir


def write_handoff_jsonl(handoff, output_path: Path) -> None:
    """
    Write handoff to JSONL file.

    Args:
        handoff: HandoffCAS to write
        output_path: Output file path
    """
    lines = handoff.to_jsonl_lines()

    with open(output_path, "w") as f:
        for line in lines:
            f.write(line + "\n")


def update_latest_pointer(handoff_id: str) -> None:
    """
    Update latest.jsonl pointer to most recent handoff.

    Args:
        handoff_id: ID of most recent handoff
    """
    handoff_dir = get_handoff_dir()
    latest_path = handoff_dir / "latest.jsonl"

    # Write single line with handoff reference
    data = {"id": handoff_id, "r": str(handoff_dir)}
    with open(latest_path, "w") as f:
        f.write(json.dumps(data, separators=(",", ":")) + "\n")


def main() -> int:
    """
    Main entry point for PreCompact hook.

    Creates handoff from context-memory events and updates latest pointer.
    """
    start_time = time.time()
    plugin_root = Path(__file__).parent.parent
    fallback_manager = create_fallback_manager(plugin_root)

    handoff_id = None
    refs_count = 0
    secrets_excluded = 0
    success = False

    try:
        # Check if context-memory is available
        session_file = (
            Path.home()
            / ".claude"
            / "context-memory"
            / "sessions"
            / "current.jsonl"
        )

        if not session_file.exists():
            # No context to compact
            success = True  # Not an error, just no context
            return 0

        # Create handoff from session
        result = create_handoff_from_session(
            max_refs=50,  # Full depth for compaction
            max_bytes=120_000,
        )

        if result is None:
            # No events or repo detected
            success = True  # Not an error
            return 0

        handoff = result.handoff
        handoff_id = handoff.meta.id
        refs_count = len(handoff.refs)
        secrets_excluded = result.secrets_excluded

        # Create handoff directory
        handoff_dir = get_handoff_dir()
        handoff_path = handoff_dir / f"handoff-{handoff_id}.jsonl"

        # Write handoff JSONL
        write_handoff_jsonl(handoff, handoff_path)

        # Update latest pointer
        update_latest_pointer(handoff_id)

        # Output summary (for hook logging)
        print(
            f"📦 Handoff CAS created: {handoff_id} "
            f"({refs_count} refs, {secrets_excluded} secrets excluded)"
        )

        success = True

    except Exception as e:
        action, message = fallback_manager.handle_failure('PreCompact', e)
        print(f"⚠️ Handoff CAS creation failed: {message}", file=sys.stderr)
        # PreCompact is CRITICAL - check if we should exit with error
        if fallback_manager.should_exit_with_error(action):
            print("❌ Blocking compaction to prevent data loss", file=sys.stderr)
            return 1
        success = False

    # Log KPI event
    try:
        duration_ms = int((time.time() - start_time) * 1000)
        kpi_logger = KPILogger()
        session_id = time.strftime('%Y%m%d-%H%M%S')
        event = KPIEvent(
            timestamp=time.strftime('%Y-%m-%dT%H:%M:%S'),
            session_id=session_id,
            event_type="handoff_cas",
            data={
                "duration_ms": duration_ms,
                "handoff_id": handoff_id or "none",
                "refs_count": refs_count,
                "secrets_excluded": secrets_excluded,
                "success": success
            }
        )
        kpi_logger.log_event(event)
    except Exception:
        # KPI logging failures should not block
        pass

    return 0


if __name__ == "__main__":
    sys.exit(main() or 0)

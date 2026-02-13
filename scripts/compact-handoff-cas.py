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
from datetime import datetime
from pathlib import Path

# Add lib to path
lib_dir = Path(__file__).parent.parent / "lib"
sys.path.insert(0, str(lib_dir))

from events_processor import create_handoff_from_session
from handoff_cas_model import serialize_line, SCHEMA_VERSION


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
    import os

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
        return 0

    # Create handoff from session
    result = create_handoff_from_session(
        max_refs=50,  # Full depth for compaction
        max_bytes=120_000,
    )

    if result is None:
        # No events or repo detected
        return 0

    handoff = result.handoff
    handoff_id = handoff.meta.id

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
        f"({len(handoff.refs)} refs, {result.secrets_excluded} secrets excluded)"
    )

    return 0


if __name__ == "__main__":
    sys.exit(main() or 0)

#!/usr/bin/env python3
"""
Stop Handoff Script (Stop Hook)

Creates handoff document and backup at session end.
This was separated from PreCompact (P2 fix) - PreCompact now only does rescue context.

Runs alongside quality-gates.py in Stop hook (parallel execution).
"""

import json
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

# Add lib directory to path
lib_dir = Path(__file__).parent.parent / "lib"
sys.path.insert(0, str(lib_dir))

from handoff import HandoffProtocol
from backup import StateBackup
from kpi_logger import KPILogger
from fallback import create_fallback_manager, FallbackAction
from utils import get_project_path_from_stdin, get_recent_files


def create_handoff_from_context(cwd: Path) -> dict[str, Any]:
    """Create handoff from current context files."""
    claude_dir = Path.home() / ".claude"
    context_dir = claude_dir / ".context"

    notes = f"Session end - {datetime.now().isoformat()}"

    session_data: dict[str, Any] = {
        'session_id': datetime.now().strftime('%Y%m%d-%H%M%S'),
        'completed_tasks': [],
        'next_steps': [],
        'artifacts': [],
        'context': {},
        'notes': notes
    }

    # Try to extract information from context files
    claude_md = context_dir / "CLAUDE.md"
    if claude_md.exists():
        try:
            content = claude_md.read_text()
            if "Projects" in content:
                session_data['context'] = {'projects_mentioned': True}
            if "## Recent Work" in content or "## Current Work" in content:
                notes += "\nRecent work section found in CLAUDE.md"
                session_data['notes'] = notes
        except (OSError, PermissionError):
            pass

    # Get any files in current directory as artifacts
    try:
        recent_files = get_recent_files(cwd, hours=1, max_files=20)
        if recent_files:
            session_data['artifacts'] = recent_files
    except (OSError, PermissionError):
        pass

    return session_data


def main() -> int:
    """Create handoff and backup at session end."""
    start_time = time.time()
    plugin_root = Path(__file__).parent.parent
    claude_dir = Path.home() / ".claude"
    fallback_manager = create_fallback_manager(plugin_root)

    print("📦 Session end: Creating handoff and backup...", file=sys.stderr)

    # Get project path from hook payload via stdin (fallback to cwd)
    project_path = get_project_path_from_stdin()

    session_data = create_handoff_from_context(project_path)
    handoff = None
    handoff_path = None
    backup_metadata = None

    # Create single instances to reuse
    handoff_protocol = HandoffProtocol(claude_dir)
    backup_system = StateBackup()

    # 1. Create handoff
    try:
        handoff = handoff_protocol.create_from_session(session_data)
        handoff_path = handoff_protocol.save_handoff(handoff)
        print(f"✅ Handoff saved: {handoff_path.name}", file=sys.stderr)
    except Exception as e:
        action, message = fallback_manager.handle_failure('Stop', e)
        print(f"⚠️ Handoff creation failed: {message}", file=sys.stderr)

    # 2. Create backup
    try:
        backup_metadata = backup_system.create_default_backup(reason="session-end")
        print(f"✅ Backup created: {backup_metadata.backup_id}", file=sys.stderr)
    except Exception as e:
        action, message = fallback_manager.handle_failure('Stop', e)
        print(f"⚠️ Backup creation failed: {message}", file=sys.stderr)

    # 3. Cleanup old backups (reuse instance)
    try:
        removed_backups = backup_system.cleanup_old_backups(keep=10)
        if removed_backups > 0:
            print(f"🧹 Cleaned up {removed_backups} old backups", file=sys.stderr)
    except Exception as e:
        pass  # Cleanup failures are not critical

    # 4. Cleanup old handoffs (reuse instance)
    try:
        if handoff_path:
            removed_handoffs = handoff_protocol.cleanup_old_handoffs(keep=30)
            if removed_handoffs > 0:
                print(f"🧹 Cleaned up {removed_handoffs} old handoff files", file=sys.stderr)
    except Exception as e:
        pass  # Cleanup failures are not critical

    # 5. Log KPI session_end event
    try:
        duration_seconds = int(time.time() - start_time)
        kpi_logger = KPILogger()
        session_id = session_data.get('session_id', time.strftime('%Y%m%d-%H%M%S'))
        artifacts_count = len(handoff.artifacts) if handoff else 0
        kpi_logger.log_session_end(
            session_id=session_id,
            duration_seconds=duration_seconds,
            total_files_modified=artifacts_count,
            total_auto_fixes=0
        )
    except Exception as e:
        pass  # KPI logging failures are not critical

    # Return 0 - don't block session end even on failures
    return 0


if __name__ == "__main__":
    sys.exit(main())

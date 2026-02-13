#!/usr/bin/env python3
"""
Handoff + Backup Script (PreCompact Hook)

Fuses Handoff Protocol + Backup/Rollback:
1. Creates handoff document for next session
2. Backs up context state for rollback capability
3. Cleans up old backups

This runs before context is compacted, ensuring state preservation.
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


def create_handoff_from_context() -> dict[str, Any]:
    """Create handoff from current context files."""
    from typing import Any

    claude_dir = Path.home() / ".claude"
    context_dir = claude_dir / ".context"

    notes = f"Session end backup - {datetime.now().isoformat()}"

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
        content = claude_md.read_text()

        # Look for project info
        if "Projects" in content:
            session_data['context'] = {'projects_mentioned': True}

        # Look for recent work
        if "## Recent Work" in content or "## Current Work" in content:
            notes += "\nRecent work section found in CLAUDE.md"
            session_data['notes'] = notes

    # Get any files in current directory as artifacts
    cwd = Path.cwd()
    if cwd != Path.home():
        # List recent files as potential artifacts
        try:
            import time
            cutoff = time.time() - 3600  # Last hour
            recent_files = []
            for f in cwd.rglob("*"):
                if f.is_file() and f.stat().st_mtime > cutoff:
                    # Only include source files
                    if f.suffix in ['.py', '.ts', '.tsx', '.js', '.jsx', '.md', '.json']:
                        recent_files.append(str(f.relative_to(cwd)))

            if recent_files:
                session_data['artifacts'] = recent_files[:20]  # Limit to 20
        except (OSError, PermissionError) as e:
            import logging
            logging.warning(f"Failed to discover recent files in {cwd}: {e}")

    return session_data


def main() -> int:
    """Create handoff and backup before session compact."""
    start_time = time.time()
    plugin_root = Path(__file__).parent.parent
    claude_dir = Path.home() / ".claude"

    print("📦 Pre-compact: Creating handoff and backup...")

    # 1. Create handoff
    handoff_protocol = HandoffProtocol(claude_dir)
    session_data = create_handoff_from_context()
    handoff = handoff_protocol.create_from_session(session_data)
    handoff_path = handoff_protocol.save_handoff(handoff)

    print(f"✅ Handoff saved: {handoff_path.name}")
    print(f"   - {len(handoff.completed_tasks)} completed tasks")
    print(f"   - {len(handoff.next_steps)} next steps")
    print(f"   - {len(handoff.artifacts)} artifacts")

    # 2. Create backup
    backup_system = StateBackup()
    backup_metadata = backup_system.create_default_backup(reason="pre-compact")

    print(f"✅ Backup created: {backup_metadata.backup_id}")
    print(f"   - {len(backup_metadata.files_backed_up)} files backed up")
    print(f"   - Restore: {backup_metadata.restore_command}")

    # 3. Cleanup old backups
    removed_backups = backup_system.cleanup_old_backups(keep=10)
    if removed_backups > 0:
        print(f"🧹 Cleaned up {removed_backups} old backups")

    # 4. Cleanup old handoffs
    removed_handoffs = handoff_protocol.cleanup_old_handoffs(keep=30)
    if removed_handoffs > 0:
        print(f"🧹 Cleaned up {removed_handoffs} old handoff files")

    # 5. Log KPI session_end event
    duration_seconds = int(time.time() - start_time)
    kpi_logger = KPILogger()
    session_id = session_data.get('session_id', time.strftime('%Y%m%d-%H%M%S'))
    kpi_logger.log_session_end(
        session_id=session_id,
        duration_seconds=duration_seconds,
        total_files_modified=len(handoff.artifacts),
        total_auto_fixes=0  # This hook doesn't track auto-fixes
    )

    return 0


if __name__ == "__main__":
    sys.exit(main())

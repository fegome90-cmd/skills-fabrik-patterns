#!/usr/bin/env python3
"""
Restore State from Backup

CLI utility to restore Claude Code state from backups.
Supports listing available backups and restoring specific backups.

Usage:
    python3 restore-backup.py --list
    python3 restore-backup.py <backup_id>
    python3 restore-backup.py --latest
"""

import argparse
import sys
from pathlib import Path
from datetime import datetime

# Add lib to path
lib_dir = Path(__file__).parent.parent / "lib"
sys.path.insert(0, str(lib_dir))

from backup import StateBackup


def format_backup_metadata(metadata, index: int) -> str:
    """Format backup metadata for display."""
    lines = [
        f"  [{index}] {metadata.backup_id}",
        f"      Time: {metadata.timestamp}",
        f"      Reason: {metadata.reason}",
        f"      Files: {len(metadata.files_backed_up)}",
    ]
    if metadata.files_backed_up:
        lines.append("      Backed up files:")
        for file_path in metadata.files_backed_up:
            lines.append(f"        - {file_path}")
    lines.append(f"      Restore: {metadata.restore_command}")
    return "\n".join(lines)


def list_backups(backup_system: StateBackup, limit: int = 20) -> None:
    """List available backups."""
    backups = backup_system.list_backups(limit=limit)

    if not backups:
        print("No backups found.")
        return

    print(f"Found {len(backups)} backup(s):\n")
    for i, metadata in enumerate(backups, 1):
        print(format_backup_metadata(metadata, i))
        print()


def restore_backup(backup_system: StateBackup, backup_id: str) -> bool:
    """Restore a specific backup."""
    # First, verify the backup exists
    backups = backup_system.list_backups(limit=100)
    backup_exists = any(b.backup_id == backup_id for b in backups)

    if not backup_exists:
        print(f"❌ Backup '{backup_id}' not found.")
        print("\nAvailable backups:")
        list_backups(backup_system, limit=10)
        return False

    print(f"Restoring from backup: {backup_id}")

    # Show what will be restored
    backup_path = backup_system.backup_dir / backup_id
    metadata_path = backup_path / "metadata.json"
    if metadata_path.exists():
        import json
        metadata = json.loads(metadata_path.read_text())
        files_count = len(metadata.get('files_backed_up', []))
        print(f"Will restore {files_count} file(s)")

    success = backup_system.restore_backup(backup_id)

    if success:
        print(f"✅ Successfully restored from backup: {backup_id}")
        return True
    else:
        print(f"❌ Failed to restore backup: {backup_id}")
        return False


def restore_latest(backup_system: StateBackup) -> bool:
    """Restore the most recent backup."""
    backups = backup_system.list_backups(limit=1)

    if not backups:
        print("No backups found.")
        return False

    latest = backups[0]
    print(f"Restoring latest backup: {latest.backup_id}")
    print(f"Created: {latest.timestamp}")
    print(f"Reason: {latest.reason}")

    return restore_backup(backup_system, latest.backup_id)


def confirm_restore() -> bool:
    """Ask user to confirm restore operation."""
    response = input("\n⚠️  This will overwrite existing files. Continue? [y/N] ").strip().lower()
    return response in ('y', 'yes')


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Restore Claude Code state from backups",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --list              List all available backups
  %(prog)s --latest            Restore the most recent backup
  %(prog)s 20250110-143000      Restore specific backup by ID
  %(prog)s --latest --yes      Restore latest without confirmation
        """
    )

    parser.add_argument(
        "backup_id",
        nargs="?",
        help="Backup ID to restore (format: YYYYMMDD-HHMMSS)"
    )

    parser.add_argument(
        "-l", "--list",
        action="store_true",
        help="List available backups"
    )

    parser.add_argument(
        "--latest",
        action="store_true",
        help="Restore the most recent backup"
    )

    parser.add_argument(
        "-y", "--yes",
        action="store_true",
        help="Skip confirmation prompt"
    )

    parser.add_argument(
        "--backup-dir",
        type=Path,
        default=Path.home() / ".claude" / "backups",
        help="Custom backup directory (default: ~/.claude/backups)"
    )

    args = parser.parse_args()

    # Initialize backup system
    backup_system = StateBackup(backup_dir=args.backup_dir)

    # Handle --list flag
    if args.list:
        list_backups(backup_system)
        return 0

    # Handle --latest flag
    if args.latest:
        if not args.yes and not confirm_restore():
            print("Restore cancelled.")
            return 1
        return 0 if restore_latest(backup_system) else 1

    # Handle backup_id argument
    if args.backup_id:
        if not args.yes and not confirm_restore():
            print("Restore cancelled.")
            return 1
        return 0 if restore_backup(backup_system, args.backup_id) else 1

    # No action specified - show help
    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())

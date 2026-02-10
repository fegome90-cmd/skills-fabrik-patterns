"""
Backup/Rollback Module

Deterministic state backup and recovery.
Pattern from: Skills-Fabrik code-quality-upgrade/backup-configs.sh

Creates timestamped backups of important files with rollback capability.
"""

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
import shutil
import json


@dataclass(frozen=True)
class BackupMetadata:
    """Metadata about a backup."""
    timestamp: str
    backup_id: str
    files_backed_up: list[str]
    reason: str
    restore_command: str


class StateBackup:
    """Manages state backups and restoration."""

    def __init__(self, backup_dir: Path | None = None):
        """
        Initialize backup system.

        Args:
            backup_dir: Directory for storing backups. Defaults to ~/.claude/backups
        """
        self.backup_dir = backup_dir or Path.home() / ".claude" / "backups"
        self.backup_dir.mkdir(parents=True, exist_ok=True)

    def create_backup(
        self,
        files: list[Path],
        reason: str = "manual"
    ) -> BackupMetadata:
        """
        Create timestamped backup of specified files.

        Args:
            files: List of file paths to backup
            reason: Reason for the backup

        Returns:
            Backup metadata
        """
        backup_id = datetime.now().strftime('%Y%m%d-%H%M%S')
        backup_path = self.backup_dir / backup_id
        backup_path.mkdir(exist_ok=True)

        backed_up = []

        for file_path in files:
            if not file_path.exists():
                continue

            # Create relative path structure in backup
            rel_path = file_path.name
            dest = backup_path / rel_path

            shutil.copy2(file_path, dest)
            backed_up.append(str(file_path))

        metadata = BackupMetadata(
            timestamp=datetime.now().isoformat(),
            backup_id=backup_id,
            files_backed_up=backed_up,
            reason=reason,
            restore_command=(
                f"python3 ~/.claude/plugins/skills-fabrik-patterns/"
                f"scripts/backup-state.py --restore {backup_id}"
            )
        )

        # Save metadata
        metadata_path = backup_path / "metadata.json"
        metadata_path.write_text(json.dumps(metadata.__dict__, indent=2))

        return metadata

    def restore_backup(self, backup_id: str) -> bool:
        """
        Restore files from backup.

        Args:
            backup_id: ID of backup to restore

        Returns:
            True if restore successful, False otherwise
        """
        backup_path = self.backup_dir / backup_id

        if not backup_path.exists():
            return False

        metadata_path = backup_path / "metadata.json"
        if not metadata_path.exists():
            return False

        metadata = json.loads(metadata_path.read_text())

        # Restore files
        for file_path in metadata['files_backed_up']:
            backup_file = backup_path / Path(file_path).name

            if not backup_file.exists():
                continue

            # Create parent directories if needed
            dest = Path(file_path)
            dest.parent.mkdir(parents=True, exist_ok=True)

            shutil.copy2(backup_file, dest)

        return True

    def list_backups(self, limit: int = 20) -> list[BackupMetadata]:
        """
        List available backups.

        Args:
            limit: Maximum number of backups to return

        Returns:
            List of backup metadata, newest first
        """
        backups = []

        for backup_dir in sorted(
            self.backup_dir.iterdir(),
            key=lambda p: p.stat().st_mtime,
            reverse=True
        ):
            if not backup_dir.is_dir():
                continue

            metadata_path = backup_dir / "metadata.json"
            if not metadata_path.exists():
                continue

            try:
                metadata = json.loads(metadata_path.read_text())
                backups.append(BackupMetadata(**metadata))
            except (json.JSONDecodeError, TypeError):
                continue

            if len(backups) >= limit:
                break

        return backups

    def create_default_backup(self, reason: str = "pre-compact") -> BackupMetadata:
        """
        Create backup of standard Claude Code files.

        Args:
            reason: Reason for the backup

        Returns:
            Backup metadata
        """
        claude_dir = Path.home() / ".claude"

        # Standard files to backup
        context_files = [
            claude_dir / ".context" / "CLAUDE.md",
            claude_dir / ".context" / "identity.md",
            claude_dir / ".context" / "projects.md",
            claude_dir / ".context" / "preferences.md",
            claude_dir / ".context" / "rules.md",
        ]

        # Filter to existing files
        existing_files = [f for f in context_files if f.exists()]

        return self.create_backup(existing_files, reason)

    def cleanup_old_backups(self, keep: int = 10) -> int:
        """
        Remove old backups, keeping only the most recent.

        Args:
            keep: Number of backups to keep

        Returns:
            Number of backups removed
        """
        backups = sorted(
            self.backup_dir.iterdir(),
            key=lambda p: p.stat().st_mtime,
            reverse=True
        )

        removed = 0
        for backup_dir in backups[keep:]:
            if backup_dir.is_dir():
                shutil.rmtree(backup_dir)
                removed += 1

        return removed

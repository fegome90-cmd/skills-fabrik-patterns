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
import uuid
import logging

# Get module logger
logger = logging.getLogger(__name__)


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

    def _generate_backup_id(self) -> str:
        """
        Generate unique backup ID with collision resistance.

        Uses UUID4 for guaranteed uniqueness + timestamp for ordering.
        UUID4 provides ~5.3×10^36 possible values, making collisions
        virtually impossible. No artificial delays needed.

        Returns:
            Unique backup ID string (format: YYYYMMDD-HHMMSS_{uuid4})
        """
        # UUID4 for guaranteed uniqueness (NOT dependent on timestamp)
        unique_id = uuid.uuid4()
        # Timestamp only for ordering/sorting, NOT for uniqueness
        timestamp = datetime.now().strftime('%Y%m%d-%H%M%S')
        return f"{timestamp}_{unique_id}"

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
        backup_id = self._generate_backup_id()
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
        try:
            metadata_path.write_text(json.dumps(metadata.__dict__, indent=2))
        except (OSError, IOError) as e:
            logger.error(f"Failed to write backup metadata to {metadata_path}: {e}", exc_info=True)
            raise  # Re-raise since metadata is critical

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
            logger.warning(f"Backup metadata file not found: {metadata_path}")
            return False

        try:
            metadata = json.loads(metadata_path.read_text())
        except (json.JSONDecodeError, OSError) as e:
            logger.error(f"Failed to read backup metadata from {metadata_path}: {e}", exc_info=True)
            return False

        # Restore files
        for file_path in metadata['files_backed_up']:
            backup_file = backup_path / Path(file_path).name

            if not backup_file.exists():
                logger.warning(f"Backup file not found: {backup_file}")
                continue

            # Create parent directories if needed
            dest = Path(file_path)
            try:
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(backup_file, dest)
            except (OSError, IOError) as e:
                logger.error(f"Failed to restore {dest} from backup: {e}", exc_info=True)
                # Continue with other files

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
            except (json.JSONDecodeError, TypeError) as e:
                logger.warning(f"Failed to load metadata from {metadata_path}: {e}")
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
                try:
                    shutil.rmtree(backup_dir)
                    removed += 1
                except (OSError, IOError) as e:
                    logger.error(f"Failed to remove old backup {backup_dir}: {e}", exc_info=True)

        return removed

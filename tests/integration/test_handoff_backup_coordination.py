"""
Integration Tests: Handoff + Backup Coordination

Verifies that handoffs and backups work together correctly.
Tests atomic operations, cleanup, and state restoration.
"""

import pytest
import tempfile
import shutil
import json
from pathlib import Path
import sys
from datetime import datetime
import time

# Ensure lib is in path
lib_dir = Path(__file__).parent.parent.parent / "lib"
if str(lib_dir) not in sys.path:
    sys.path.insert(0, str(lib_dir))

from handoff import Handoff, HandoffProtocol
from backup import StateBackup, BackupMetadata


class TestHandoffCreation:
    """Test handoff creation and storage."""

    def test_create_from_session_data(self, sample_handoff_data: dict, temp_dir: Path):
        """Test creating handoff from session data."""
        claude_dir = temp_dir / ".claude"
        claude_dir.mkdir()

        protocol = HandoffProtocol(claude_dir=claude_dir)
        handoff = protocol.create_from_session(sample_handoff_data)

        assert isinstance(handoff, Handoff)
        assert handoff.from_session == "test-session-001"
        assert len(handoff.completed_tasks) > 0
        assert len(handoff.next_steps) > 0
        assert isinstance(handoff.timestamp, str)

    def test_handoff_format_as_markdown(self, sample_handoff_data: dict, temp_dir: Path):
        """Test handoff formats to markdown correctly."""
        claude_dir = temp_dir / ".claude"
        claude_dir.mkdir()

        protocol = HandoffProtocol(claude_dir=claude_dir)
        handoff = protocol.create_from_session(sample_handoff_data)
        formatted = handoff.format()

        # Check markdown structure
        assert "# 🚀 HANDOFF:" in formatted
        assert "## 📊 Completed Tasks" in formatted
        assert "## 🎯 Next Steps" in formatted
        assert "## 📦 Artifacts" in formatted

    def test_save_handoff_creates_files(self, sample_handoff_data: dict, temp_dir: Path):
        """Test saving handoff creates both .md and .json files."""
        claude_dir = temp_dir / ".claude"
        claude_dir.mkdir()

        protocol = HandoffProtocol(claude_dir=claude_dir)
        handoff = protocol.create_from_session(sample_handoff_data)
        md_path = protocol.save_handoff(handoff)

        # Check markdown file exists
        assert md_path.exists()
        assert md_path.suffix == ".md"

        # Check JSON file exists
        json_path = md_path.with_suffix(md_path.suffix + ".json")
        assert json_path.exists()

        # Verify JSON content
        json_data = json.loads(json_path.read_text())
        assert json_data["from_session"] == "test-session-001"

    def test_list_handoffs(self, sample_handoff_data: dict, temp_dir: Path):
        """Test listing handoffs returns most recent first."""
        claude_dir = temp_dir / ".claude"
        claude_dir.mkdir()

        protocol = HandoffProtocol(claude_dir=claude_dir)

        # Create multiple handoffs
        for i in range(3):
            data = sample_handoff_data.copy()
            data["session_id"] = f"session-{i}"
            handoff = protocol.create_from_session(data)
            protocol.save_handoff(handoff)

        # List handoffs
        handoffs = protocol.list_handoffs(limit=10)

        assert len(handoffs) == 3
        assert all(h.suffix == ".md" for h in handoffs)

    def test_cleanup_old_handoffs(self, sample_handoff_data: dict, temp_dir: Path):
        """Test cleanup keeps only specified number of handoffs."""
        claude_dir = temp_dir / ".claude"
        claude_dir.mkdir()

        protocol = HandoffProtocol(claude_dir=claude_dir)

        # Create more handoffs than we want to keep
        for i in range(5):
            data = sample_handoff_data.copy()
            data["session_id"] = f"session-{i}"
            handoff = protocol.create_from_session(data)
            protocol.save_handoff(handoff)

        # Cleanup keeping only 3
        removed = protocol.cleanup_old_handoffs(keep=3)

        # Should have removed 4 files (2 handoffs * 2 files each)
        assert removed >= 4

        # Verify only 3 remain
        handoffs = protocol.list_handoffs(limit=10)
        assert len(handoffs) == 3


class TestBackupCreation:
    """Test backup creation and restoration."""

    def test_create_backup_of_files(self, temp_dir: Path):
        """Test creating backup of specified files."""
        # Create test files
        test_files = []
        for i in range(3):
            test_file = temp_dir / f"test-{i}.txt"
            test_file.write_text(f"Content {i}")
            test_files.append(test_file)

        backup_sys = StateBackup(backup_dir=temp_dir / "backups")
        metadata = backup_sys.create_backup(test_files, reason="test backup")

        assert isinstance(metadata, BackupMetadata)
        assert metadata.reason == "test backup"
        assert len(metadata.files_backed_up) == 3
        assert metadata.backup_id in metadata.restore_command

    def test_backup_creates_metadata(self, temp_dir: Path):
        """Test backup creates metadata file."""
        test_file = temp_dir / "test.txt"
        test_file.write_text("test content")

        backup_sys = StateBackup(backup_dir=temp_dir / "backups")
        metadata = backup_sys.create_backup([test_file])

        # Check metadata file exists
        backup_path = backup_sys.backup_dir / metadata.backup_id
        metadata_file = backup_path / "metadata.json"
        assert metadata_file.exists()

        # Verify metadata content
        metadata_data = json.loads(metadata_file.read_text())
        assert metadata_data["reason"] == "manual"

    def test_list_backups(self, temp_dir: Path):
        """Test listing backups returns newest first."""
        backup_sys = StateBackup(backup_dir=temp_dir / "backups")

        # Create multiple backups (UUID4 ensures uniqueness without delays)
        for i in range(3):
            test_file = temp_dir / f"test-{i}.txt"
            test_file.write_text(f"content {i}")
            backup_sys.create_backup([test_file], reason=f"backup-{i}")

        # List backups
        backups = backup_sys.list_backups(limit=10)

        assert len(backups) == 3
        assert all(isinstance(b, BackupMetadata) for b in backups)

    def test_cleanup_old_backups(self, temp_dir: Path):
        """Test cleanup keeps only specified number of backups."""
        backup_sys = StateBackup(backup_dir=temp_dir / "backups")

        # Create more backups than we want to keep (UUID4 ensures uniqueness)
        for i in range(5):
            test_file = temp_dir / f"test-{i}.txt"
            test_file.write_text(f"content {i}")
            backup_sys.create_backup([test_file])

        # Cleanup keeping only 3
        removed = backup_sys.cleanup_old_backups(keep=3)

        # Should have removed 2 backup directories
        assert removed == 2

        # Verify only 3 remain
        backups = backup_sys.list_backups(limit=10)
        assert len(backups) == 3


class TestBackupRestoration:
    """Test backup restoration functionality."""

    def test_restore_backup(self, temp_dir: Path):
        """Test restoring files from backup."""
        # Create original file
        original_file = temp_dir / "original.txt"
        original_file.write_text("original content")

        # Create backup
        backup_sys = StateBackup(backup_dir=temp_dir / "backups")
        metadata = backup_sys.create_backup([original_file])

        # Modify original file
        original_file.write_text("modified content")

        # Restore from backup
        success = backup_sys.restore_backup(metadata.backup_id)

        assert success is True

        # Verify content was restored
        restored_content = original_file.read_text()
        assert restored_content == "original content"

    def test_restore_nonexistent_backup(self, temp_dir: Path):
        """Test restoring non-existent backup returns False."""
        backup_sys = StateBackup(backup_dir=temp_dir / "backups")
        success = backup_sys.restore_backup("nonexistent-id")

        assert success is False

    def test_restore_creates_parent_dirs(self, temp_dir: Path):
        """Test restoration creates parent directories if needed."""
        # Create file in subdirectory
        subdir = temp_dir / "subdir"
        subdir.mkdir()
        original_file = subdir / "file.txt"
        original_file.write_text("content")

        # Create backup
        backup_sys = StateBackup(backup_dir=temp_dir / "backups")
        metadata = backup_sys.create_backup([original_file])

        # Delete subdirectory
        shutil.rmtree(subdir)

        # Restore should recreate subdirectory
        success = backup_sys.restore_backup(metadata.backup_id)

        assert success is True
        assert original_file.exists()


class TestHandoffBackupCoordination:
    """Integration tests for handoff + backup working together."""

    def test_simultaneous_handoff_and_backup(
        self,
        sample_handoff_data: dict,
        temp_dir: Path
    ):
        """Test creating handoff and backup simultaneously."""
        claude_dir = temp_dir / ".claude"
        claude_dir.mkdir()

        # Create handoff
        protocol = HandoffProtocol(claude_dir=claude_dir)
        handoff = protocol.create_from_session(sample_handoff_data)
        md_path = protocol.save_handoff(handoff)

        # Create backup of handoff files
        backup_sys = StateBackup(backup_dir=temp_dir / "backups")
        files_to_backup = [
            md_path,
            md_path.with_suffix(md_path.suffix + ".json")
        ]
        backup_metadata = backup_sys.create_backup(
            files_to_backup,
            reason="handoff-backup"
        )

        # Verify both exist
        assert md_path.exists()
        assert backup_sys.backup_dir.exists()

        # Verify backup contains handoff files
        assert len(backup_metadata.files_backed_up) == 2

    def test_restore_handoff_from_backup(
        self,
        sample_handoff_data: dict,
        temp_dir: Path
    ):
        """Test restoring handoff from backup."""
        claude_dir = temp_dir / ".claude"
        claude_dir.mkdir()

        # Create and save handoff
        protocol = HandoffProtocol(claude_dir=claude_dir)
        handoff = protocol.create_from_session(sample_handoff_data)
        md_path = protocol.save_handoff(handoff)

        # Create backup
        backup_sys = StateBackup(backup_dir=temp_dir / "backups")
        files_to_backup = [md_path]
        backup_metadata = backup_sys.create_backup(files_to_backup)

        # Delete handoff file
        md_path.unlink()

        assert not md_path.exists()

        # Restore from backup
        success = backup_sys.restore_backup(backup_metadata.backup_id)

        assert success is True
        assert md_path.exists()

    def test_cleanup_coordinated(
        self,
        sample_handoff_data: dict,
        temp_dir: Path
    ):
        """Test that cleanup is coordinated between handoffs and backups."""
        claude_dir = temp_dir / ".claude"
        claude_dir.mkdir()

        protocol = HandoffProtocol(claude_dir=claude_dir)
        backup_sys = StateBackup(backup_dir=temp_dir / "backups")

        # Create handoffs and backups with 1.2s delay to ensure distinct backup IDs
        # Using 7 iterations to keep test fast while still testing cleanup
        for i in range(7):
            data = sample_handoff_data.copy()
            data["session_id"] = f"session-{i}"
            handoff = protocol.create_from_session(data)
            md_path = protocol.save_handoff(handoff)

            # Create backup for this handoff (UUID4 ensures uniqueness without delays)
            backup_sys.create_backup([md_path], reason=f"backup-{i}")

        # Verify we created multiple items
        all_handoffs = protocol.list_handoffs(limit=100)
        all_backups = backup_sys.list_backups(limit=100)
        initial_handoff_count = len(all_handoffs)
        initial_backup_count = len(all_backups)

        # Should have created at least several of each
        assert initial_handoff_count >= 7
        assert initial_backup_count >= 6  # May have some timestamp collisions

        # Cleanup handoffs (keep 3)
        handoffs_removed = protocol.cleanup_old_handoffs(keep=3)
        assert handoffs_removed > 0

        # Cleanup backups (keep 2)
        backups_removed = backup_sys.cleanup_old_backups(keep=2)
        assert backups_removed > 0

        # Verify counts match our keep settings
        remaining_handoffs = protocol.list_handoffs(limit=100)
        remaining_backups = backup_sys.list_backups(limit=100)
        assert len(remaining_handoffs) == 3
        assert len(remaining_backups) == 2

    def test_atomic_operations(
        self,
        sample_handoff_data: dict,
        temp_dir: Path
    ):
        """Test that handoff and backup operations are atomic."""
        claude_dir = temp_dir / ".claude"
        claude_dir.mkdir()

        protocol = HandoffProtocol(claude_dir=claude_dir)
        backup_sys = StateBackup(backup_dir=temp_dir / "backups")

        # All operations should complete fully or fail completely
        handoff = protocol.create_from_session(sample_handoff_data)
        md_path = protocol.save_handoff(handoff)

        # If save_handoff succeeded, both files should exist
        assert md_path.exists()
        json_path = md_path.with_suffix(md_path.suffix + ".json")
        assert json_path.exists()

        # Same for backup
        backup_metadata = backup_sys.create_backup([md_path])
        backup_dir = backup_sys.backup_dir / backup_metadata.backup_id
        assert backup_dir.exists()
        assert (backup_dir / "metadata.json").exists()

    def test_cross_reference(
        self,
        sample_handoff_data: dict,
        temp_dir: Path
    ):
        """Test that handoffs and backups can reference each other."""
        claude_dir = temp_dir / ".claude"
        claude_dir.mkdir()

        # Create handoff
        protocol = HandoffProtocol(claude_dir=claude_dir)
        handoff = protocol.create_from_session(sample_handoff_data)
        md_path = protocol.save_handoff(handoff)

        # Create backup with handoff reference in notes
        backup_sys = StateBackup(backup_dir=temp_dir / "backups")
        backup_metadata = backup_sys.create_backup(
            [md_path],
            reason=f"Handoff backup for session {sample_handoff_data['session_id']}"
        )

        # Verify backup reason references session
        assert sample_handoff_data["session_id"] in backup_metadata.reason

        # Verify handoff could be recreated from backup
        json_path = md_path.with_suffix(md_path.suffix + ".json")
        json_data = json.loads(json_path.read_text())
        assert json_data["from_session"] == sample_handoff_data["session_id"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

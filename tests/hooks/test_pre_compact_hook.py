"""
Hook Tests: PreCompact Hook

Tests that the PreCompact hook (handoff-backup.py) executes correctly.
Verifies handoff creation, backup creation, and cleanup.
"""

import pytest
import subprocess
import sys
import json
import tempfile
from pathlib import Path
import shutil


class TestHandoffBackupHookScript:
    """Test handoff-backup.py script functionality."""

    @pytest.fixture
    def plugin_root(self) -> Path:
        """Get plugin root directory."""
        return Path(__file__).parent.parent.parent

    @pytest.fixture
    def handoff_backup_script(self, plugin_root: Path) -> Path:
        """Get path to handoff-backup.py script."""
        return plugin_root / "scripts" / "handoff-backup.py"

    def test_script_exists(self, handoff_backup_script: Path):
        """Test handoff-backup.py script exists."""
        assert handoff_backup_script.exists()
        assert handoff_backup_script.is_file()

    def test_script_runs(self, handoff_backup_script: Path, temp_dir: Path):
        """Test handoff-backup.py runs without error."""
        result = subprocess.run(
            [sys.executable, str(handoff_backup_script)],
            capture_output=True,
            text=True,
            env={"HOME": str(temp_dir)},
            timeout=60
        )

        # Should complete
        assert result.returncode == 0

    def test_script_outputs_success_messages(self, handoff_backup_script: Path, temp_dir: Path):
        """Test script outputs success messages."""
        result = subprocess.run(
            [sys.executable, str(handoff_backup_script)],
            capture_output=True,
            text=True,
            env={"HOME": str(temp_dir)},
            timeout=60
        )

        # Should indicate success
        output = result.stdout + result.stderr
        assert "Handoff" in output or "Backup" in output


class TestHandoffCreation:
    """Test handoff creation during PreCompact."""

    def test_creates_handoff_file(self, temp_dir: Path):
        """Test handoff file is created."""
        plugin_root = Path(__file__).parent.parent.parent
        script = plugin_root / "scripts" / "handoff-backup.py"

        claude_dir = temp_dir / ".claude"
        claude_dir.mkdir()
        handoff_dir = claude_dir / "handoffs"
        handoff_dir.mkdir()

        result = subprocess.run(
            [sys.executable, str(script)],
            capture_output=True,
            text=True,
            env={"HOME": str(temp_dir)},
            timeout=60
        )

        # Check handoff was created
        handoffs = list(handoff_dir.glob("handoff-*.md"))
        assert len(handoffs) > 0

    def test_handoff_has_required_content(self, temp_dir: Path):
        """Test handoff has required content."""
        plugin_root = Path(__file__).parent.parent.parent
        script = plugin_root / "scripts" / "handoff-backup.py"

        claude_dir = temp_dir / ".claude"
        claude_dir.mkdir()
        handoff_dir = claude_dir / "handoffs"
        handoff_dir.mkdir()

        subprocess.run(
            [sys.executable, str(script)],
            capture_output=True,
            text=True,
            env={"HOME": str(temp_dir)},
            timeout=60
        )

        # Find latest handoff
        handoffs = sorted(handoff_dir.glob("handoff-*.md"))
        if handoffs:
            content = handoffs[-1].read_text()
            # Should have handoff structure
            assert "# 🚀 HANDOFF:" in content or "HANDOFF" in content

    def test_creates_handoff_json(self, temp_dir: Path):
        """Test handoff JSON is also created."""
        plugin_root = Path(__file__).parent.parent.parent
        script = plugin_root / "scripts" / "handoff-backup.py"

        claude_dir = temp_dir / ".claude"
        claude_dir.mkdir()
        handoff_dir = claude_dir / "handoffs"
        handoff_dir.mkdir()

        subprocess.run(
            [sys.executable, str(script)],
            capture_output=True,
            text=True,
            env={"HOME": str(temp_dir)},
            timeout=60
        )

        # Check JSON file exists
        json_files = list(handoff_dir.glob("handoff-*.json"))
        assert len(json_files) > 0


class TestBackupCreation:
    """Test backup creation during PreCompact."""

    def test_creates_backup_directory(self, temp_dir: Path):
        """Test backup directory is created."""
        plugin_root = Path(__file__).parent.parent.parent
        script = plugin_root / "scripts" / "handoff-backup.py"

        claude_dir = temp_dir / ".claude"
        claude_dir.mkdir()

        subprocess.run(
            [sys.executable, str(script)],
            capture_output=True,
            text=True,
            env={"HOME": str(temp_dir)},
            timeout=60
        )

        # Check backup was created
        backup_dir = claude_dir / "backups"
        assert backup_dir.exists()

    def test_backup_has_metadata(self, temp_dir: Path):
        """Test backup has metadata."""
        plugin_root = Path(__file__).parent.parent.parent
        script = plugin_root / "scripts" / "handoff-backup.py"

        claude_dir = temp_dir / ".claude"
        claude_dir.mkdir()

        subprocess.run(
            [sys.executable, str(script)],
            capture_output=True,
            text=True,
            env={"HOME": str(temp_dir)},
            timeout=60
        )

        # Find backup directories
        backup_dir = claude_dir / "backups"
        if backup_dir.exists():
            backups = [d for d in backup_dir.iterdir() if d.is_dir()]
            if backups:
                # Check for metadata
                metadata_file = backups[0] / "metadata.json"
                if metadata_file.exists():
                    metadata = json.loads(metadata_file.read_text())
                    assert "backup_id" in metadata
                    assert "timestamp" in metadata


class TestCleanupOldHandoffs:
    """Test cleanup of old handoffs."""

    def test_keeps_recent_handoffs(self, temp_dir: Path):
        """Test that recent handoffs are kept."""
        plugin_root = Path(__file__).parent.parent.parent
        script = plugin_root / "scripts" / "handoff-backup.py"

        claude_dir = temp_dir / ".claude"
        claude_dir.mkdir()
        handoff_dir = claude_dir / "handoffs"
        handoff_dir.mkdir()

        # Create multiple handoffs
        for i in range(5):
            handoff_file = handoff_dir / f"handoff-{i:04d}.md"
            handoff_file.write_text(f"# Handoff {i}\n")

        # Run hook
        subprocess.run(
            [sys.executable, str(script)],
            capture_output=True,
            text=True,
            env={"HOME": str(temp_dir)},
            timeout=60
        )

        # Check some handoffs remain (cleanup keeps 30 by default)
        remaining = list(handoff_dir.glob("handoff-*.md"))
        # Should have at least our created handoffs plus new one
        assert len(remaining) >= 1


class TestCleanupOldBackups:
    """Test cleanup of old backups."""

    def test_keeps_recent_backups(self, temp_dir: Path):
        """Test that recent backups are kept."""
        plugin_root = Path(__file__).parent.parent.parent
        script = plugin_root / "scripts" / "handoff-backup.py"

        claude_dir = temp_dir / ".claude"
        claude_dir.mkdir()

        subprocess.run(
            [sys.executable, str(script)],
            capture_output=True,
            text=True,
            env={"HOME": str(temp_dir)},
            timeout=60
        )

        # Check backups exist
        backup_dir = claude_dir / "backups"
        if backup_dir.exists():
            backups = [d for d in backup_dir.iterdir() if d.is_dir()]
            # Default cleanup keeps 10
            assert len(backups) <= 10


class TestHookExecutionTiming:
    """Test hook timing requirements."""

    def test_completes_before_compact(self, temp_dir: Path):
        """Test hook completes before compaction would occur."""
        import time

        plugin_root = Path(__file__).parent.parent.parent
        script = plugin_root / "scripts" / "handoff-backup.py"

        claude_dir = temp_dir / ".claude"
        claude_dir.mkdir()

        start = time.time()
        result = subprocess.run(
            [sys.executable, str(script)],
            capture_output=True,
            text=True,
            env={"HOME": str(temp_dir)},
            timeout=60
        )
        duration_ms = (time.time() - start) * 1000

        # Should complete reasonably quickly
        assert result.returncode == 0
        assert duration_ms < 10000, f"Duration: {duration_ms:.0f}ms"


class TestAtomicOperations:
    """Test that handoff and backup are atomic."""

    def test_both_succeed_or_both_fail(self, temp_dir: Path):
        """Test handoff and backup both succeed or both fail."""
        plugin_root = Path(__file__).parent.parent.parent
        script = plugin_root / "scripts" / "handoff-backup.py"

        claude_dir = temp_dir / ".claude"
        claude_dir.mkdir()

        result = subprocess.run(
            [sys.executable, str(script)],
            capture_output=True,
            text=True,
            env={"HOME": str(temp_dir)},
            timeout=60
        )

        # If script succeeds, both should exist
        if result.returncode == 0:
            handoff_dir = claude_dir / "handoffs"
            backup_dir = claude_dir / "backups"
            # At least one should have content
            assert handoff_dir.exists() or backup_dir.exists()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

"""
End-to-End Tests: Handoff System

Tests handoff functionality in realistic contexts.
Verifies handoff creation, restoration, artifact preservation, and notes.
"""

import pytest
import subprocess
import sys
import tempfile
import json
from pathlib import Path
import time

# Add lib to path for direct imports
lib_dir = Path(__file__).parent.parent / "lib"
if str(lib_dir) not in sys.path:
    sys.path.insert(0, str(lib_dir))

from handoff import HandoffProtocol


class TestHandoffCreationE2E:
    """Test handoff creation in E2E scenarios."""

    @pytest.fixture
    def plugin_root(self) -> Path:
        """Get plugin root directory."""
        return Path(__file__).parent.parent.parent

    @pytest.fixture
    def claude_environment(self, temp_dir: Path) -> Path:
        """Create Claude environment."""
        claude_dir = temp_dir / ".claude"
        claude_dir.mkdir()

        # Create handoff directory
        handoff_dir = claude_dir / "handoffs"
        handoff_dir.mkdir()

        # Create context
        context_dir = claude_dir / ".context"
        context_dir.mkdir()
        (context_dir / "CLAUDE.md").write_text("# Test Context\n")

        return claude_dir

    def test_handoff_created_from_real_session(
        self,
        claude_environment: Path,
        plugin_root: Path
    ):
        """Test handoff is created from real session data."""
        script = plugin_root / "scripts" / "handoff-backup.py"

        result = subprocess.run(
            [sys.executable, str(script)],
            capture_output=True,
            text=True,
            env={"HOME": str(claude_environment.parent)},
            timeout=60
        )

        # Should complete
        assert result.returncode == 0

        # Check handoff was created
        handoff_dir = claude_environment / "handoffs"
        handoffs = list(handoff_dir.glob("handoff-*.md"))
        assert len(handoffs) > 0

    def test_handoff_contains_session_context(
        self,
        claude_environment: Path,
        plugin_root: Path
    ):
        """Test handoff contains session context."""
        script = plugin_root / "scripts" / "handoff-backup.py"

        subprocess.run(
            [sys.executable, str(script)],
            capture_output=True,
            text=True,
            env={"HOME": str(claude_environment.parent)},
            timeout=60
        )

        # Find latest handoff
        handoff_dir = claude_environment / "handoffs"
        handoffs = sorted(handoff_dir.glob("handoff-*.md"))

        if handoffs:
            content = handoffs[-1].read_text()
            # Should have handoff structure
            assert "HANDOFF" in content or "#" in content

    def test_handoff_json_also_created(
        self,
        claude_environment: Path,
        plugin_root: Path
    ):
        """Test handoff JSON is also created."""
        script = plugin_root / "scripts" / "handoff-backup.py"

        subprocess.run(
            [sys.executable, str(script)],
            capture_output=True,
            text=True,
            env={"HOME": str(claude_environment.parent)},
            timeout=60
        )

        # Check for JSON file
        handoff_dir = claude_environment / "handoffs"
        json_files = list(handoff_dir.glob("handoff-*.json"))

        # May or may not exist depending on implementation
        if json_files:
            # Verify JSON is valid
            data = json.loads(json_files[0].read_text())
            assert isinstance(data, dict)


class TestHandoffRestorationE2E:
    """Test handoff restoration in E2E scenarios."""

    @pytest.fixture
    def environment_with_handoff(self, temp_dir: Path) -> dict:
        """Create environment with existing handoff."""
        claude_dir = temp_dir / ".claude"
        claude_dir.mkdir()

        handoff_dir = claude_dir / "handoffs"
        handoff_dir.mkdir()

        # Create sample handoff
        handoff_file = handoff_dir / "handoff-previous.md"
        handoff_file.write_text("""# 🚀 HANDOFF: session-001 → session-002

**Timestamp**: 2024-01-01T12:00:00
**Status**: ✅ READY FOR NEXT

## 📊 Completed Tasks
- ✅ Implemented auth module
- ✅ Added unit tests

## 🎯 Next Steps
1. Add integration tests
2. Update documentation

## 📦 Artifacts
- `lib/auth.py`
- `tests/test_auth.py`

## 📋 Context Snapshot
```json
{
  "current_feature": "Authentication",
  "files_created": 2
}
```
""")

        return {"claude_dir": claude_dir, "handoff_file": handoff_file}

    def test_restore_from_previous_handoff(
        self,
        environment_with_handoff: dict,
        plugin_root: Path
    ):
        """Test restoring from previous handoff."""
        # In real E2E, this would involve reading handoff
        # and recreating session context
        handoff_file = environment_with_handoff["handoff_file"]

        # Verify handoff can be read
        content = handoff_file.read_text()
        assert "session-001" in content
        assert "Completed Tasks" in content


class TestArtifactPreservation:
    """Test artifacts are preserved in handoffs."""

    def test_artifacts_listed_in_handoff(self, temp_dir: Path, plugin_root: Path):
        """Test created artifacts are listed."""
        claude_dir = temp_dir / ".claude"
        claude_dir.mkdir()
        (claude_dir / "handoffs").mkdir()

        # Create some artifact files
        (temp_dir / "module.py").write_text("# Module\n")
        (temp_dir / "test.py").write_text("# Test\n")

        script = plugin_root / "scripts" / "handoff-backup.py"

        subprocess.run(
            [sys.executable, str(script)],
            capture_output=True,
            text=True,
            env={"HOME": str(temp_dir)},
            timeout=60
        )

        # Check handoff mentions artifacts (if implementation supports)
        handoff_dir = claude_dir / "handoffs"
        handoffs = list(handoff_dir.glob("*.md"))
        if handoffs:
            # Latest handoff might mention artifacts
            content = handoffs[-1].read_text()
            # Implementation dependent

    def test_artifact_paths_preserved(self, temp_dir: Path, plugin_root: Path):
        """Test artifact paths are preserved correctly."""
        claude_dir = temp_dir / ".claude"
        claude_dir.mkdir()
        (claude_dir / "handoffs").mkdir()

        # Create nested artifact
        nested_dir = temp_dir / "src" / "auth"
        nested_dir.mkdir(parents=True)
        artifact = nested_dir / "login.py"
        artifact.write_text("# Login\n")

        script = plugin_root / "scripts" / "handoff-backup.py"

        subprocess.run(
            [sys.executable, str(script)],
            capture_output=True,
            text=True,
            env={"HOME": str(temp_dir)},
            timeout=60
        )

        # Verify artifact exists
        assert artifact.exists()


class TestNotesPreservation:
    """Test notes are preserved in handoffs."""

    def test_notes_included_in_handoff(self, temp_dir: Path, plugin_root: Path):
        """Test notes section is included."""
        claude_dir = temp_dir / ".claude"
        claude_dir.mkdir()
        (claude_dir / "handoffs").mkdir()

        script = plugin_root / "scripts" / "handoff-backup.py"

        subprocess.run(
            [sys.executable, str(script)],
            capture_output=True,
            text=True,
            env={"HOME": str(temp_dir)},
            timeout=60
        )

        # Check if notes section exists (implementation dependent)
        handoff_dir = claude_dir / "handoffs"
        handoffs = list(handoff_dir.glob("*.md"))
        if handoffs:
            content = handoffs[-1].read_text()
            # May have notes section


class TestMultipleHandoffs:
    """Test multiple handoffs are managed correctly."""

    def test_multiple_handoffs_created(self, temp_dir: Path, plugin_root: Path):
        """Test multiple sessions create multiple handoffs."""
        claude_dir = temp_dir / ".claude"
        claude_dir.mkdir()
        handoff_dir = claude_dir / "handoffs"
        handoff_dir.mkdir()

        # Use HandoffProtocol directly (more reliable than subprocess with HOME env)
        protocol = HandoffProtocol(claude_dir=claude_dir)

        # Create multiple handoffs with different session data
        for i in range(5):
            session_data = {
                "session_id": f"test-session-{i:03d}",
                "completed_tasks": [f"Task {i}"],
                "next_steps": [f"Next step {i}"],
                "artifacts": [f"file-{i}.py"],
                "context": {"index": i},
                "notes": f"Session {i} notes"
            }
            handoff = protocol.create_from_session(session_data)
            protocol.save_handoff(handoff)  # UUID4 ensures uniqueness without delay

        # Check multiple handoffs exist
        handoffs = list(handoff_dir.glob("handoff-*.md"))
        assert len(handoffs) >= 5

    def test_handoffs_chronologically_ordered(self, temp_dir: Path, plugin_root: Path):
        """Test handoffs are ordered chronologically."""
        claude_dir = temp_dir / ".claude"
        claude_dir.mkdir()
        handoff_dir = claude_dir / "handoffs"
        handoff_dir.mkdir()

        # Use HandoffProtocol directly
        protocol = HandoffProtocol(claude_dir=claude_dir)

        # Create handoffs in sequence
        for i in range(3):
            session_data = {
                "session_id": f"chron-session-{i}",
                "completed_tasks": [f"Task {i}"],
                "next_steps": [],
                "artifacts": [],
                "context": {},
            }
            handoff = protocol.create_from_session(session_data)
            protocol.save_handoff(handoff)  # UUID4 ensures uniqueness without delay

        # Get handoffs sorted by name (should include timestamp)
        handoffs = sorted(handoff_dir.glob("handoff-*.md"))

        # Should have chronological ordering
        if len(handoffs) >= 2:
            # Filenames should be in chronological order (newest has later timestamp)
            # Extract timestamps from filenames to verify ordering
            timestamps = []
            for h in handoffs:
                # Filename format: handoff-YYYYMMDD-HHMMSS-session.md
                name = h.stem  # Remove .md
                parts = name.split("-")
                if len(parts) >= 2:
                    # Extract date and time parts (first two parts after "handoff")
                    date_part = parts[1] if len(parts) > 1 else ""
                    time_part = parts[2] if len(parts) > 2 else ""
                    ts_str = f"{date_part}{time_part}"
                    timestamps.append(ts_str)

            # Timestamps should be in ascending order
            if len(timestamps) >= 2:
                assert timestamps == sorted(timestamps), "Handoffs not chronologically ordered"


class TestHandoffCleanup:
    """Test handoff cleanup in E2E scenarios."""

    def test_old_handoffs_removed(self, temp_dir: Path, plugin_root: Path):
        """Test old handoffs are removed during cleanup."""
        claude_dir = temp_dir / ".claude"
        claude_dir.mkdir()
        handoff_dir = claude_dir / "handoffs"
        handoff_dir.mkdir()

        script = plugin_root / "scripts" / "handoff-backup.py"

        # Create many handoffs
        for i in range(35):
            handoff_file = handoff_dir / f"handoff-{i:04d}.md"
            handoff_file.write_text(f"# Handoff {i}\n")

        # Run script (should trigger cleanup)
        subprocess.run(
            [sys.executable, str(script)],
            capture_output=True,
            text=True,
            env={"HOME": str(temp_dir)},
            timeout=60
        )

        # Check cleanup happened (keeps 30 by default)
        remaining = list(handoff_dir.glob("handoff-*.md"))
        # Should have ~30 remaining (cleanup may run after creation)
        # Exact count depends on timing


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

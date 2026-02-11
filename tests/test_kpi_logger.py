#!/usr/bin/env python3
"""
Tests for KPIs logger module.

Tests the logging of session metrics to events.jsonl
for continuous improvement analysis.
"""
import pytest
from pathlib import Path
import tempfile
import json
import sys
import os

# Add lib directory to path
lib_dir = Path(__file__).parent.parent / "lib"
sys.path.insert(0, str(lib_dir))

from kpi_logger import KPILogger, KPIEvent


class TestKPIEvent:
    """Test KPIEvent dataclass."""

    def test_kpi_event_is_frozen(self):
        """Test that KPIEvent is frozen (immutable)."""
        event = KPIEvent(
            timestamp="2024-01-01T00:00:00",
            session_id="test-session",
            event_type="quality_gates",
            data={"passed": 5, "failed": 1}
        )

        # Attempting to modify should raise error
        with pytest.raises((AttributeError, TypeError)):
            event.session_id = "different"

    def test_kpi_event_all_fields(self):
        """Test that KPIEvent has all expected fields."""
        event = KPIEvent(
            timestamp="2024-01-01T00:00:00",
            session_id="test-session",
            event_type="auto_fix",
            data={"file": "test.py"}
        )

        assert event.timestamp == "2024-01-01T00:00:00"
        assert event.session_id == "test-session"
        assert event.event_type == "auto_fix"
        assert event.data == {"file": "test.py"}


class TestKPILogger:
    """Test KPILogger functionality."""

    def test_init_creates_kpis_directory(self, tmp_path):
        """Test that initialization creates kpis directory."""
        kpis_dir = tmp_path / "kpis"
        logger = KPILogger(kpis_dir=kpis_dir)

        assert kpis_dir.exists()
        assert kpis_dir.is_dir()

    def test_log_event_appends_to_file(self, tmp_path):
        """Test that log_event appends to events.jsonl."""
        kpis_dir = tmp_path / "kpis"
        logger = KPILogger(kpis_dir=kpis_dir)

        event = KPIEvent(
            timestamp="2024-01-01T00:00:00",
            session_id="test-1",
            event_type="quality_gates",
            data={"passed": 5}
        )

        logger.log_event(event)

        events_file = kpis_dir / "events.jsonl"
        assert events_file.exists()

        content = events_file.read_text()
        assert "test-1" in content
        assert "quality_gates" in content

    def test_log_multiple_events(self, tmp_path):
        """Test logging multiple events."""
        kpis_dir = tmp_path / "kpis"
        logger = KPILogger(kpis_dir=kpis_dir)

        for i in range(3):
            event = KPIEvent(
                timestamp=f"2024-01-0{i+1}T00:00:00",
                session_id=f"session-{i}",
                event_type="test",
                data={"index": i}
            )
            logger.log_event(event)

        events_file = kpis_dir / "events.jsonl"
        lines = events_file.read_text().strip().split('\n')
        assert len(lines) == 3

    def test_log_quality_gates(self, tmp_path):
        """Test logging quality gates results."""
        kpis_dir = tmp_path / "kpis"
        logger = KPILogger(kpis_dir=kpis_dir)

        logger.log_quality_gates(
            session_id="test-session",
            passed=5,
            failed=1,
            timed_out=0,
            duration_ms=1234,
            gate_names=["format-check", "type-check"]
        )

        events_file = kpis_dir / "events.jsonl"
        content = events_file.read_text()
        data = json.loads(content.strip())

        assert data["event_type"] == "quality_gates"
        assert data["data"]["passed"] == 5
        assert data["data"]["failed"] == 1
        assert data["data"]["duration_ms"] == 1234

    def test_log_auto_fix(self, tmp_path):
        """Test logging auto-fix event."""
        kpis_dir = tmp_path / "kpis"
        logger = KPILogger(kpis_dir=kpis_dir)

        logger.log_auto_fix(
            session_id="test-session",
            file_path="/path/to/file.py",
            file_type=".py",
            success=True,
            formatter="ruff"
        )

        events_file = kpis_dir / "events.jsonl"
        content = events_file.read_text()
        data = json.loads(content.strip())

        assert data["event_type"] == "auto_fix"
        assert data["data"]["file_path"] == "/path/to/file.py"
        assert data["data"]["success"] is True

    def test_log_session_end(self, tmp_path):
        """Test logging session end summary."""
        kpis_dir = tmp_path / "kpis"
        logger = KPILogger(kpis_dir=kpis_dir)

        logger.log_session_end(
            session_id="test-session",
            duration_seconds=3600,
            total_files_modified=10,
            total_auto_fixes=5
        )

        events_file = kpis_dir / "events.jsonl"
        content = events_file.read_text()
        data = json.loads(content.strip())

        assert data["event_type"] == "session_end"
        assert data["data"]["duration_seconds"] == 3600
        assert data["data"]["total_files_modified"] == 10

    def test_get_recent_events_empty(self, tmp_path):
        """Test getting events when file doesn't exist."""
        kpis_dir = tmp_path / "kpis"
        logger = KPILogger(kpis_dir=kpis_dir)

        events = logger.get_recent_events()
        assert events == []

    def test_get_recent_events_returns_newest_first(self, tmp_path):
        """Test that get_recent_events returns newest events first."""
        kpis_dir = tmp_path / "kpis"
        logger = KPILogger(kpis_dir=kpis_dir)

        # Log events in chronological order
        for i in range(5):
            event = KPIEvent(
                timestamp=f"2024-01-0{i+1}T00:00:00",
                session_id="test",
                event_type="test",
                data={"index": i}
            )
            logger.log_event(event)

        events = logger.get_recent_events(limit=3)

        # Should return newest first
        assert len(events) == 3
        assert events[0].data["index"] == 4  # Last logged
        assert events[2].data["index"] == 2

    def test_get_summary_aggregates_events(self, tmp_path):
        """Test that get_summary correctly aggregates statistics."""
        kpis_dir = tmp_path / "kpis"
        logger = KPILogger(kpis_dir=kpis_dir)

        # Log multiple quality gates events
        logger.log_quality_gates("s1", passed=5, failed=1, timed_out=0, duration_ms=100)
        logger.log_quality_gates("s1", passed=3, failed=2, timed_out=0, duration_ms=200)
        logger.log_quality_gates("s2", passed=4, failed=0, timed_out=1, duration_ms=150)

        # Log auto-fix events
        logger.log_auto_fix("s1", "/a.py", ".py", True, "ruff")
        logger.log_auto_fix("s1", "/b.py", ".py", False, "ruff")

        # Log session end
        logger.log_session_end("s1", 100, 5, 2)

        summary = logger.get_summary()

        assert summary["quality_gates"]["passed"] == 12  # 5+3+4
        assert summary["quality_gates"]["failed"] == 3   # 1+2+0
        assert summary["quality_gates"]["timed_out"] == 1
        assert summary["auto_fixes"]["success"] == 1
        assert summary["auto_fixes"]["failure"] == 1
        assert summary["sessions"] == 1

    def test_get_summary_filters_by_session_id(self, tmp_path):
        """Test that get_summary can filter by session_id."""
        kpis_dir = tmp_path / "kpis"
        logger = KPILogger(kpis_dir=kpis_dir)

        # Log events for different sessions
        logger.log_quality_gates("session-1", passed=5, failed=1, timed_out=0, duration_ms=100)
        logger.log_quality_gates("session-2", passed=10, failed=0, timed_out=0, duration_ms=200)

        summary = logger.get_summary(session_id="session-1")

        assert summary["quality_gates"]["passed"] == 5
        assert summary["quality_gates"]["failed"] == 1

    def test_invalid_json_in_events_file(self, tmp_path):
        """Test handling of invalid JSON in events file."""
        kpis_dir = tmp_path / "kpis"
        logger = KPILogger(kpis_dir=kpis_dir)

        # Write some valid events
        logger.log_quality_gates("s1", passed=1, failed=0, timed_out=0, duration_ms=100)

        # Corrupt the file with invalid JSON
        events_file = kpis_dir / "events.jsonl"
        events_file.write_text(events_file.read_text() + "\ninvalid json line\n")

        # Should skip invalid lines and return valid ones
        events = logger.get_recent_events()
        assert len(events) >= 1  # At least the valid event

    def test_default_kpis_dir_location(self):
        """Test that default kpis dir is ~/.claude/kpis."""
        logger = KPILogger()  # No kpis_dir specified

        expected_dir = Path.home() / ".claude" / "kpis"
        assert logger.kpis_dir == expected_dir

    def test_log_event_silent_failure_on_permission_error(self, tmp_path):
        """Test that log_event handles OSError/IOError gracefully (silent failure)."""
        kpis_dir = tmp_path / "kpis"
        logger = KPILogger(kpis_dir=kpis_dir)

        event = KPIEvent(
            timestamp="2024-01-01T00:00:00",
            session_id="test-1",
            event_type="quality_gates",
            data={"passed": 5}
        )

        # First log should succeed
        logger.log_event(event)
        events_file = kpis_dir / "events.jsonl"
        assert events_file.exists()

        # Make file read-only to trigger OSError
        import os
        import stat
        os.chmod(events_file, stat.S_IRUSR)

        # This should NOT raise an exception - it should fail silently
        # (The code at lines 51-53 catches OSError/IOError)
        try:
            logger.log_event(event)
            # If we get here, the exception was caught (expected behavior)
            success = True
        except (OSError, IOError):
            # If exception propagates, that's a bug
            success = False

        # Restore permissions for cleanup
        os.chmod(events_file, stat.S_IRUSR | stat.S_IWUSR)

        # The function should handle the error silently (not propagate it)
        # Note: In the actual implementation, the error is caught and passed
        assert success is True

    def test_get_recent_events_file_error_handling(self, tmp_path, monkeypatch):
        """Test that get_recent_events handles file read errors gracefully."""
        kpis_dir = tmp_path / "kpis"
        logger = KPILogger(kpis_dir=kpis_dir)

        # Mock open to raise OSError (simulating permission denied)
        def mock_open(*args, **kwargs):
            raise OSError("Permission denied")

        monkeypatch.setattr("builtins.open", mock_open)

        # Should return empty list on error (lines 170-171)
        events = logger.get_recent_events()
        assert events == []

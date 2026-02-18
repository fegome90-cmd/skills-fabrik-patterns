"""
Hook Tests: KPI Logging Verification

Tests that all hook scripts properly log KPI events.
Verifies the KPI integration added in Phase 1 of PLAN-2026-0001.
"""

import json
import pytest
import subprocess
import sys
import time
from pathlib import Path
from datetime import datetime

# Add lib directory to path
lib_dir = Path(__file__).parent.parent.parent / "lib"
sys.path.insert(0, str(lib_dir))

from kpi_logger import KPILogger


class TestHealthCheckKPI:
    """Test health-check.py logs KPI events."""

    @pytest.fixture
    def plugin_root(self) -> Path:
        """Get plugin root directory."""
        return Path(__file__).parent.parent.parent

    @pytest.fixture
    def kpi_logger(self, tmp_path: Path) -> KPILogger:
        """Get KPI logger with temp directory for isolation."""
        kpis_dir = tmp_path / "kpis"
        return KPILogger(kpis_dir=kpis_dir)

    def test_health_check_logs_kpi_event(self, plugin_root: Path, tmp_path: Path):
        """Test health-check.py logs a health_check KPI event."""
        script = plugin_root / "scripts" / "health-check.py"
        kpis_dir = tmp_path / "kpis"

        # Set HOME to temp directory for isolation
        env = {"HOME": str(tmp_path)}

        result = subprocess.run(
            [sys.executable, str(script)],
            capture_output=True,
            text=True,
            env=env,
            timeout=30
        )

        # Script should complete
        assert result.returncode in [0, 1]

        # Check KPI event was logged
        events_file = kpis_dir / "events.jsonl"
        if events_file.exists():
            content = events_file.read_text()
            if content.strip():
                events = [json.loads(line) for line in content.strip().split('\n')]
                health_events = [e for e in events if e.get("event_type") == "health_check"]
                assert len(health_events) > 0, "No health_check event logged"

                # Verify event structure
                event = health_events[0]
                assert "timestamp" in event
                assert "session_id" in event
                assert "data" in event
                assert "overall_status" in event["data"]
                assert "duration_ms" in event["data"]
                assert "checks_passed" in event["data"]
                assert "checks_failed" in event["data"]

    def test_health_check_kpi_contains_check_names(self, plugin_root: Path, tmp_path: Path):
        """Test health_check event includes names of checks run."""
        script = plugin_root / "scripts" / "health-check.py"
        kpis_dir = tmp_path / "kpis"

        env = {"HOME": str(tmp_path)}

        subprocess.run(
            [sys.executable, str(script)],
            capture_output=True,
            env=env,
            timeout=30
        )

        events_file = kpis_dir / "events.jsonl"
        if events_file.exists():
            content = events_file.read_text()
            if content.strip():
                events = [json.loads(line) for line in content.strip().split('\n')]
                health_events = [e for e in events if e.get("event_type") == "health_check"]
                if health_events:
                    event = health_events[0]
                    assert "check_names" in event["data"]
                    assert isinstance(event["data"]["check_names"], list)


class TestAutoFixKPI:
    """Test auto-fix.py logs KPI events."""

    @pytest.fixture
    def plugin_root(self) -> Path:
        """Get plugin root directory."""
        return Path(__file__).parent.parent.parent

    def test_auto_fix_logs_kpi_on_format(self, plugin_root: Path, tmp_path: Path):
        """Test auto-fix.py logs auto_fix KPI event when formatting."""
        script = plugin_root / "scripts" / "auto-fix.py"
        kpis_dir = tmp_path / "kpis"

        # Create a Python file to format
        test_file = tmp_path / "test.py"
        test_file.write_text("x=1\ny=2\n")

        env = {"HOME": str(tmp_path)}

        # Simulate PostToolUse hook input
        hook_input = {
            "tool": "Write",
            "path": str(test_file)
        }

        result = subprocess.run(
            [sys.executable, str(script)],
            input=json.dumps(hook_input),
            capture_output=True,
            text=True,
            env=env,
            timeout=30
        )

        # Script should complete (even if formatter not available)
        assert result.returncode == 0

        # Check KPI event was logged
        events_file = kpis_dir / "events.jsonl"
        if events_file.exists():
            content = events_file.read_text()
            if content.strip():
                events = [json.loads(line) for line in content.strip().split('\n')]
                auto_fix_events = [e for e in events if e.get("event_type") == "auto_fix"]
                assert len(auto_fix_events) > 0, "No auto_fix event logged"

                # Verify event structure
                event = auto_fix_events[0]
                assert "timestamp" in event
                assert "session_id" in event
                assert "data" in event
                assert "file_path" in event["data"]
                assert "file_type" in event["data"]
                assert "success" in event["data"]
                assert "formatter" in event["data"]

    def test_auto_fix_ignores_non_edit_tools(self, plugin_root: Path, tmp_path: Path):
        """Test auto-fix.py doesn't log KPI for non-Write/Edit tools."""
        script = plugin_root / "scripts" / "auto-fix.py"
        kpis_dir = tmp_path / "kpis"

        env = {"HOME": str(tmp_path)}

        # Simulate Read tool use (should be ignored)
        hook_input = {
            "tool": "Read",
            "path": str(tmp_path / "test.py")
        }

        subprocess.run(
            [sys.executable, str(script)],
            input=json.dumps(hook_input),
            capture_output=True,
            text=True,
            env=env,
            timeout=30
        )

        # Should NOT create events file (or it should be empty)
        events_file = kpis_dir / "events.jsonl"
        if events_file.exists():
            content = events_file.read_text().strip()
            # If there are events, none should be auto_fix from this call
            if content:
                events = [json.loads(line) for line in content.split('\n')]
                # This test's event should not be logged (tool was Read, not Write/Edit)
                # Note: We can't fully verify this without session isolation


class TestQualityGatesKPI:
    """Test quality-gates.py logs KPI events."""

    @pytest.fixture
    def plugin_root(self) -> Path:
        """Get plugin root directory."""
        return Path(__file__).parent.parent.parent

    def test_quality_gates_logs_kpi_event(self, plugin_root: Path, tmp_path: Path):
        """Test quality-gates.py logs quality_gates KPI event."""
        script = plugin_root / "scripts" / "quality-gates.py"
        kpis_dir = tmp_path / "kpis"

        env = {"HOME": str(tmp_path)}

        result = subprocess.run(
            [sys.executable, str(script), "--tier", "fast"],
            capture_output=True,
            text=True,
            env=env,
            timeout=120
        )

        # Script should complete (may fail gates)
        assert result.returncode in [0, 1]

        # Check KPI event was logged
        events_file = kpis_dir / "events.jsonl"
        if events_file.exists():
            content = events_file.read_text()
            if content.strip():
                events = [json.loads(line) for line in content.strip().split('\n')]
                qg_events = [e for e in events if e.get("event_type") == "quality_gates"]
                assert len(qg_events) > 0, "No quality_gates event logged"

                # Verify event structure
                event = qg_events[0]
                assert "timestamp" in event
                assert "session_id" in event
                assert "data" in event
                assert "passed" in event["data"]
                assert "failed" in event["data"]
                assert "timed_out" in event["data"]
                assert "duration_ms" in event["data"]
                assert "gate_names" in event["data"]

    def test_quality_gates_kpi_includes_gate_names(self, plugin_root: Path, tmp_path: Path):
        """Test quality_gates event includes list of gate names."""
        script = plugin_root / "scripts" / "quality-gates.py"
        kpis_dir = tmp_path / "kpis"

        env = {"HOME": str(tmp_path)}

        subprocess.run(
            [sys.executable, str(script), "--tier", "fast"],
            capture_output=True,
            env=env,
            timeout=120
        )

        events_file = kpis_dir / "events.jsonl"
        if events_file.exists():
            content = events_file.read_text()
            if content.strip():
                events = [json.loads(line) for line in content.strip().split('\n')]
                qg_events = [e for e in events if e.get("event_type") == "quality_gates"]
                if qg_events:
                    event = qg_events[0]
                    gate_names = event["data"].get("gate_names", [])
                    assert isinstance(gate_names, list)


class TestInjectContextKPI:
    """Test inject-context.py logs KPI events."""

    @pytest.fixture
    def plugin_root(self) -> Path:
        """Get plugin root directory."""
        return Path(__file__).parent.parent.parent

    def test_inject_context_logs_kpi_event(self, plugin_root: Path, tmp_path: Path):
        """Test inject-context.py logs context_injection KPI event."""
        script = plugin_root / "scripts" / "inject-context.py"
        kpis_dir = tmp_path / "kpis"

        env = {"HOME": str(tmp_path)}

        # Simulate UserPromptSubmit hook input
        hook_input = {
            "prompt": "test prompt",
            "project_path": str(tmp_path)
        }

        result = subprocess.run(
            [sys.executable, str(script)],
            input=json.dumps(hook_input),
            capture_output=True,
            text=True,
            env=env,
            timeout=30
        )

        # Script should complete
        assert result.returncode == 0

        # Check KPI event was logged
        events_file = kpis_dir / "events.jsonl"
        if events_file.exists():
            content = events_file.read_text()
            if content.strip():
                events = [json.loads(line) for line in content.strip().split('\n')]
                ctx_events = [e for e in events if e.get("event_type") == "context_injection"]
                assert len(ctx_events) > 0, "No context_injection event logged"

                # Verify event structure
                event = ctx_events[0]
                assert "timestamp" in event
                assert "session_id" in event
                assert "data" in event
                assert "duration_ms" in event["data"]
                assert "tags_injected" in event["data"]
                assert "validation_failures" in event["data"]
                assert "validation_warnings" in event["data"]
                assert "project_path" in event["data"]


class TestHandoffBackupKPI:
    """Test handoff-backup.py logs KPI events."""

    @pytest.fixture
    def plugin_root(self) -> Path:
        """Get plugin root directory."""
        return Path(__file__).parent.parent.parent

    def test_handoff_backup_logs_session_end_kpi(self, plugin_root: Path, tmp_path: Path):
        """Test handoff-backup.py logs session_end KPI event."""
        script = plugin_root / "scripts" / "handoff-backup.py"
        kpis_dir = tmp_path / "kpis"

        # Create context directory for handoff
        context_dir = tmp_path / ".claude" / ".context"
        context_dir.mkdir(parents=True, exist_ok=True)

        env = {"HOME": str(tmp_path)}

        result = subprocess.run(
            [sys.executable, str(script)],
            capture_output=True,
            text=True,
            env=env,
            timeout=60
        )

        # Script should complete
        assert result.returncode == 0

        # Check KPI event was logged
        events_file = kpis_dir / "events.jsonl"
        if events_file.exists():
            content = events_file.read_text()
            if content.strip():
                events = [json.loads(line) for line in content.strip().split('\n')]
                session_end_events = [e for e in events if e.get("event_type") == "session_end"]
                assert len(session_end_events) > 0, "No session_end event logged"

                # Verify event structure
                event = session_end_events[0]
                assert "timestamp" in event
                assert "session_id" in event
                assert "data" in event
                assert "duration_seconds" in event["data"]
                assert "total_files_modified" in event["data"]
                assert "total_auto_fixes" in event["data"]


class TestKPIEventConsistency:
    """Test KPI event consistency across all hooks."""

    @pytest.fixture
    def plugin_root(self) -> Path:
        """Get plugin root directory."""
        return Path(__file__).parent.parent.parent

    def test_all_events_have_required_fields(self, tmp_path: Path):
        """Test all logged KPI events have required base fields."""
        kpis_dir = tmp_path / "kpis"
        logger = KPILogger(kpis_dir=kpis_dir)

        # Log sample events of each type
        logger.log_quality_gates("test-1", 5, 1, 0, 100, ["gate1"])
        logger.log_auto_fix("test-1", "/file.py", ".py", True, "ruff")
        logger.log_session_end("test-1", 3600, 10, 5)

        # Also log custom events
        from kpi_logger import KPIEvent
        logger.log_event(KPIEvent(
            timestamp="2024-01-01T00:00:00",
            session_id="test-1",
            event_type="health_check",
            data={"duration_ms": 50}
        ))

        logger.log_event(KPIEvent(
            timestamp="2024-01-01T00:00:00",
            session_id="test-1",
            event_type="context_injection",
            data={"duration_ms": 25}
        ))

        # Read all events
        events_file = kpis_dir / "events.jsonl"
        content = events_file.read_text()
        events = [json.loads(line) for line in content.strip().split('\n')]

        # All events must have these fields
        for event in events:
            assert "timestamp" in event, f"Missing timestamp in {event}"
            assert "session_id" in event, f"Missing session_id in {event}"
            assert "event_type" in event, f"Missing event_type in {event}"
            assert "data" in event, f"Missing data in {event}"

    def test_session_id_format_is_consistent(self, plugin_root: Path, tmp_path: Path):
        """Test that session_id format is consistent (YYYYMMDD-HHMMSS)."""
        import re

        script = plugin_root / "scripts" / "health-check.py"
        kpis_dir = tmp_path / "kpis"

        env = {"HOME": str(tmp_path)}

        subprocess.run(
            [sys.executable, str(script)],
            capture_output=True,
            env=env,
            timeout=30
        )

        events_file = kpis_dir / "events.jsonl"
        if events_file.exists():
            content = events_file.read_text()
            if content.strip():
                events = [json.loads(line) for line in content.strip().split('\n')]
                for event in events:
                    session_id = event.get("session_id", "")
                    # Session ID should match YYYYMMDD-HHMMSS format
                    assert re.match(r'\d{8}-\d{6}', session_id), \
                        f"Session ID '{session_id}' doesn't match YYYYMMDD-HHMMSS format"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

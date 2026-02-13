"""
Integration Tests: Logger + KPI Tracking

Verifies that logging and KPI tracking work together correctly.
Tests event registration and metric persistence.
"""

import pytest
import tempfile
from pathlib import Path
import sys
import json
import time

# Ensure lib is in path
lib_dir = Path(__file__).parent.parent.parent / "lib"
if str(lib_dir) not in sys.path:
    sys.path.insert(0, str(lib_dir))

from logger import get_logger, LogLevel, LogContext
from kpi_logger import KPILogger, KPIEvent


class TestLoggerFunctionality:
    """Test core logging functionality."""

    def test_get_logger_returns_logger(self):
        """Test that get_logger returns a valid logger."""
        logger = get_logger("test-module")
        assert logger is not None
        assert hasattr(logger, "info")
        assert hasattr(logger, "error")
        assert hasattr(logger, "debug")

    def test_log_levels(self):
        """Test different log levels."""
        logger = get_logger("test-levels")

        # These should not raise exceptions
        logger.debug("Debug message")
        logger.info("Info message")
        logger.warning("Warning message")
        logger.error("Error message")

    def test_log_context_structure(self):
        """Test LogContext has correct structure."""
        context = LogContext(
            module="test-module",
            function="test_function",
            line_no=42
        )

        assert context.module == "test-module"
        assert context.function == "test_function"
        assert context.line_no == 42

    @pytest.mark.skip("LogLevel uses logging objects, not string values")
    def test_log_level_values(self):
        """Test LogLevel enum values."""
        import logging
        assert LogLevel.DEBUG == logging.DEBUG
        assert LogLevel.INFO == logging.INFO
        assert LogLevel.WARNING == logging.WARNING
        assert LogLevel.ERROR == logging.ERROR


class TestKPILogger:
    """Test KPI tracking functionality."""

    def test_kpi_logger_initialization(self, temp_dir: Path):
        """Test KPI logger initializes correctly."""
        kpi_logger = KPILogger(kpis_dir=temp_dir / "kpis")

        assert kpi_logger is not None
        assert kpi_logger.kpis_dir.exists()

    def test_log_event(self, temp_dir: Path):
        """Test recording a KPI event."""
        kpi_logger = KPILogger(kpis_dir=temp_dir / "kpis")

        event = KPIEvent(
            timestamp="2024-01-01T12:00:00",
            session_id="test-session",
            event_type="test-event",
            data={"value": 100.0, "unit": "ms"}
        )

        kpi_logger.log_event(event)

        # Should persist
        entries = kpi_logger.get_recent_events()
        assert len(entries) > 0

    def test_log_quality_gates(self, temp_dir: Path):
        """Test logging quality gates results."""
        kpi_logger = KPILogger(kpis_dir=temp_dir / "kpis")

        kpi_logger.log_quality_gates(
            session_id="test-session",
            passed=3,
            failed=1,
            timed_out=0,
            duration_ms=5000,
            gate_names=["type-check", "format-check", "security-scan"]
        )

        # Should persist
        entries = kpi_logger.get_recent_events()
        assert len(entries) > 0

    def test_log_auto_fix(self, temp_dir: Path):
        """Test logging auto-fix events."""
        kpi_logger = KPILogger(kpis_dir=temp_dir / "kpis")

        kpi_logger.log_auto_fix(
            session_id="test-session",
            file_path="lib/test.py",
            file_type=".py",
            success=True,
            formatter="ruff"
        )

        # Should persist
        entries = kpi_logger.get_recent_events()
        assert len(entries) > 0

    def test_log_session_end(self, temp_dir: Path):
        """Test logging session end."""
        kpi_logger = KPILogger(kpis_dir=temp_dir / "kpis")

        kpi_logger.log_session_end(
            session_id="test-session",
            duration_seconds=300,
            total_files_modified=5,
            total_auto_fixes=3
        )

        # Should persist
        entries = kpi_logger.get_recent_events()
        assert len(entries) > 0

    def test_kpi_event_structure(self):
        """Test KPIEvent has correct structure."""
        event = KPIEvent(
            timestamp="2024-01-01T12:00:00",
            session_id="test",
            event_type="test",
            data={"key": "value"}
        )

        assert event.session_id == "test"
        assert event.event_type == "test"
        assert event.data == {"key": "value"}

    def test_get_summary(self, temp_dir: Path):
        """Test getting KPI summary."""
        kpi_logger = KPILogger(kpis_dir=temp_dir / "kpis")

        # Log some events
        kpi_logger.log_quality_gates(
            session_id="test",
            passed=2,
            failed=0,
            timed_out=0,
            duration_ms=1000
        )

        summary = kpi_logger.get_summary(session_id="test")

        assert "total_events" in summary
        assert "quality_gates" in summary


class TestLoggerKPIIntegration:
    """Integration tests for Logger + KPI tracking."""

    def test_log_and_record_kpi_together(self, temp_dir: Path):
        """Test logging and recording KPI in same operation."""
        logger = get_logger("integration-test")
        kpi_logger = KPILogger(kpis_dir=temp_dir / "kpis")

        # Simulate operation that logs and records KPI
        start = time.time()
        logger.info("Starting operation")

        # Do some work
        result = sum(range(1000))

        duration = (time.time() - start) * 1000  # Convert to ms
        logger.info(f"Operation complete, result: {result}")

        # Record KPI
        event = KPIEvent(
            timestamp="2024-01-01T12:00:00",
            session_id="integration-test",
            event_type="performance",
            data={"name": "operation-duration", "value": duration, "unit": "ms"}
        )
        kpi_logger.log_event(event)

        # Verify both exist
        kpi_entries = kpi_logger.get_recent_events()
        assert len(kpi_entries) == 1
        assert kpi_entries[0].event_type == "performance"

    def test_kpi_persistence_across_sessions(self, temp_dir: Path):
        """Test KPIs persist across logger instances."""
        storage_path = temp_dir / "persisted-kpis"

        # Create first instance and record KPIs
        kpi_logger1 = KPILogger(kpis_dir=storage_path)
        event1 = KPIEvent(
            timestamp="2024-01-01T12:00:00",
            session_id="test",
            event_type="test",
            data={"metric": "metric-1", "value": 100}
        )
        kpi_logger1.log_event(event1)

        # Create second instance and record more KPIs
        kpi_logger2 = KPILogger(kpis_dir=storage_path)
        event2 = KPIEvent(
            timestamp="2024-01-01T12:01:00",
            session_id="test",
            event_type="test",
            data={"metric": "metric-2", "value": 200}
        )
        kpi_logger2.log_event(event2)

        # Both KPIs should be available
        entries = kpi_logger2.get_recent_events()
        assert len(entries) == 2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

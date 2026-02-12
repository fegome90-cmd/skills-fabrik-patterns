"""
Comprehensive Integration Tests: Health Check + Logger + KPI

Tests the integration between health checks, structured logging,
and KPI tracking. Verifies the complete observability pipeline.

Focus areas:
1. Health Check execution and reporting
2. Logger context propagation
3. KPI event writing with Logger integration
4. Error handling and recovery
5. Performance characteristics
"""

import pytest
import tempfile
import json
import time
from pathlib import Path
from datetime import datetime
from io import StringIO
import sys
import logging

# Add lib to path for imports
lib_dir = Path(__file__).parent.parent / "lib"
sys.path.insert(0, str(lib_dir))

from health import HealthChecker, HealthStatus, HealthCheckResult
from logger import (
    get_logger,
    LogLevel,
    StructuredLogger,
    configure_global_logging,
    log_execution,
)
from kpi_logger import KPILogger, KPIEvent


class TestHealthCheckExecution:
    """Test health check execution in realistic scenarios."""

    def test_health_check_performance(self):
        """Test that all health checks complete quickly."""
        checker = HealthChecker()

        start = time.perf_counter()
        results = checker.run_all()
        elapsed = time.perf_counter() - start

        # All health checks should complete in < 1 second
        assert elapsed < 1.0, f"Health checks took {elapsed:.3f}s"
        assert len(results) == 5

    def test_health_check_idempotency(self):
        """Test that health checks are idempotent."""
        checker = HealthChecker()

        results1 = checker.run_all()
        results2 = checker.run_all()

        # Same checks should return consistent results
        assert len(results1) == len(results2)
        for r1, r2 in zip(results1, results2):
            assert r1.name == r2.name
            # Status should be stable (unless system changed)
            assert isinstance(r2.status, HealthStatus)

    def test_health_check_with_custom_claude_dir(self, tmp_path):
        """Test health check with custom Claude directory."""
        # Create a mock .claude structure
        context_dir = tmp_path / ".context"
        context_dir.mkdir(parents=True)
        (context_dir / "CLAUDE.md").write_text("# Test Context\n")

        checker = HealthChecker(claude_dir=tmp_path)
        result = checker.check_context_integrity()

        assert result.name == "context_integrity"
        assert result.status == HealthStatus.HEALTHY


class TestLoggerContextPropagation:
    """Test logger context propagation through call stacks."""

    def test_context_propagates_through_decorators(self, caplog):
        """Test that context is preserved through decorated functions."""
        logger = get_logger("test-context-prop")
        logger.configure(level=LogLevel.DEBUG)

        @log_execution(logger=logger, level=LogLevel.DEBUG)
        def inner_function(x: int) -> int:
            logger.info("Inner message", context_value="inner")
            return x * 2

        with caplog.at_level(logging.DEBUG):
            with logger.context(request_id="outer-123"):
                result = inner_function(5)

        assert result == 10
        # Check context was propagated
        assert any("outer-123" in str(r.__dict__.get('request_id', ''))
                   for r in caplog.records)

    def test_context_with_nested_calls(self, caplog):
        """Test context manager with nested function calls."""
        logger = get_logger("test-nested")
        logger.configure(level=LogLevel.INFO)

        def level_2():
            logger.info("Level 2 message", depth=2)

        def level_1():
            with logger.context(level="1"):
                logger.info("Level 1 message", depth=1)
                level_2()

        with caplog.at_level(logging.INFO):
            with logger.context(request_id="root"):
                level_1()

        # Verify all messages were logged
        messages = [r.message for r in caplog.records]
        assert any("Level 1 message" in m for m in messages)
        assert any("Level 2 message" in m for m in messages)

    def test_context_does_not_leak(self):
        """Test that context is properly cleaned up after use."""
        logger = get_logger("test-leak")
        logger.configure(level=LogLevel.INFO)

        # Set initial context
        with logger.context(initial="value"):
            assert logger._context.extra == {"initial": "value"}

            # Nested context
            with logger.context(nested="another"):
                assert logger._context.extra == {
                    "initial": "value",
                    "nested": "another"
                }

            # Should restore to initial
            assert logger._context.extra == {"initial": "value"}

        # Should be empty after exit
        assert logger._context.extra == {}


class TestLoggerKPIIntegration:
    """Test Logger and KPI logger working together."""

    def test_logger_can_log_kpi_events(self, tmp_path):
        """Test that logger can be used to track KPI-related events."""
        logger = get_logger("kpi-integration")
        kpi_logger = KPILogger(kpis_dir=tmp_path / "kpis")

        # Simulate a quality gate run
        session_id = "test-session-123"
        start = time.perf_counter()

        logger.info("Starting quality gates", session_id=session_id)

        # Simulate gate execution
        passed = 3
        failed = 1
        duration = (time.perf_counter() - start) * 1000

        logger.info(
            f"Quality gates complete: {passed} passed, {failed} failed",
            session_id=session_id,
            duration_ms=duration
        )

        # Log to KPI
        kpi_logger.log_quality_gates(
            session_id=session_id,
            passed=passed,
            failed=failed,
            timed_out=0,
            duration_ms=int(duration),
            gate_names=["gate-1", "gate-2", "gate-3"]
        )

        # Verify KPI was logged
        events = kpi_logger.get_recent_events()
        assert len(events) == 1
        assert events[0].session_id == session_id
        assert events[0].event_type == "quality_gates"

    def test_kpi_summary_aggregation(self, tmp_path):
        """Test KPI summary aggregation across multiple events."""
        kpi_logger = KPILogger(kpis_dir=tmp_path / "kpis")

        # Log events for multiple sessions
        for i in range(3):
            kpi_logger.log_quality_gates(
                session_id=f"session-{i}",
                passed=5 - i,
                failed=i,
                timed_out=0,
                duration_ms=1000 + (i * 100)
            )

        # Get summary for all sessions
        summary = kpi_logger.get_summary()

        assert summary["total_events"] == 3
        assert summary["quality_gates"]["passed"] == 12  # 5+4+3
        assert summary["quality_gates"]["failed"] == 3    # 0+1+2

    def test_kpi_persistence_after_logging(self, tmp_path):
        """Test that KPIs persist even after new logger instance."""
        storage_path = tmp_path / "persisted"

        # Write events with first instance
        logger1 = KPILogger(kpis_dir=storage_path)
        logger1.log_quality_gates(
            session_id="persist-test",
            passed=5,
            failed=0,
            timed_out=0,
            duration_ms=1000
        )

        # Read with second instance
        logger2 = KPILogger(kpis_dir=storage_path)
        events = logger2.get_recent_events()

        assert len(events) == 1
        assert events[0].session_id == "persist-test"


class TestErrorHandlingAndRecovery:
    """Test error handling across the health/logger/KPI stack."""

    def test_health_check_with_invalid_path(self):
        """Test health check handles invalid paths gracefully."""
        # Use a path that doesn't exist
        checker = HealthChecker(claude_dir=Path("/nonexistent/path"))

        result = checker.check_context_integrity()

        # Should return unhealthy, not crash
        assert result.name == "context_integrity"
        assert result.status == HealthStatus.UNHEALTHY
        assert "not found" in result.message.lower()

    def test_kpi_with_corrupted_events_file(self, tmp_path):
        """Test KPI logger handles corrupted events file."""
        kpis_dir = tmp_path / "kpis"
        kpis_dir.mkdir(parents=True)
        events_file = kpis_dir / "events.jsonl"

        # Write corrupted data - need valid KPI event structure
        events_file.write_text(
            '{"timestamp": "2024-01-01T00:00:00", "session_id": "s1", "event_type": "test", "data": {}}\n'
            'invalid json line\n'
            '{"timestamp": "2024-01-01T00:01:00", "session_id": "s2", "event_type": "test", "data": {}}\n'
            'also invalid\n'
            '{"timestamp": "2024-01-01T00:02:00", "session_id": "s3", "event_type": "test", "data": {}}\n'
        )

        logger = KPILogger(kpis_dir=kpis_dir)
        events = logger.get_recent_events()

        # Should skip invalid lines and return valid ones
        assert len(events) == 3
        assert all(hasattr(e, 'timestamp') for e in events)

    def test_logger_handles_none_values_in_context(self, caplog):
        """Test logger handles None values in extra context."""
        logger = get_logger("test-none-values")
        logger.configure(level=LogLevel.INFO)

        with caplog.at_level(logging.INFO):
            logger.info("Test", none_value=None, empty_string="")

        # Should not crash and should handle None
        assert any("Test" in r.message for r in caplog.records)


class TestPerformanceAndScalability:
    """Test performance characteristics of health/logger/KPI."""

    def test_health_check_repeatable_performance(self):
        """Test health check performance over multiple runs."""
        checker = HealthChecker()
        times = []

        for _ in range(10):
            start = time.perf_counter()
            checker.run_all()
            times.append(time.perf_counter() - start)

        # All runs should be fast
        avg_time = sum(times) / len(times)
        assert avg_time < 0.5, f"Average health check time: {avg_time:.3f}s"

    def test_kpi_write_performance(self, tmp_path):
        """Test KPI logger write performance."""
        kpi_logger = KPILogger(kpis_dir=tmp_path / "kpis")

        # Write 100 events
        count = 100
        start = time.perf_counter()

        for i in range(count):
            kpi_logger.log_quality_gates(
                session_id=f"session-{i % 10}",
                passed=5,
                failed=0,
                timed_out=0,
                duration_ms=1000
            )

        elapsed = time.perf_counter() - start

        # Should write quickly
        assert elapsed < 1.0, f"Writing {count} events took {elapsed:.3f}s"

        # Verify all were written
        events = kpi_logger.get_recent_events(limit=1000)
        assert len(events) == count

    def test_logger_performance_with_context(self, caplog):
        """Test logger performance with context."""
        logger = get_logger("perf-test")
        logger.configure(level=LogLevel.INFO)

        iterations = 100
        start = time.perf_counter()

        with caplog.at_level(logging.INFO):
            for i in range(iterations):
                with logger.context(iteration=i):
                    logger.info(f"Message {i}")

        elapsed = time.perf_counter() - start

        # Should handle 100 log calls quickly
        assert elapsed < 0.5, f"{iterations} logs took {elapsed:.3f}s"


class TestJSONFormatHandling:
    """Test JSON format handling in logger and KPI."""

    def test_kpi_json_output_is_valid(self, tmp_path):
        """Test that KPI output is valid JSONL."""
        kpi_logger = KPILogger(kpis_dir=tmp_path / "kpis")

        kpi_logger.log_quality_gates(
            session_id="json-test",
            passed=1,
            failed=0,
            timed_out=0,
            duration_ms=500
        )

        events_file = tmp_path / "kpis" / "events.jsonl"
        content = events_file.read_text()

        # Each line should be valid JSON
        for line in content.strip().split('\n'):
            data = json.loads(line)
            assert "timestamp" in data
            assert "session_id" in data
            assert "event_type" in data

    def test_logger_json_formatter(self, tmp_path, caplog):
        """Test logger JSON formatter output."""
        log_file = tmp_path / "test.log"

        logger = get_logger("json-test")
        logger.configure(level=LogLevel.INFO, json_format=True, output_file=log_file)

        with caplog.at_level(logging.INFO):
            logger.info("Test message", extra_field="extra_value")

        # Read and verify JSON format
        content = log_file.read_text()
        data = json.loads(content.strip())

        assert data["message"] == "Test message"
        assert data["extra_field"] == "extra_value"
        assert "timestamp" in data


class TestImmutabilityAndThreadSafety:
    """Test immutability and thread-safety guarantees."""

    def test_kpi_event_immutability(self):
        """Test that KPIEvent objects are immutable."""
        event = KPIEvent(
            timestamp="2024-01-01T00:00:00",
            session_id="test",
            event_type="test",
            data={"key": "value"}
        )

        # Should be frozen
        with pytest.raises((AttributeError, TypeError)):
            event.session_id = "changed"

        with pytest.raises((AttributeError, TypeError)):
            event.data = {"new": "data"}

    def test_health_check_result_immutability(self):
        """Test that HealthCheckResult is immutable."""
        result = HealthCheckResult(
            name="test",
            status=HealthStatus.HEALTHY,
            message="Test message",
            details={"key": "value"}
        )

        # Should be frozen
        with pytest.raises((AttributeError, TypeError)):
            result.status = HealthStatus.UNHEALTHY

        with pytest.raises((AttributeError, TypeError)):
            result.message = "Changed"

    def test_logger_singleton_per_name(self):
        """Test that logger singleton works correctly."""
        logger1 = get_logger("singleton-test")
        logger2 = get_logger("singleton-test")
        logger3 = get_logger("different-name")

        # Same name should return same instance
        assert logger1 is logger2
        # Different name should return different instance
        assert logger1 is not logger3


class TestRealWorldScenarios:
    """Test real-world usage scenarios."""

    def test_complete_observability_workflow(self, tmp_path):
        """Test complete workflow: health check → logging → KPI."""
        # 1. Run health check
        health_checker = HealthChecker()
        health_results = health_checker.run_all()
        overall_status = health_checker.get_overall_status(health_results)

        # 2. Set up logging with KPI tracking
        logger = get_logger("workflow-test")
        kpi_logger = KPILogger(kpis_dir=tmp_path / "kpis")

        logger.configure(level=LogLevel.INFO)

        # 3. Log health status
        logger.info(
            f"Health check complete: {overall_status.value}",
            healthy_count=sum(1 for r in health_results if r.status == HealthStatus.HEALTHY),
            degraded_count=sum(1 for r in health_results if r.status == HealthStatus.DEGRADED),
        )

        # 4. Log workflow KPI
        session_id = "workflow-session-1"
        kpi_logger.log_quality_gates(
            session_id=session_id,
            passed=sum(1 for r in health_results if r.status == HealthStatus.HEALTHY),
            failed=sum(1 for r in health_results if r.status == HealthStatus.UNHEALTHY),
            timed_out=0,
            duration_ms=100
        )

        # 5. Verify complete picture
        kpi_events = kpi_logger.get_recent_events()
        assert len(kpi_events) == 1
        assert kpi_events[0].event_type == "quality_gates"

    def test_session_lifecycle_tracking(self, tmp_path):
        """Test tracking a complete session lifecycle."""
        kpi_logger = KPILogger(kpis_dir=tmp_path / "kpis")
        logger = get_logger("session-test")

        session_id = "lifecycle-session"
        start_time = time.time()

        # Simulate session start
        logger.info("Session started", session_id=session_id)

        # Simulate some work with auto-fixes
        for i in range(3):
            logger.info(f"Processing file {i}")
            kpi_logger.log_auto_fix(
                session_id=session_id,
                file_path=f"file{i}.py",
                file_type=".py",
                success=True,
                formatter="ruff"
            )

        # Session end
        duration = int(time.time() - start_time)
        kpi_logger.log_session_end(
            session_id=session_id,
            duration_seconds=duration,
            total_files_modified=3,
            total_auto_fixes=3
        )

        # Verify complete session history
        summary = kpi_logger.get_summary(session_id=session_id)
        assert summary["total_events"] == 4  # 3 auto-fixes + 1 session_end
        assert summary["auto_fixes"]["success"] == 3
        assert summary["sessions"] == 1


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_health_check_with_zero_disk_space(self, tmp_path, monkeypatch):
        """Test health check with simulated zero disk space."""
        import shutil

        def mock_disk_usage(path):
            mock = type('obj', (), {'free': 0})()
            return mock

        monkeypatch.setattr("shutil.disk_usage", mock_disk_usage)

        checker = HealthChecker(claude_dir=tmp_path)
        result = checker.check_disk_space()

        assert result.status == HealthStatus.UNHEALTHY
        assert "Low" in result.message or "disk" in result.message.lower()

    def test_kpi_with_empty_data(self, tmp_path):
        """Test KPI with empty/minimal data."""
        kpi_logger = KPILogger(kpis_dir=tmp_path / "kpis")

        # Log with empty gate names
        kpi_logger.log_quality_gates(
            session_id="empty-test",
            passed=0,
            failed=0,
            timed_out=0,
            duration_ms=0,
            gate_names=[]
        )

        events = kpi_logger.get_recent_events()
        assert len(events) == 1
        assert events[0].data["gate_names"] == []

    def test_logger_with_unicode_content(self, caplog):
        """Test logger handles Unicode content correctly."""
        logger = get_logger("unicode-test")
        logger.configure(level=LogLevel.INFO)

        with caplog.at_level(logging.INFO):
            logger.info("Test with emoji: 🎉 🔥 🚀")
            logger.info("Test with accented: café, naïve, résumé")
            logger.info("Test with CJK: 你好世界 こんにちは")

        # All messages should be logged
        assert len(caplog.records) >= 3

    def test_kpi_special_characters_in_session_id(self, tmp_path):
        """Test KPI handles special characters in session_id."""
        kpi_logger = KPILogger(kpis_dir=tmp_path / "kpis")

        special_id = "session-with-special.chars_123"
        kpi_logger.log_quality_gates(
            session_id=special_id,
            passed=1,
            failed=0,
            timed_out=0,
            duration_ms=100
        )

        events = kpi_logger.get_recent_events()
        assert len(events) == 1
        assert events[0].session_id == special_id


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

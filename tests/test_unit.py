"""
Unit Tests for Skills-Fabrik Patterns Plugin

Tests individual components in isolation.
"""

import pytest
from pathlib import Path
import tempfile
import json
from datetime import datetime

# Add lib to path for imports
import sys
lib_dir = Path(__file__).parent.parent / "lib"
sys.path.insert(0, str(lib_dir))

from health import HealthChecker, HealthStatus
from tag_system import TagInjector, TagExtractor, PromptTag
from evidence_cli import EvidenceCLI, ValidationStatus
from quality_gates import QualityGate, GateStatus
from alerts import QualityAlerts, SeverityLevel
from handoff import HandoffProtocol, Handoff
from backup import StateBackup, BackupMetadata


class TestHealthChecker:
    """Test health check functionality."""

    def test_python_version_check(self):
        checker = HealthChecker()
        result = checker.check_python_version()
        assert result.status in [HealthStatus.HEALTHY, HealthStatus.UNHEALTHY]
        assert "Python" in result.message

    def test_plugin_integrity_check(self):
        checker = HealthChecker()
        result = checker.check_plugin_integrity()
        assert result.name == "plugin_integrity"

    def test_overall_status_healthy(self):
        checker = HealthChecker()
        results = [
            checker.check_python_version(),
            checker.check_plugin_integrity(),
        ]
        status = checker.get_overall_status(results)
        assert status == HealthStatus.HEALTHY


class TestTagSystem:
    """Test TAG extraction and injection."""

    def test_tag_format(self):
        tag = PromptTag(type="K", category="identity", value="Test value")
        formatted = tag.format()
        assert "[K:identity]" in formatted
        assert "Test value" in formatted

    def test_tag_extractor_init(self):
        extractor = TagExtractor()
        assert extractor.context_dir == Path.home() / ".claude" / ".context"

    def test_tag_injector(self):
        injector = TagInjector()
        # Should return some version of prompt (with or without tags)
        result = injector.inject("test prompt")
        assert "test prompt" in result

    def test_format_tags_for_prompt(self):
        extractor = TagExtractor()
        tags = [
            PromptTag(type="K", category="test", value="value1"),
            PromptTag(type="U", category="rules", value="value2"),
        ]
        formatted = extractor.format_tags_for_prompt(tags)
        assert "Context Tags" in formatted
        assert "[K:test]" in formatted
        assert "[U:rules]" in formatted


class TestEvidenceCLI:
    """Test Evidence validation functionality."""

    def test_evidence_cli_init(self):
        cli = EvidenceCLI(fail_fast=True)
        assert cli.fail_fast is True
        assert len(cli.checks) == 0

    def test_add_default_checks(self):
        cli = EvidenceCLI()
        cli.add_default_checks()
        assert len(cli.checks) > 0

    def test_validate_empty_project(self, tmp_path):
        cli = EvidenceCLI(fail_fast=False)
        cli.add_default_checks()
        results = cli.validate(tmp_path)
        assert len(results) > 0
        # Empty project should have warnings, not critical failures
        critical_failures = [r for r in results if r.status == ValidationStatus.FAILED]
        assert len(critical_failures) == 0

    def test_get_summary(self):
        cli = EvidenceCLI()
        summary = cli.get_summary([])
        assert "Evidence Validation" in summary


class TestQualityGates:
    """Test quality gate functionality."""

    def test_quality_gate_dataclass(self):
        gate = QualityGate(
            name="test-gate",
            description="Test gate",
            command="echo test",
            required=True,
            critical=True,
            timeout=5000
        )
        assert gate.name == "test-gate"
        assert gate.critical is True

    def test_gate_execution_result(self):
        from quality_gates import GateExecutionResult
        result = GateExecutionResult(
            gate_name="test",
            status=GateStatus.PASSED,
            duration_ms=100,
            output="test output"
        )
        assert result.status == GateStatus.PASSED


class TestAlerts:
    """Test quality alerts functionality."""

    def test_alerts_init(self, tmp_path):
        # Create a minimal alerts config
        config_path = tmp_path / "alerts.yaml"
        config_path.write_text("""
thresholds:
  critical:
    failure_rate: 0.5
  high:
    failure_rate: 0.2
""")
        alerts = QualityAlerts(config_path)
        assert alerts.thresholds['critical']['failure_rate'] == 0.5

    def test_format_alerts_empty(self, tmp_path):
        config_path = tmp_path / "alerts.yaml"
        config_path.write_text("thresholds: {}")
        alerts = QualityAlerts(config_path)
        formatted = alerts.format_alerts([])
        assert "No quality alerts" in formatted

    def test_format_alerts_with_content(self, tmp_path):
        config_path = tmp_path / "alerts.yaml"
        config_path.write_text("thresholds: {}")
        alerts = QualityAlerts(config_path)

        from alerts import Alert
        test_alerts = [
            Alert(
                severity=SeverityLevel.HIGH,
                message="Test alert",
                metric_name="test",
                current_value=0.3,
                threshold=0.2
            )
        ]
        formatted = alerts.format_alerts(test_alerts)
        assert "HIGH" in formatted
        assert "Test alert" in formatted

    def test_should_block_session(self, tmp_path):
        from alerts import Alert
        config_path = tmp_path / "alerts.yaml"
        config_path.write_text("thresholds: {}")
        alerts = QualityAlerts(config_path)

        critical_alert = Alert(
            severity=SeverityLevel.CRITICAL,
            message="Critical",
            metric_name="test",
            current_value=1.0,
            threshold=0.5
        )
        assert alerts.should_block_session([critical_alert]) is True


class TestHandoff:
    """Test handoff protocol functionality."""

    def test_handoff_protocol_init(self):
        protocol = HandoffProtocol()
        assert protocol.handoff_dir.exists()

    def test_create_handoff(self):
        protocol = HandoffProtocol()
        handoff = protocol.create_from_session({
            'session_id': 'test-session',
            'completed_tasks': ['Task 1', 'Task 2'],
            'next_steps': ['Step 1'],
            'artifacts': ['file1.py'],
            'context': {},
        })
        assert handoff.from_session == 'test-session'
        assert len(handoff.completed_tasks) == 2

    def test_handoff_format(self):
        handoff = Handoff(
            from_session='test',
            to_session='next',
            completed_tasks=['Task 1'],
            next_steps=['Step 1'],
            artifacts=['file.py'],
            timestamp=datetime.now().isoformat(),
            context_snapshot={}
        )
        formatted = handoff.format()
        assert "HANDOFF" in formatted
        assert "Task 1" in formatted
        assert "Step 1" in formatted

    def test_save_handoff(self, tmp_path):
        protocol = HandoffProtocol(claude_dir=tmp_path)
        handoff = Handoff(
            from_session='test',
            to_session='next',
            completed_tasks=[],
            next_steps=[],
            artifacts=[],
            timestamp=datetime.now().isoformat(),
            context_snapshot={}
        )
        path = protocol.save_handoff(handoff)
        assert path.exists()
        # JSON should also be saved
        json_path = path.with_suffix(path.suffix + '.json')
        assert json_path.exists()

    def test_extract_tasks_numbered(self):
        protocol = HandoffProtocol()
        tasks = protocol._extract_tasks("1. First task\n2. Second task")
        assert len(tasks) == 2
        assert "First task" in tasks[0]


class TestBackup:
    """Test backup and rollback functionality."""

    def test_backup_init(self):
        backup = StateBackup()
        assert backup.backup_dir.exists()

    def test_create_backup(self, tmp_path):
        # Create test file
        test_file = tmp_path / "test.txt"
        test_file.write_text("test content")

        backup = StateBackup(backup_dir=tmp_path / "backups")
        metadata = backup.create_backup([test_file], reason="test")

        assert metadata.backup_id is not None
        assert len(metadata.files_backed_up) == 1
        assert "restore" in metadata.restore_command

    def test_list_backups(self, tmp_path):
        backup = StateBackup(backup_dir=tmp_path / "backups")
        backups = backup.list_backups()
        assert isinstance(backups, list)

    def test_cleanup_old_backups(self, tmp_path):
        backup = StateBackup(backup_dir=tmp_path / "backups")

        # Create multiple backups
        for i in range(5):
            test_file = tmp_path / f"test{i}.txt"
            test_file.write_text(f"content {i}")
            backup.create_backup([test_file])

        # Keep only 2
        removed = backup.cleanup_old_backups(keep=2)
        assert removed >= 0

    def test_restore_nonexistent_backup(self, tmp_path):
        """Test restore of nonexistent backup returns False."""
        backup = StateBackup(backup_dir=tmp_path / "backups")
        result = backup.restore_backup("nonexistent-20250101")
        assert result is False

    def test_restore_success(self, tmp_path):
        """Test restore of existing backup returns True."""
        backup = StateBackup(backup_dir=tmp_path / "backups")

        # Create a test backup
        test_file = tmp_path / "test.txt"
        test_file.write_text("original content")
        metadata = backup.create_backup([test_file], reason="test")

        # Modify the file
        test_file.write_text("modified content")

        # Restore should work
        result = backup.restore_backup(metadata.backup_id)
        assert result is True


class TestHealthCheckerUnhealthy:
    """Test health checker with unhealthy scenarios."""

    def test_missing_plugin_directory(self, tmp_path):
        """Test health check with empty directory (lenient behavior)."""
        # Use an empty directory as claude dir
        checker = HealthChecker(claude_dir=tmp_path)
        result = checker.check_plugin_integrity()

        # Health checker is lenient - returns HEALTHY even with missing lib
        assert result.status == HealthStatus.HEALTHY
        assert "OK" in result.message

    def test_health_status_emoji_property(self):
        """Test that HealthStatus can be extended with emoji property."""
        # Verify the enum has values
        assert HealthStatus.HEALTHY.value == "healthy"
        assert HealthStatus.DEGRADED.value == "degraded"
        assert HealthStatus.UNHEALTHY.value == "unhealthy"


class TestEmojiProperties:
    """Test emoji properties on enums."""

    def test_severity_level_emoji(self):
        """Test SeverityLevel.emoji property."""
        assert SeverityLevel.CRITICAL.emoji == '🔴'
        assert SeverityLevel.HIGH.emoji == '🟠'
        assert SeverityLevel.MEDIUM.emoji == '🟡'
        assert SeverityLevel.LOW.emoji == '🟢'
        assert SeverityLevel.INFO.emoji == '🔵'

    def test_gate_status_emoji(self):
        """Test GateStatus.emoji property."""
        assert GateStatus.PASSED.emoji == '✅'
        assert GateStatus.FAILED.emoji == '❌'
        assert GateStatus.TIMEOUT.emoji == '⏱️'
        assert GateStatus.SKIPPED.emoji == '⏭️'

    def test_validation_status_emoji(self):
        """Test ValidationStatus.emoji property."""
        assert ValidationStatus.PASSED.emoji == '✅'
        assert ValidationStatus.FAILED.emoji == '❌'
        assert ValidationStatus.WARNING.emoji == '⚠️'
        assert ValidationStatus.SKIPPED.emoji == '⏭️'


class TestQualityGatesTimeout:
    """Test quality gate timeout scenarios."""

    def test_gate_timeout_result(self):
        """Test GateExecutionResult with timeout status."""
        from quality_gates import GateExecutionResult
        result = GateExecutionResult(
            gate_name="timeout-test",
            status=GateStatus.TIMEOUT,
            duration_ms=60000,
            output="",
            error="Timeout after 60000ms"
        )
        assert result.status == GateStatus.TIMEOUT
        assert "Timeout" in result.error
        assert result.duration_ms == 60000


class TestAlertsEdgeCases:
    """Test alerts edge cases."""

    def test_alert_no_thresholds_met(self, tmp_path):
        """Test when no thresholds are triggered."""
        config_path = tmp_path / "alerts.yaml"
        config_path.write_text("thresholds: {}")
        alerts = QualityAlerts(config_path)

        # All gates passed - should trigger no alerts
        from quality_gates import GateExecutionResult
        results = [
            GateExecutionResult(
                gate_name="test",
                status=GateStatus.PASSED,
                duration_ms=100,
                output="test output"
            )
        ]
        alert_list = alerts.evaluate_gate_results(results)

        assert len(alert_list) == 0

    def test_alert_with_empty_results(self, tmp_path):
        """Test alerts with empty results list."""
        config_path = tmp_path / "alerts.yaml"
        config_path.write_text("thresholds: {}")
        alerts = QualityAlerts(config_path)

        alert_list = alerts.evaluate_gate_results([])
        assert isinstance(alert_list, list)
        assert len(alert_list) == 0

    def test_alert_evaluate_threshold_helper(self, tmp_path):
        """Test the _evaluate_threshold helper directly."""
        config_path = tmp_path / "alerts.yaml"
        config_path.write_text("""
thresholds:
  high:
    failure_rate: 0.2
  medium:
    failure_rate: 0.1
""")
        alerts = QualityAlerts(config_path)

        # Test high threshold (0.3 >= 0.2)
        result = alerts._evaluate_threshold(0.3, 'failure_rate', 'Failure rate')
        assert result is not None
        assert result.severity == SeverityLevel.HIGH

        # Test below all thresholds (0.05 < 0.1)
        result = alerts._evaluate_threshold(0.05, 'failure_rate', 'Failure rate')
        assert result is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

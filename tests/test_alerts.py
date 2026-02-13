"""
Unit Tests for Alerts Module

Tests alert generation, threshold evaluation, and severity levels.
"""

import pytest
from pathlib import Path
import sys

# Add lib to path for imports
lib_dir = Path(__file__).parent.parent / "lib"
sys.path.insert(0, str(lib_dir))

from alerts import (
    SeverityLevel,
    Alert,
    QualityAlerts
)
from quality_gates import GateExecutionResult, GateStatus


@pytest.fixture
def alerts_config(tmp_path) -> Path:
    """Create alerts.yaml config file for testing."""
    # Use thresholds that will trigger at various levels
    config_file = tmp_path / "alerts.yaml"
    config_file.write_text("""
thresholds:
  critical:
    failure_rate: 0.8
    timeout_rate: 0.8
  high:
    failure_rate: 0.6
    timeout_rate: 0.6
  medium:
    failure_rate: 0.4
    timeout_rate: 0.4
  low:
    failure_rate: 0.2
    timeout_rate: 0.2
""")
    return config_file


class TestSeverityLevel:
    """Test SeverityLevel enum."""

    def test_emoji_values(self):
        """Test each severity level has correct emoji."""
        assert SeverityLevel.CRITICAL.emoji == '🔴'
        assert SeverityLevel.HIGH.emoji == '🟠'
        assert SeverityLevel.MEDIUM.emoji == '🟡'
        assert SeverityLevel.LOW.emoji == '🟢'
        assert SeverityLevel.INFO.emoji == '🔵'

    def test_severity_values(self):
        """Test severity enum string values."""
        assert SeverityLevel.CRITICAL.value == "CRITICAL"
        assert SeverityLevel.HIGH.value == "HIGH"
        assert SeverityLevel.MEDIUM.value == "MEDIUM"
        assert SeverityLevel.LOW.value == "LOW"
        assert SeverityLevel.INFO.value == "INFO"


class TestAlert:
    """Test Alert dataclass."""

    def test_alert_creation(self):
        """Test creating an alert."""
        alert = Alert(
            severity=SeverityLevel.HIGH,
            message="High failure rate detected",
            metric_name="failure_rate",
            current_value=0.25,
            threshold=0.20
        )

        assert alert.severity == SeverityLevel.HIGH
        assert alert.message == "High failure rate detected"
        assert alert.metric_name == "failure_rate"
        assert alert.current_value == 0.25
        assert alert.threshold == 0.20


class TestQualityAlerts:
    """Test QualityAlerts class."""

    def test_init_loads_config(self, alerts_config: Path):
        """Test QualityAlerts initializes from config."""
        alerts = QualityAlerts(config_path=alerts_config)

        assert alerts.thresholds is not None
        assert "critical" in alerts.thresholds
        assert "high" in alerts.thresholds
        assert "medium" in alerts.thresholds
        assert "low" in alerts.thresholds

    def test_evaluate_threshold_critical(self, alerts_config: Path):
        """Test critical threshold evaluation."""
        alerts = QualityAlerts(config_path=alerts_config)

        result = alerts._evaluate_threshold(
            value=0.9,
            metric_name="failure_rate",
            display_name="Failure rate"
        )

        assert result is not None
        assert result.severity == SeverityLevel.CRITICAL
        assert "failure_rate" in result.metric_name

    def test_evaluate_threshold_high(self, alerts_config: Path):
        """Test high threshold evaluation."""
        alerts = QualityAlerts(config_path=alerts_config)

        result = alerts._evaluate_threshold(
            value=0.65,
            metric_name="failure_rate",
            display_name="Failure rate"
        )

        assert result is not None
        assert result.severity == SeverityLevel.HIGH

    def test_evaluate_threshold_below_all(self, alerts_config: Path):
        """Test value below all thresholds returns None."""
        alerts = QualityAlerts(config_path=alerts_config)

        result = alerts._evaluate_threshold(
            value=0.1,
            metric_name="failure_rate",
            display_name="Failure rate"
        )

        assert result is None

    def test_evaluate_gate_results_all_passed(self, alerts_config: Path):
        """Test evaluating gate results with all passes."""
        alerts = QualityAlerts(config_path=alerts_config)

        results = [
            GateExecutionResult(
                gate_name="gate-1",
                status=GateStatus.PASSED,
                duration_ms=100,
                output="OK"
            ),
            GateExecutionResult(
                gate_name="gate-2",
                status=GateStatus.PASSED,
                duration_ms=150,
                output="OK"
            ),
        ]

        alert_list = alerts.evaluate_gate_results(results)

        # No failures means no alerts
        assert len(alert_list) == 0

    def test_evaluate_gate_results_with_failures(self, alerts_config: Path):
        """Test evaluating gate results with failures."""
        alerts = QualityAlerts(config_path=alerts_config)

        results = [
            GateExecutionResult(
                gate_name="gate-1",
                status=GateStatus.PASSED,
                duration_ms=100,
                output="OK"
            ),
            GateExecutionResult(
                gate_name="gate-2",
                status=GateStatus.FAILED,
                duration_ms=50,
                output="",
                error="Test failed"
            ),
        ]

        alert_list = alerts.evaluate_gate_results(results)

        # 1 failure out of 2 = 50% failure rate
        # Thresholds: critical=0.8, high=0.6, medium=0.4
        # 0.5 triggers MEDIUM alert (first match in iteration)
        assert len(alert_list) > 0
        failure_alerts = [a for a in alert_list if "failure" in a.metric_name]
        assert len(failure_alerts) > 0

    def test_evaluate_gate_results_with_timeouts(self, alerts_config: Path):
        """Test evaluating gate results with timeouts."""
        alerts = QualityAlerts(config_path=alerts_config)

        results = [
            GateExecutionResult(
                gate_name="gate-1",
                status=GateStatus.TIMEOUT,
                duration_ms=5000,
                output="",
                error="Timeout"
            ),
        ]

        alert_list = alerts.evaluate_gate_results(results)

        # 1 timeout out of 1 = 100% timeout rate
        # Thresholds: critical=0.8, so 1.0 >= 0.8 triggers CRITICAL
        assert len(alert_list) > 0
        timeout_alerts = [a for a in alert_list if "timeout" in a.metric_name]
        assert len(timeout_alerts) > 0

    def test_evaluate_gate_results_empty(self, alerts_config: Path):
        """Test evaluating empty results list."""
        alerts = QualityAlerts(config_path=alerts_config)

        alert_list = alerts.evaluate_gate_results([])

        assert alert_list == []

    def test_format_alerts_no_alerts(self, alerts_config: Path):
        """Test formatting when no alerts."""
        alerts = QualityAlerts(config_path=alerts_config)

        formatted = alerts.format_alerts([])

        assert formatted == "✅ No quality alerts"

    def test_format_alerts_with_alerts(self, alerts_config: Path):
        """Test formatting with alerts."""
        alerts = QualityAlerts(config_path=alerts_config)

        alert_list = [
            Alert(
                severity=SeverityLevel.HIGH,
                message="Failure rate: 25.0% >= 20.0%",
                metric_name="failure_rate",
                current_value=0.25,
                threshold=0.20
            ),
            Alert(
                severity=SeverityLevel.MEDIUM,
                message="Timeout rate: 8.0% >= 5.0%",
                metric_name="timeout_rate",
                current_value=0.08,
                threshold=0.05
            ),
        ]

        formatted = alerts.format_alerts(alert_list)

        assert "🚨 Quality Alerts" in formatted
        assert "🟠" in formatted
        assert "🟡" in formatted
        assert "[HIGH]" in formatted
        assert "[MEDIUM]" in formatted

    def test_should_block_session_critical(self, alerts_config: Path):
        """Test should_block_session with CRITICAL alert."""
        alerts = QualityAlerts(config_path=alerts_config)

        critical_alert = Alert(
            severity=SeverityLevel.CRITICAL,
            message="Critical failure",
            metric_name="failure_rate",
            current_value=0.9,
            threshold=0.8
        )

        assert alerts.should_block_session([critical_alert]) is True

    def test_should_block_session_no_critical(self, alerts_config: Path):
        """Test should_block_session without CRITICAL alert."""
        alerts = QualityAlerts(config_path=alerts_config)

        high_alert = Alert(
            severity=SeverityLevel.HIGH,
            message="High failure rate",
            metric_name="failure_rate",
            current_value=0.7,
            threshold=0.6
        )

        assert alerts.should_block_session([high_alert]) is False

    def test_should_block_session_empty(self, alerts_config: Path):
        """Test should_block_session with no alerts."""
        alerts = QualityAlerts(config_path=alerts_config)

        assert alerts.should_block_session([]) is False

    def test_alert_escalation_levels(self, alerts_config: Path):
        """Test alert escalation through severity levels."""
        alerts = QualityAlerts(config_path=alerts_config)

        # Test with various failure rates
        # Thresholds: critical=0.8, high=0.6, medium=0.4
        test_cases = [
            (0.1, None),  # Below LOW - no alert
            (0.25, SeverityLevel.LOW),  # At LOW threshold (0.2)
            (0.5, SeverityLevel.MEDIUM),  # At MEDIUM threshold (0.4)
            (0.7, SeverityLevel.HIGH),  # At HIGH threshold (0.6)
            (0.9, SeverityLevel.CRITICAL),  # At CRITICAL threshold (0.8)
        ]

        for failure_rate, expected_severity in test_cases:
            result = alerts._evaluate_threshold(
                value=failure_rate,
                metric_name="failure_rate",
                display_name="Failure rate"
            )

            if expected_severity is None:
                assert result is None
            else:
                assert result is not None
                assert result.severity == expected_severity


class TestAlertEscalationScenarios:
    """Test realistic alert escalation scenarios."""

    def test_multiple_gates_partial_failure(self, alerts_config: Path):
        """Test alert escalation with partial gate failures."""
        alerts = QualityAlerts(config_path=alerts_config)

        # 5 gates, 2 failed = 40% failure rate
        # Thresholds: medium=0.4, so 0.4 triggers MEDIUM alert
        results = [
            GateExecutionResult(
                gate_name=f"gate-{i}",
                status=GateStatus.PASSED if i < 3 else GateStatus.FAILED,
                duration_ms=100,
                output="OK" if i < 3 else "",
                error="" if i < 3 else "Failed"
            )
            for i in range(5)
        ]

        alert_list = alerts.evaluate_gate_results(results)

        # 40% failure should trigger MEDIUM alert
        assert len(alert_list) > 0

    def test_all_gates_fail_critical_alert(self, alerts_config: Path):
        """Test critical alert when all gates fail."""
        alerts = QualityAlerts(config_path=alerts_config)

        # 4 gates, all failed = 100% failure rate
        # Thresholds: critical=0.8, so triggers CRITICAL alert
        results = [
            GateExecutionResult(
                gate_name=f"gate-{i}",
                status=GateStatus.FAILED,
                duration_ms=50,
                output="",
                error="Failed"
            )
            for i in range(4)
        ]

        alert_list = alerts.evaluate_gate_results(results)

        # 100% failure should trigger CRITICAL alert
        assert len(alert_list) > 0
        critical_alerts = [a for a in alert_list if a.severity == SeverityLevel.CRITICAL]
        assert len(critical_alerts) > 0

    def test_mixed_failures_and_timeouts(self, alerts_config: Path):
        """Test alerts with mix of failures and timeouts."""
        alerts = QualityAlerts(config_path=alerts_config)

        # 4 gates: 1 passed, 2 failed, 1 timeout
        # 50% failure rate (MEDIUM at 0.4), 25% timeout rate (LOW at 0.2)
        results = [
            GateExecutionResult(
                gate_name="gate-1",
                status=GateStatus.PASSED,
                duration_ms=100,
                output="OK"
            ),
            GateExecutionResult(
                gate_name="gate-2",
                status=GateStatus.FAILED,
                duration_ms=50,
                output="",
                error="Failed"
            ),
            GateExecutionResult(
                gate_name="gate-3",
                status=GateStatus.FAILED,
                duration_ms=60,
                output="",
                error="Failed"
            ),
            GateExecutionResult(
                gate_name="gate-4",
                status=GateStatus.TIMEOUT,
                duration_ms=5000,
                output="",
                error="Timeout"
            ),
        ]

        alert_list = alerts.evaluate_gate_results(results)

        # Should generate both failure_rate and timeout_rate alerts
        failure_alerts = [a for a in alert_list if "failure" in a.metric_name]
        timeout_alerts = [a for a in alert_list if "timeout" in a.metric_name]

        assert len(failure_alerts) > 0
        assert len(timeout_alerts) > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

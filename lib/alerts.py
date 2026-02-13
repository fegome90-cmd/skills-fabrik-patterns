"""
Quality Alerts Module

Alert escalation system based on gate results.
Pattern from: Skills-Fabrik code-quality-upgrade/QualityAlerts.ts

Evaluates gate results and generates alerts with severity levels.
"""

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
import yaml

from quality_gates import GateExecutionResult, GateStatus


class SeverityLevel(Enum):
    """Alert severity levels.

    Attributes:
        CRITICAL: Block session end immediately
        HIGH: Major quality issue
        MEDIUM: Moderate quality concern
        LOW: Minor quality issue
        INFO: Informational only
    """
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    INFO = "INFO"

    @property
    def emoji(self) -> str:
        """Return emoji for this severity level."""
        match self:
            case SeverityLevel.CRITICAL:
                return '🔴'
            case SeverityLevel.HIGH:
                return '🟠'
            case SeverityLevel.MEDIUM:
                return '🟡'
            case SeverityLevel.LOW:
                return '🟢'
            case SeverityLevel.INFO:
                return '🔵'
            case _:
                return '?'


@dataclass(frozen=True)
class Alert:
    """A single quality alert."""
    severity: SeverityLevel
    message: str
    metric_name: str
    current_value: float
    threshold: float


class QualityAlerts:
    """Evaluates gate results and generates alerts."""

    def _evaluate_threshold(
        self,
        value: float,
        metric_name: str,
        display_name: str
    ) -> Alert | None:
        """
        Evaluate a metric against severity thresholds.

        Returns an Alert if the value exceeds any threshold, None otherwise.
        Checks thresholds in order: critical > high > medium > low.
        """
        for severity_name in ['critical', 'high', 'medium', 'low']:
            severity_thresholds = self.thresholds.get(severity_name, {})
            threshold = severity_thresholds.get(metric_name, 1.0)

            if value >= threshold:
                return Alert(
                    severity=SeverityLevel(severity_name.upper()),
                    message=f"{display_name}: {value:.1%} >= {threshold:.1%}",
                    metric_name=metric_name,
                    current_value=value,
                    threshold=threshold
                )

        return None

    def __init__(self, config_path: Path):
        """
        Initialize alerts system.

        Args:
            config_path: Path to alerts.yaml config file
        """
        from yaml import YAMLError
        import logging

        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                self.config = yaml.safe_load(f)
        except (YAMLError, OSError) as e:
            # Log error properly - NEVER silently fail
            logging.error(f"Failed to load alerts config from {config_path}: {e}", exc_info=True)
            raise

        self.thresholds = self.config.get('thresholds', {})

    def evaluate_gate_results(self, results: list[GateExecutionResult]) -> list[Alert]:
        """Evaluate gate results and generate alerts."""
        alerts: list[Alert] = []

        if not results:
            return alerts

        total = len(results)
        failed = sum(1 for r in results if r.status == GateStatus.FAILED)
        timed_out = sum(1 for r in results if r.status == GateStatus.TIMEOUT)

        failure_rate = failed / total if total > 0 else 0
        timeout_rate = timed_out / total if total > 0 else 0

        # Check failure rate thresholds
        failure_alert = self._evaluate_threshold(
            failure_rate, 'failure_rate', 'Failure rate'
        )
        if failure_alert:
            alerts.append(failure_alert)

        # Check timeout rate thresholds
        timeout_alert = self._evaluate_threshold(
            timeout_rate, 'timeout_rate', 'Timeout rate'
        )
        if timeout_alert:
            alerts.append(timeout_alert)

        # Individual gate failures are tracked via failure_rate above
        # Critical gate checking can be added as a parameter in the future
        # For now, all failed gates generate alerts based on severity thresholds

        return alerts

    def format_alerts(self, alerts: list[Alert]) -> str:
        """Format alerts for display."""
        if not alerts:
            return "✅ No quality alerts"

        lines = ["🚨 Quality Alerts\n"]
        for alert in alerts:
            lines.append(
                f"{alert.severity.emoji} [{alert.severity.value}] {alert.message}"
            )

        return "\n".join(lines)

    def should_block_session(self, alerts: list[Alert]) -> bool:
        """Check if alerts should block session end."""
        return any(a.severity == SeverityLevel.CRITICAL for a in alerts)

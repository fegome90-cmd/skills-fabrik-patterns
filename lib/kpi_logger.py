#!/usr/bin/env python3
"""
KPIs Logger Module

Logs session metrics to ~/.claude/kpis/events.jsonl
Pattern from: skills-fabrik "No Mess Left Behind"

Tracks quality gate results, auto-fix events, and session duration
for continuous improvement analysis.
"""
import json
import sys
from datetime import datetime
from pathlib import Path
from dataclasses import dataclass, asdict
from typing import Any


@dataclass(frozen=True)
class KPIEvent:
    """KPI event structure."""
    timestamp: str
    session_id: str
    event_type: str  # "quality_gates", "auto_fix", "session_end"
    data: dict[str, Any]


class KPILogger:
    """Logger for KPI events."""

    def __init__(self, kpis_dir: Path | None = None):
        """
        Initialize KPI logger.

        Args:
            kpis_dir: Directory for KPI storage. Defaults to ~/.claude/kpis
        """
        self.kpis_dir = kpis_dir or Path.home() / ".claude" / "kpis"
        self.kpis_dir.mkdir(parents=True, exist_ok=True)
        self.events_file = self.kpis_dir / "events.jsonl"

    def log_event(self, event: KPIEvent) -> None:
        """
        Append event to events.jsonl.

        Args:
            event: KPIEvent to log
        """
        try:
            with open(self.events_file, 'a', encoding='utf-8') as f:
                f.write(json.dumps(asdict(event)) + '\n')
        except (OSError, IOError) as e:
            # Log to stderr for debugging (non-blocking)
            print(f"⚠️ KPI logging failed: {e}", file=sys.stderr)

    def _create_event(self, session_id: str, event_type: str, data: dict[str, Any]) -> KPIEvent:
        """
        Create a KPIEvent with current timestamp.

        Helper method to reduce duplication in event creation.

        Args:
            session_id: Session identifier
            event_type: Type of event (e.g., "quality_gates", "auto_fix", "session_end")
            data: Event-specific data

        Returns:
            KPIEvent with timestamp and provided data
        """
        return KPIEvent(
            timestamp=datetime.now().isoformat(),
            session_id=session_id,
            event_type=event_type,
            data=data
        )

    def log_quality_gates(
        self,
        session_id: str,
        passed: int,
        failed: int,
        timed_out: int,
        duration_ms: int,
        gate_names: list[str] | None = None
    ) -> None:
        """
        Log quality gates results.

        Args:
            session_id: Session identifier
            passed: Number of passed gates
            failed: Number of failed gates
            timed_out: Number of timed out gates
            duration_ms: Total execution duration
            gate_names: Optional list of gate names that ran
        """
        event = self._create_event(
            session_id=session_id,
            event_type="quality_gates",
            data={
                "passed": passed,
                "failed": failed,
                "timed_out": timed_out,
                "duration_ms": duration_ms,
                "gate_names": gate_names or []
            }
        )
        self.log_event(event)

    def log_auto_fix(
        self,
        session_id: str,
        file_path: str,
        file_type: str,
        success: bool,
        formatter: str
    ) -> None:
        """
        Log auto-fix event.

        Args:
            session_id: Session identifier
            file_path: Path to file that was formatted
            file_type: File extension (e.g., ".py", ".ts")
            success: Whether formatting succeeded
            formatter: Name of formatter used
        """
        event = self._create_event(
            session_id=session_id,
            event_type="auto_fix",
            data={
                "file_path": file_path,
                "file_type": file_type,
                "success": success,
                "formatter": formatter
            }
        )
        self.log_event(event)

    def log_session_end(
        self,
        session_id: str,
        duration_seconds: int,
        total_files_modified: int,
        total_auto_fixes: int
    ) -> None:
        """
        Log session end summary.

        Args:
            session_id: Session identifier
            duration_seconds: Session duration in seconds
            total_files_modified: Number of files modified
            total_auto_fixes: Number of auto-fix operations
        """
        event = self._create_event(
            session_id=session_id,
            event_type="session_end",
            data={
                "duration_seconds": duration_seconds,
                "total_files_modified": total_files_modified,
                "total_auto_fixes": total_auto_fixes
            }
        )
        self.log_event(event)

    def get_recent_events(self, limit: int = 100) -> list[KPIEvent]:
        """
        Read recent events from events.jsonl.

        Args:
            limit: Maximum number of events to return

        Returns:
            List of KPIEvent objects, newest first
        """
        if not self.events_file.exists():
            return []

        events = []
        try:
            with open(self.events_file, 'r', encoding='utf-8') as f:
                for line in f:
                    try:
                        data = json.loads(line.strip())
                        events.append(KPIEvent(**data))
                    except (json.JSONDecodeError, TypeError):
                        continue
        except (OSError, IOError) as e:
            print(f"⚠️ Failed to read KPI events: {e}", file=sys.stderr)
            return []

        # Return newest first
        return list(reversed(events[-limit:]))

    def get_summary(self, session_id: str | None = None) -> dict[str, Any]:
        """
        Get summary statistics for KPI events.

        Args:
            session_id: Optional session ID to filter by

        Returns:
            Summary statistics dictionary
        """
        events = self.get_recent_events(limit=10000)

        if session_id:
            events = [e for e in events if e.session_id == session_id]

        summary = {
            "total_events": len(events),
            "quality_gates": {"passed": 0, "failed": 0, "timed_out": 0},
            "auto_fixes": {"success": 0, "failure": 0},
            "sessions": 0
        }

        for event in events:
            if event.event_type == "quality_gates":
                data = event.data
                summary["quality_gates"]["passed"] += data.get("passed", 0)
                summary["quality_gates"]["failed"] += data.get("failed", 0)
                summary["quality_gates"]["timed_out"] += data.get("timed_out", 0)
            elif event.event_type == "auto_fix":
                if event.data.get("success", False):
                    summary["auto_fixes"]["success"] += 1
                else:
                    summary["auto_fixes"]["failure"] += 1
            elif event.event_type == "session_end":
                summary["sessions"] += 1

        return summary

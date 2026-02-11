"""
Handoff Protocol Module

Preserves session state for seamless continuation.
Pattern from: Skills-Fabrik dev-docs/handoff/

Creates handoff documents that summarize:
- Completed tasks
- Next steps
- Artifacts produced
- Context snapshot
"""

from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
import json
import re
from typing import Any


@dataclass(frozen=True)
class Handoff:
    """Handoff data structure."""
    from_session: str
    to_session: str
    completed_tasks: list[str]
    next_steps: list[str]
    artifacts: list[str]
    timestamp: str
    context_snapshot: dict[str, Any]
    notes: str = ""

    def format(self) -> str:
        """Format handoff as markdown document."""
        completed = "\n".join(f"- ✅ {t}" for t in self.completed_tasks)
        if not self.completed_tasks:
            completed = "- *(no completed tasks)*"

        next_items = "\n".join(
            f"{i+1}. {step}" for i, step in enumerate(self.next_steps)
        )
        if not self.next_steps:
            next_items = "*(no next steps defined)*"

        artifacts = "\n".join(f"- `{a}`" for a in self.artifacts)
        if not self.artifacts:
            artifacts = "- *(no artifacts)*"

        notes = f"\n## 📝 Notes\n{self.notes}\n" if self.notes else ""

        return f"""# 🚀 HANDOFF: {self.from_session} → {self.to_session}

**Timestamp**: {self.timestamp}
**Status**: ✅ READY FOR NEXT

## 📊 Completed Tasks
{completed}

## 🎯 Next Steps
{next_items}

## 📦 Artifacts
{artifacts}
{notes}

## 📋 Context Snapshot
```json
{json.dumps(self.context_snapshot, indent=2)}
```
"""


class HandoffProtocol:
    """Manages handoff creation and storage."""

    def __init__(self, claude_dir: Path | None = None):
        """
        Initialize handoff protocol.

        Args:
            claude_dir: Path to Claude directory. Defaults to ~/.claude
        """
        self.claude_dir = claude_dir or Path.home() / ".claude"
        self.handoff_dir = self.claude_dir / "handoffs"
        self.handoff_dir.mkdir(parents=True, exist_ok=True)

    def create_from_session(self, session_data: dict[str, Any]) -> Handoff:
        """
        Create handoff from current session data.

        Args:
            session_data: Dictionary containing session information

        Returns:
            Handoff object
        """
        # Extract or infer session ID
        from_session = session_data.get('session_id', 'current')
        to_session = 'next'

        # Parse completed tasks from conversation or task list
        completed_tasks = session_data.get('completed_tasks', [])
        if isinstance(completed_tasks, str):
            # Try to parse from natural language
            completed_tasks = self._extract_tasks(completed_tasks)

        # Extract next steps
        next_steps = session_data.get('next_steps', [])
        if isinstance(next_steps, str):
            next_steps = self._extract_tasks(next_steps)

        # Get artifacts (files created/modified)
        artifacts = session_data.get('artifacts', [])

        # Context snapshot (key information to preserve)
        context_snapshot = session_data.get('context', {})

        # Any additional notes
        notes = session_data.get('notes', '')

        return Handoff(
            from_session=from_session,
            to_session=to_session,
            completed_tasks=completed_tasks,
            next_steps=next_steps,
            artifacts=artifacts,
            timestamp=datetime.now().isoformat(),
            context_snapshot=context_snapshot,
            notes=notes
        )

    def save_handoff(self, handoff: Handoff) -> Path:
        """
        Save handoff to disk.

        Args:
            handoff: Handoff object to save

        Returns:
            Path to saved handoff file
        """
        # Extract timestamp from handoff, or use current time
        handoff_ts = datetime.fromisoformat(handoff.timestamp)
        timestamp = handoff_ts.strftime('%Y%m%d-%H%M%S')

        # Add session ID suffix to avoid collisions
        session_suffix = handoff.from_session if handoff.from_session != 'current' else 'now'
        filename = f"handoff-{timestamp}-{session_suffix}.md"
        handoff_path = self.handoff_dir / filename

        # Save markdown version
        handoff_path.write_text(handoff.format())

        # Also save JSON for programmatic access
        json_path = self.handoff_dir / f"{filename}.json"
        json_path.write_text(json.dumps(asdict(handoff), indent=2))

        return handoff_path

    def _extract_tasks(self, text: str) -> list[str]:
        """Extract task items from text."""
        tasks: list[str] = []

        # Look for numbered items
        numbered = re.findall(r'^\d+\.?\s+(.+)$', text, re.MULTILINE)
        if numbered:
            return numbered

        # Look for bullet points
        bulleted = re.findall(r'^[-*]\s+(.+)$', text, re.MULTILINE)
        if bulleted:
            return bulleted

        # Split by common delimiters
        for delimiter in ['\n', ';', ',']:
            if delimiter in text:
                return [t.strip() for t in text.split(delimiter) if t.strip()]

        # Return whole text as single task
        return [text.strip()] if text.strip() else []

    def list_handoffs(self, limit: int = 10) -> list[Path]:
        """List recent handoffs."""
        handoffs = sorted(
            self.handoff_dir.glob("handoff-*.md"),
            key=lambda p: p.stat().st_mtime,
            reverse=True
        )
        return handoffs[:limit]

    def cleanup_old_handoffs(self, keep: int = 30) -> int:
        """
        Remove old handoffs, keeping only the most recent.

        Args:
            keep: Number of handoffs to keep (default 30)

        Returns:
            Number of handoff files removed (both .md and .json)
        """
        # Find all .md files (excluding .json files)
        handoff_files = sorted(
            [f for f in self.handoff_dir.glob("handoff-*.md") if not f.name.endswith('.json.md')],
            key=lambda p: p.stat().st_mtime,
            reverse=True  # Newest first
        )

        removed = 0
        for handoff_file in handoff_files[keep:]:
            # Remove both .md and .json files
            if handoff_file.is_file():
                handoff_file.unlink()
                removed += 1

            # Also remove the corresponding .json file
            json_file = handoff_file.with_suffix(handoff_file.suffix + '.json')
            if json_file.is_file():
                json_file.unlink()
                removed += 1

        return removed

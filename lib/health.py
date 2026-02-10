"""
Health Check Module

Verifies Claude Code installation integrity before session start.
Pattern from: Skills-Fabrik shared/ + OpenClaw heartbeat
"""

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
import sys
from typing import Any


class HealthStatus(Enum):
    """Health check status levels."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"


@dataclass(frozen=True)
class HealthCheckResult:
    """Result of a single health check."""
    name: str
    status: HealthStatus
    message: str
    details: dict[str, Any] | None = None


class HealthChecker:
    """Main health checker for Claude Code installation."""

    def __init__(self, claude_dir: Path | None = None):
        """
        Initialize health checker.

        Args:
            claude_dir: Path to Claude directory. Defaults to ~/.claude
        """
        self.claude_dir = claude_dir or Path.home() / ".claude"

    def check_context_integrity(self) -> HealthCheckResult:
        """Verify context system exists and is valid."""
        context_file = self.claude_dir / ".context" / "CLAUDE.md"

        if not context_file.exists():
            return HealthCheckResult(
                name="context_integrity",
                status=HealthStatus.UNHEALTHY,
                message=f"Context file not found: {context_file}",
                details={"path": str(context_file)}
            )

        # Check if file is readable and not empty
        try:
            content = context_file.read_text()
            if len(content.strip()) == 0:
                return HealthCheckResult(
                    name="context_integrity",
                    status=HealthStatus.DEGRADED,
                    message="Context file is empty",
                    details={"path": str(context_file)}
                )
        except Exception as e:
            return HealthCheckResult(
                name="context_integrity",
                status=HealthStatus.UNHEALTHY,
                message=f"Cannot read context file: {e}",
                details={"path": str(context_file)}
            )

        return HealthCheckResult(
            name="context_integrity",
            status=HealthStatus.HEALTHY,
            message="Context system OK",
            details={"path": str(context_file), "size_bytes": len(content)}
        )

    def check_memory_usage(self) -> HealthCheckResult:
        """Check process memory usage."""
        try:
            import psutil
            process = psutil.Process()
            memory_mb = process.memory_info().rss / 1024 / 1024

            # Warn if > 500MB, error if > 1GB
            if memory_mb > 1024:
                return HealthCheckResult(
                    name="memory_usage",
                    status=HealthStatus.UNHEALTHY,
                    message=f"High memory usage: {memory_mb:.1f} MB",
                    details={"memory_mb": round(memory_mb, 1)}
                )
            elif memory_mb > 500:
                return HealthCheckResult(
                    name="memory_usage",
                    status=HealthStatus.DEGRADED,
                    message=f"Elevated memory usage: {memory_mb:.1f} MB",
                    details={"memory_mb": round(memory_mb, 1)}
                )

            return HealthCheckResult(
                name="memory_usage",
                status=HealthStatus.HEALTHY,
                message=f"Memory OK: {memory_mb:.1f} MB",
                details={"memory_mb": round(memory_mb, 1)}
            )
        except ImportError:
            # psutil not available - skip check
            return HealthCheckResult(
                name="memory_usage",
                status=HealthStatus.HEALTHY,
                message="Memory check skipped (psutil not installed)",
                details=None
            )
        except Exception as e:
            return HealthCheckResult(
                name="memory_usage",
                status=HealthStatus.DEGRADED,
                message=f"Memory check failed: {e}",
                details=None
            )

    def check_disk_space(self) -> HealthCheckResult:
        """Check available disk space."""
        try:
            import shutil
            usage = shutil.disk_usage(self.claude_dir)
            free_mb = usage.free / 1024 / 1024

            if free_mb < 50:
                return HealthCheckResult(
                    name="disk_space",
                    status=HealthStatus.UNHEALTHY,
                    message=f"Low disk space: {free_mb:.1f} MB free",
                    details={"free_mb": round(free_mb, 1)}
                )
            elif free_mb < 100:
                return HealthCheckResult(
                    name="disk_space",
                    status=HealthStatus.DEGRADED,
                    message=f"Low disk space: {free_mb:.1f} MB free",
                    details={"free_mb": round(free_mb, 1)}
                )

            return HealthCheckResult(
                name="disk_space",
                status=HealthStatus.HEALTHY,
                message=f"Disk space OK: {free_mb:.0f} MB free",
                details={"free_mb": round(free_mb, 1)}
            )
        except Exception as e:
            return HealthCheckResult(
                name="disk_space",
                status=HealthStatus.DEGRADED,
                message=f"Disk space check failed: {e}",
                details=None
            )

    def check_python_version(self) -> HealthCheckResult:
        """Verify Python version compatibility."""
        version = sys.version_info

        if version < (3, 10):
            return HealthCheckResult(
                name="python_version",
                status=HealthStatus.UNHEALTHY,
                message=f"Python 3.10+ required, found {version.major}.{version.minor}",
                details={"version": f"{version.major}.{version.minor}.{version.micro}"}
            )

        return HealthCheckResult(
            name="python_version",
            status=HealthStatus.HEALTHY,
            message=f"Python {version.major}.{version.minor}.{version.micro}",
            details={"version": f"{version.major}.{version.minor}.{version.micro}"}
        )

    def check_plugin_integrity(self) -> HealthCheckResult:
        """Verify plugin installation is correct."""
        required_files = [
            ".claude-plugin/plugin.json",
            ".claude-plugin/hooks/hooks.json",
            "requirements.txt"
        ]

        missing = []
        for file_path in required_files:
            full_path = Path(__file__).parent.parent / file_path
            if not full_path.exists():
                missing.append(file_path)

        if missing:
            return HealthCheckResult(
                name="plugin_integrity",
                status=HealthStatus.UNHEALTHY,
                message=f"Missing plugin files: {', '.join(missing)}",
                details={"missing": missing}
            )

        return HealthCheckResult(
            name="plugin_integrity",
            status=HealthStatus.HEALTHY,
            message="Plugin files OK",
            details={"required_files": required_files}
        )

    def run_all(self) -> list[HealthCheckResult]:
        """Run all health checks and return results."""
        return [
            self.check_python_version(),
            self.check_plugin_integrity(),
            self.check_context_integrity(),
            self.check_memory_usage(),
            self.check_disk_space(),
        ]

    def get_overall_status(self, results: list[HealthCheckResult]) -> HealthStatus:
        """Determine overall health from all results."""
        if any(r.status == HealthStatus.UNHEALTHY for r in results):
            return HealthStatus.UNHEALTHY
        if any(r.status == HealthStatus.DEGRADED for r in results):
            return HealthStatus.DEGRADED
        return HealthStatus.HEALTHY

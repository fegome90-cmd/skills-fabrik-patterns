"""
EvidenceCLI Module

Pre-activation validation of project state.
Pattern from: Skills-Fabrik code-quality-upgrade/EvidenceCLI.ts

Validates project before starting work to prevent wasted time
on invalid projects or missing dependencies.
"""

from dataclasses import dataclass
from enum import Enum
import subprocess
import time
from pathlib import Path
from typing import Any, Callable


class ValidationStatus(Enum):
    """Validation check status."""
    PASSED = "passed"
    FAILED = "failed"
    SKIPPED = "skipped"
    WARNING = "warning"

    @property
    def emoji(self) -> str:
        """Return emoji for this status."""
        return {
            ValidationStatus.PASSED: "✅",
            ValidationStatus.FAILED: "❌",
            ValidationStatus.WARNING: "⚠️",
            ValidationStatus.SKIPPED: "⏭️"
        }[self]


@dataclass(frozen=True)
class ValidationResult:
    """Result of a single validation check."""
    check_name: str
    status: ValidationStatus
    message: str
    duration_ms: int
    details: dict[str, Any] | None = None


class EvidenceCheck:
    """Base class for validation checks."""

    def __init__(self, name: str, description: str, critical: bool = True):
        self.name = name
        self.description = description
        self.critical = critical

    def validate(self, project_path: Path) -> ValidationResult:
        """Run the validation check. Override in subclasses."""
        raise NotImplementedError


class ProjectStructureCheck(EvidenceCheck):
    """Validates project structure is present."""

    def validate(self, project_path: Path) -> ValidationResult:
        """Check for common project indicators."""
        start = time.time()

        # Look for common project files
        indicators = [
            "package.json",  # Node.js
            "pyproject.toml",  # Python
            "Cargo.toml",  # Rust
            "go.mod",  # Go
            "pom.xml",  # Maven
            "build.gradle",  # Gradle
            "Gemfile",  # Ruby
            "composer.json",  # PHP
        ]

        found = []
        for indicator in indicators:
            if (project_path / indicator).exists():
                found.append(indicator)

        if found:
            duration = int((time.time() - start) * 1000)
            return ValidationResult(
                check_name=self.name,
                status=ValidationStatus.PASSED,
                message=f"Project structure detected: {', '.join(found)}",
                duration_ms=duration,
                details={"found": found}
            )

        duration = int((time.time() - start) * 1000)
        return ValidationResult(
            check_name=self.name,
            status=ValidationStatus.WARNING,
            message="No standard project file found",
            duration_ms=duration,
            details={"checked": indicators}
        )


class DependencyCheck(EvidenceCheck):
    """Validates dependencies are installed."""

    def validate(self, project_path: Path) -> ValidationResult:
        """Check for common dependency directories."""
        start = time.time()

        # Look for dependency directories
        indicators = [
            "node_modules",  # Node.js
            "venv",  # Python virtualenv
            ".venv",  # Python virtualenv
            "target",  # Rust/Cargo
            "vendor",  # Go/Ruby/PHP
            "__pycache__",  # Python (at least some packages used)
        ]

        found = []
        for indicator in indicators:
            if (project_path / indicator).exists():
                found.append(indicator)

        if found:
            duration = int((time.time() - start) * 1000)
            return ValidationResult(
                check_name=self.name,
                status=ValidationStatus.PASSED,
                message=f"Dependencies installed: {', '.join(found)}",
                duration_ms=duration,
                details={"found": found}
            )

        duration = int((time.time() - start) * 1000)
        return ValidationResult(
            check_name=self.name,
            status=ValidationStatus.WARNING,
            message="No dependency directory found",
            duration_ms=duration,
            details={"checked": indicators}
        )


class ConfigFileCheck(EvidenceCheck):
    """Validates required config files exist."""

    def __init__(self, name: str, description: str, critical: bool, required_files: list[str]):
        super().__init__(name, description, critical)
        self.required_files = required_files

    def validate(self, project_path: Path) -> ValidationResult:
        """Check for required config files."""
        start = time.time()

        missing = []
        found = []
        for file_path in self.required_files:
            full_path = project_path / file_path
            if full_path.exists():
                found.append(file_path)
            else:
                missing.append(file_path)

        duration = int((time.time() - start) * 1000)

        if not missing:
            return ValidationResult(
                check_name=self.name,
                status=ValidationStatus.PASSED,
                message=f"All config files present: {len(found)}",
                duration_ms=duration,
                details={"found": found}
            )

        if self.critical:
            return ValidationResult(
                check_name=self.name,
                status=ValidationStatus.FAILED,
                message=f"Missing critical files: {', '.join(missing)}",
                duration_ms=duration,
                details={"missing": missing, "found": found}
            )

        return ValidationResult(
            check_name=self.name,
            status=ValidationStatus.WARNING,
            message=f"Missing optional files: {', '.join(missing)}",
            duration_ms=duration,
            details={"missing": missing, "found": found}
        )


class EvidenceCLI:
    """Main Evidence CLI for project validation."""

    def __init__(
        self,
        fail_fast: bool = True,
        parallel: bool = True,
        timeout_ms: int = 30000
    ):
        """
        Initialize Evidence CLI.

        Args:
            fail_fast: Stop on first critical failure
            parallel: Run checks in parallel (when implemented)
            timeout_ms: Maximum time for all checks
        """
        self.fail_fast = fail_fast
        self.parallel = parallel
        self.timeout_ms = timeout_ms
        self.checks: list[EvidenceCheck] = []

    def add_check(self, check: EvidenceCheck) -> None:
        """Add a validation check."""
        self.checks.append(check)

    def add_default_checks(self) -> None:
        """Add standard validation checks."""
        self.checks.extend([
            ProjectStructureCheck("project-structure", "Verify project structure", critical=False),
            DependencyCheck("dependencies-check", "Check dependencies installed", critical=False),
        ])

    def validate(self, project_path: Path) -> list[ValidationResult]:
        """
        Run all validation checks.

        Args:
            project_path: Path to project directory

        Returns:
            List of validation results
        """
        results = []

        for check in self.checks:
            try:
                result = check.validate(project_path)
                results.append(result)

                # Fail fast if critical check failed
                if self.fail_fast and check.critical and result.status == ValidationStatus.FAILED:
                    break

            except Exception as e:
                # Don't let one check break all validation
                results.append(ValidationResult(
                    check_name=check.name,
                    status=ValidationStatus.FAILED,
                    message=f"Check failed with error: {e}",
                    duration_ms=0
                ))

        return results

    def get_summary(self, results: list[ValidationResult]) -> str:
        """Get human-readable summary of validation results."""
        passed = sum(1 for r in results if r.status == ValidationStatus.PASSED)
        failed = sum(1 for r in results if r.status == ValidationStatus.FAILED)
        warnings = sum(1 for r in results if r.status == ValidationStatus.WARNING)

        lines = [
            f"📊 Evidence Validation: {passed} passed, {warnings} warnings, {failed} failed"
        ]

        for result in results:
            lines.append(f"  {result.status.emoji} {result.check_name}: {result.message}")

        return "\n".join(lines)

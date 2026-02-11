#!/usr/bin/env python3
"""
Ruff Formatter Module

Wrapper para ruff (Python formatter + linter).
Reemplaza: black (formatting), flake8 (linting), isort (imports)

Pattern from: skills-fabrik "No Mess Left Behind"
Provides a unified interface for formatting and linting Python files.
"""
import subprocess
from pathlib import Path
from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True)
class RuffResult:
    """Resultado de ejecución ruff."""
    success: bool
    formatted: bool
    lint_errors: int
    lint_fixed: int
    output: str
    exit_code: int


class RuffFormatter:
    """Wrapper para ruff format + check."""

    def __init__(self, config_path: Path | None = None, target_version: str = "py314"):
        """
        Initialize Ruff formatter.

        Args:
            config_path: Optional path to ruff config file (ruff.toml or pyproject.toml)
            target_version: Python target version (default: py314)
        """
        self.config_path = config_path
        self.target_version = target_version
        self.config_args = [f"--config={config_path}"] if config_path else []

    def _handle_subprocess_error(self, error: Exception, operation: str) -> RuffResult:
        """
        Handle subprocess errors consistently.

        Args:
            error: The caught exception
            operation: Description of the operation (e.g., "ruff format", "ruff check")

        Returns:
            RuffResult with error details
        """
        if isinstance(error, subprocess.TimeoutExpired):
            timeout = error.timeout if hasattr(error, 'timeout') else 10
            return RuffResult(
                success=False,
                formatted=False,
                lint_errors=0,
                lint_fixed=0,
                output=f"{operation} timed out after {timeout} seconds",
                exit_code=-1
            )
        elif isinstance(error, FileNotFoundError):
            return RuffResult(
                success=False,
                formatted=False,
                lint_errors=0,
                lint_fixed=0,
                output="ruff not found. Install with: pip install ruff",
                exit_code=-2
            )
        else:
            return RuffResult(
                success=False,
                formatted=False,
                lint_errors=0,
                lint_fixed=0,
                output=f"Unexpected error: {type(error).__name__}",
                exit_code=-3
            )

    def format_file(self, file_path: Path) -> RuffResult:
        """
        Formatea archivo Python con ruff format.

        Args:
            file_path: Path to Python file to format

        Returns:
            RuffResult with formatting outcome
        """
        cmd = [
            "ruff", "format",
            *self.config_args,
            str(file_path)
        ]

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=10
            )

            # Determine if file was actually formatted
            formatted = (
                result.returncode == 0 and
                ('formatted' in result.stdout.lower() or '1 file' in result.stdout)
            )

            return RuffResult(
                success=result.returncode == 0,
                formatted=formatted,
                lint_errors=0,
                lint_fixed=0,
                output=result.stdout + result.stderr,
                exit_code=result.returncode
            )
        except (subprocess.TimeoutExpired, FileNotFoundError) as e:
            return self._handle_subprocess_error(e, "ruff format")

    def check_and_fix(
        self,
        file_path: Path | None = None,
        fix: bool = True
    ) -> RuffResult:
        """
        Ejecuta ruff check con auto-fix.

        Args:
            file_path: Path to file/directory, or None for current directory
            fix: Whether to automatically fix fixable issues

        Returns:
            RuffResult with lint findings
        """
        target = [str(file_path)] if file_path else ["."]
        fix_flag = ["--fix"] if fix else []

        cmd = [
            "ruff", "check",
            *fix_flag,
            *self.config_args,
            *target
        ]

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30
            )

            output = result.stdout + result.stderr

            # Parse output for fixed issues count
            fixed = 0
            if "Found" in output and "fixed" in output:
                # "Found 3 errors, fixed 2"
                parts = output.split(",")
                for part in parts:
                    if "fixed" in part:
                        try:
                            fixed = int(''.join(filter(str.isdigit, part)))
                        except ValueError:
                            pass

            # Count remaining errors from exit code
            # ruff returns 1 if there are unfixed issues
            lint_errors = 1 if result.returncode == 1 else 0

            return RuffResult(
                success=result.returncode == 0,
                formatted=False,
                lint_errors=lint_errors,
                lint_fixed=fixed,
                output=output,
                exit_code=result.returncode
            )
        except (subprocess.TimeoutExpired, FileNotFoundError) as e:
            return self._handle_subprocess_error(e, "ruff check")

    def format_and_check(self, file_path: Path) -> RuffResult:
        """
        Formatea + lint en un solo comando.

        Args:
            file_path: Path to Python file

        Returns:
            RuffResult with combined results
        """
        format_result = self.format_file(file_path)
        check_result = self.check_and_fix(file_path)

        combined_output = format_result.output
        if check_result.output.strip():
            combined_output += "\n" + check_result.output

        return RuffResult(
            success=format_result.success and check_result.success,
            formatted=format_result.formatted,
            lint_errors=check_result.lint_errors,
            lint_fixed=check_result.lint_fixed,
            output=combined_output,
            exit_code=max(format_result.exit_code, check_result.exit_code)
        )

    def is_available(self) -> bool:
        """Check if ruff is installed and available."""
        try:
            result = subprocess.run(
                ["ruff", "--version"],
                capture_output=True,
                timeout=5
            )
            return result.returncode == 0
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return False

#!/usr/bin/env python3
"""
Auto-Fix Hook (PostToolUse)

Applies automatic formatting fixes to edited files.
Pattern from: skills-fabrik "No Mess Left Behind"

When Claude uses Write or Edit tools on a file, this hook:
1. Detects the file type by extension
2. Applies the appropriate formatter
3. Silently succeeds if formatting fails (non-blocking)

Input: JSON via stdin with tool result data
Output: Formatted file (in-place) + stderr status message
"""
import json
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

# Add lib directory to path
lib_dir = Path(__file__).parent.parent / "lib"
sys.path.insert(0, str(lib_dir))

from kpi_logger import KPILogger
from ruff_formatter import RuffFormatter
from fallback import create_fallback_manager, FallbackAction


@dataclass(frozen=True)
class FormatterConfig:
    """Configuration for a single formatter."""
    name: str
    enabled: bool
    extensions: tuple[str, ...]
    command: str


class AutoFixConfig:
    """Loads and manages auto-fix configuration from YAML."""

    def __init__(self, config_path: Path):
        """
        Initialize configuration from YAML file.

        Args:
            config_path: Path to auto_fix.yaml config file
        """
        self.enabled = True
        self.timeout = 15
        self.formatters: dict[str, FormatterConfig] = {}
        self.exclude_dirs: set[str] = set()
        self.exclude_patterns: set[str] = set()
        self.verbose = False

        self._load_config(config_path)

    def _load_config(self, config_path: Path) -> None:
        """Load configuration from YAML file."""
        try:
            import yaml
            with open(config_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f) or {}
        except Exception:
            # Use safe defaults if config fails to load
            self._set_defaults()
            return

        self.enabled = config.get('enabled', True)
        self.timeout = config.get('timeout', 15)
        self.verbose = config.get('options', {}).get('verbose', False)

        # Load formatters
        for name, fmt_config in config.get('formatters', {}).items():
            if fmt_config.get('enabled', True):
                self.formatters[name] = FormatterConfig(
                    name=name,
                    enabled=True,
                    extensions=tuple(fmt_config.get('extensions', [])),
                    command=fmt_config.get('command', '')
                )

        # Load exclude directories
        self.exclude_dirs = set(config.get('exclude_dirs', []))
        self.exclude_patterns = set(config.get('exclude_patterns', []))

    def _set_defaults(self) -> None:
        """Set safe defaults if config loading fails."""
        self.enabled = True
        self.timeout = 15
        self.verbose = False
        self.formatters = {
            'python': FormatterConfig('python', True, ('.py',), 'ruff format'),
            'typescript': FormatterConfig('typescript', True, ('.ts', '.tsx'), 'npx prettier --write'),
            'javascript': FormatterConfig('javascript', True, ('.js', '.jsx'), 'npx prettier --write'),
            'markdown': FormatterConfig('markdown', True, ('.md',), 'npx prettier --write'),
            'yaml': FormatterConfig('yaml', True, ('.yaml', '.yml'), 'npx prettier --write'),
            'json': FormatterConfig('json', True, ('.json',), 'npx prettier --write'),
        }
        self.exclude_dirs = {
            '.venv', 'venv', '.virtualenv', 'node_modules', '.pytest_cache',
            '__pycache__', '.tox', '.git', '.mypy_cache', 'dist', 'build'
        }

    def get_formatter_for_extension(self, ext: str) -> FormatterConfig | None:
        """
        Get formatter configuration for a file extension.

        Args:
            ext: File extension (e.g., '.py', '.ts')

        Returns:
            FormatterConfig if found, None otherwise
        """
        for fmt in self.formatters.values():
            if ext in fmt.extensions:
                return fmt
        return None


class AutoFixHook:
    """Handles automatic file formatting on PostToolUse hook."""

    def __init__(self, plugin_root: Path):
        """
        Initialize auto-fix hook.

        Args:
            plugin_root: Root directory of the plugin
        """
        self.plugin_root = plugin_root
        self.config = AutoFixConfig(plugin_root / "config" / "auto_fix.yaml")
        self.fallback_manager = create_fallback_manager(plugin_root)
        self.ruff_formatter = RuffFormatter(
            config_path=plugin_root / "config" / "ruff.yaml"
        )
        self.kpi_logger = KPILogger()

    def should_exclude(self, file_path: Path) -> bool:
        """
        Check if file should be excluded from formatting.

        Args:
            file_path: Path to the file

        Returns:
            True if file should be excluded
        """
        # Check directory exclusions
        for part in file_path.parts:
            if part in self.config.exclude_dirs:
                return True

        # Check pattern exclusions
        import fnmatch
        file_name = file_path.name
        for pattern in self.config.exclude_patterns:
            if fnmatch.fnmatch(file_name, pattern):
                return True

        return False

    def format_file(self, file_path: Path) -> tuple[bool, str]:
        """
        Format a single file.

        Args:
            file_path: Path to file to format

        Returns:
            Tuple of (formatted: bool, formatter_name: str)
        """
        ext = file_path.suffix
        formatter_config = self.config.get_formatter_for_extension(ext)

        if not formatter_config:
            return False, 'none'

        if not formatter_config.enabled:
            return False, formatter_config.name

        # Check exclusions
        if self.should_exclude(file_path):
            return False, formatter_config.name

        # Use RuffFormatter for Python files (WO-0007)
        if ext == '.py':
            return self._format_python_ruff(file_path)

        # Use subprocess for other formatters
        return self._format_subprocess(file_path, formatter_config)

    def _format_python_ruff(self, file_path: Path) -> tuple[bool, str]:
        """
        Format Python file using RuffFormatter wrapper.

        Args:
            file_path: Path to Python file

        Returns:
            Tuple of (formatted: bool, formatter_name: str)
        """
        try:
            result = self.ruff_formatter.format_file(file_path)
            return result.formatted, 'ruff'
        except Exception as e:
            # Use fallback handling
            action, message = self.fallback_manager.handle_failure(
                'PostToolUse', e, is_timeout=False
            )
            if self.config.verbose:
                print(f"⚠️ {message}", file=sys.stderr)
            return False, 'ruff'

    def _format_subprocess(
        self,
        file_path: Path,
        formatter_config: FormatterConfig
    ) -> tuple[bool, str]:
        """
        Format file using subprocess (prettier, etc.).

        Args:
            file_path: Path to file
            formatter_config: Formatter configuration

        Returns:
            Tuple of (formatted: bool, formatter_name: str)
        """
        try:
            cmd = formatter_config.command.split() + [str(file_path)]
            result = subprocess.run(
                cmd,
                capture_output=True,
                timeout=self.config.timeout,
                text=True
            )

            # Check if file was actually formatted
            formatted = self._was_formatted(result)
            return formatted, formatter_config.name

        except subprocess.TimeoutExpired as e:
            action, message = self.fallback_manager.handle_failure(
                'PostToolUse', e, is_timeout=True
            )
            if self.config.verbose:
                print(f"⚠️ {message}", file=sys.stderr)
            return False, formatter_config.name

        except (FileNotFoundError, OSError) as e:
            action, message = self.fallback_manager.handle_failure(
                'PostToolUse', e, is_timeout=False
            )
            if self.config.verbose:
                print(f"⚠️ {message}", file=sys.stderr)
            return False, formatter_config.name

    def _was_formatted(self, result: subprocess.CompletedProcess) -> bool:
        """
        Check if the file was actually formatted.

        Args:
            result: CompletedProcess from subprocess.run

        Returns:
            True if file was formatted
        """
        if result.returncode != 0:
            return False

        # Check for "formatted" keyword (ruff)
        if 'formatted' in result.stdout.lower() or 'formatted' in result.stderr.lower():
            return True

        # Prettier outputs filename when formatting occurs
        if result.stdout.strip():
            return True

        return False

    def run(self, input_data: dict[str, Any]) -> int:
        """
        Process hook input and format file if needed.

        Args:
            input_data: JSON input from Claude Code hook

        Returns:
            Exit code (0 for success)
        """
        if not self.config.enabled:
            return 0

        # Only process Write/Edit tools
        tool = input_data.get('tool')
        if tool not in ['Write', 'Edit']:
            return 0

        file_path = input_data.get('path')
        if not file_path:
            return 0

        path = Path(file_path)
        if not path.exists():
            return 0

        # Apply formatting
        formatted, formatter_name = self.format_file(path)

        if formatted:
            print(f"✅ Auto-formatted: {path.name}", file=sys.stderr)

        # Log KPI event
        session_id = time.strftime('%Y%m%d-%H%M%S')
        self.kpi_logger.log_auto_fix(
            session_id=session_id,
            file_path=str(path),
            file_type=path.suffix,
            success=formatted,
            formatter=formatter_name
        )

        return 0


def main() -> int:
    """Process tool result and format if needed."""
    plugin_root = Path(__file__).parent.parent

    try:
        # Read from stdin
        stdin_content = sys.stdin.read() if hasattr(sys.stdin, 'read') else str(sys.stdin)

        if not stdin_content or not stdin_content.strip():
            return 0

        input_data = json.loads(stdin_content)

    except (json.JSONDecodeError, ValueError, AttributeError, OSError) as e:
        # Use fallback handling for input errors
        hook = AutoFixHook(plugin_root)
        action, message = hook.fallback_manager.handle_failure(
            'PostToolUse', e, is_timeout=False
        )
        # PostToolUse failures should never block - always return 0
        return 0

    # Initialize and run hook
    hook = AutoFixHook(plugin_root)
    return hook.run(input_data)


if __name__ == "__main__":
    sys.exit(main())

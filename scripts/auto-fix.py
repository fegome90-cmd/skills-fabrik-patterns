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
import sys
import subprocess
from pathlib import Path

# Formatters por extensión
# Nota: Felipe usa ruff según rules/python/coding-style.md
FORMATTERS = {
    '.ts': 'npx prettier --write',
    '.tsx': 'npx prettier --write',
    '.js': 'npx prettier --write',
    '.jsx': 'npx prettier --write',
    '.py': 'ruff format',     # Formatea Python (reemplaza black)
    '.md': 'npx prettier --write',
    '.yaml': 'npx prettier --write',
    '.yml': 'npx prettier --write',
    '.json': 'npx prettier --write',
}

# Directorios a excluir
EXCLUDE_DIRS = {
    '.venv', 'venv', '.virtualenv', 'node_modules', '.pytest_cache',
    '__pycache__', '.tox', '.git', '.mypy_cache',
    'dist', 'build', '.eggs'
}


def should_exclude(file_path: Path) -> bool:
    """Check if file is in an excluded directory."""
    try:
        # Check if any parent directory is in exclude list
        for part in file_path.parts:
            if part in EXCLUDE_DIRS:
                return True
        return False
    except (OSError, ValueError):
        return False


def _was_formatted(result: subprocess.CompletedProcess) -> bool:
    """
    Check if the file was actually formatted by the formatter.

    Different formatters have different output patterns:
    - ruff: says "formatted" or returns 0 with no output if no changes
    - prettier: outputs the filename when formatting occurred

    Args:
        result: CompletedProcess from subprocess.run

    Returns:
        True if file was formatted, False otherwise
    """
    if result.returncode != 0:
        return False

    # Check for "formatted" keyword in output (ruff, some prettier versions)
    if 'formatted' in result.stdout.lower() or 'formatted' in result.stderr.lower():
        return True

    # Prettier and other formatters output filenames when formatting occurs
    if result.stdout.strip():
        return True

    return False


def format_file(file_path: Path) -> bool:
    """
    Format a single file.

    Returns True if formatting was attempted, False otherwise.
    """
    ext = file_path.suffix
    formatter = FORMATTERS.get(ext)
    if not formatter:
        return False

    # Check exclusions
    if should_exclude(file_path):
        return False

    try:
        cmd = formatter.split() + [str(file_path)]
        result = subprocess.run(
            cmd,
            capture_output=True,
            timeout=10,
            text=True
        )

        return _was_formatted(result)
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError) as e:
        # Log to stderr for debugging (non-blocking)
        print(f"⚠️ Auto-format failed for {file_path.name}: {e}", file=sys.stderr)
        return False


def main() -> int:
    """Process tool result and format if needed."""
    try:
        # Read from stdin (handles both file-like and string input in tests)
        if hasattr(sys.stdin, 'read'):
            stdin_content = sys.stdin.read()
        else:
            # In tests, sys.stdin might be replaced with a string
            stdin_content = str(sys.stdin)

        if not stdin_content or not stdin_content.strip():
            return 0
        input_data = json.loads(stdin_content)
    except (json.JSONDecodeError, ValueError):
        return 0  # No hay datos, salir silenciosamente

    # Solo procesar Write/Edit tools
    tool = input_data.get('tool')
    if tool not in ['Write', 'Edit']:
        return 0

    file_path = input_data.get('path')
    if not file_path:
        return 0

    path = Path(file_path)
    if not path.exists():
        return 0

    # Aplicar formato
    if format_file(path):
        print(f"✅ Auto-formatted: {path.name}", file=sys.stderr)

    return 0


if __name__ == "__main__":
    sys.exit(main())

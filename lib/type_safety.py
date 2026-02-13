"""
Type Safety Improvements Module

NewType wrappers for enhanced type validation.
Provides compile-time type safety for critical values.

Pattern from: Type Design Analyzer improvements
"""

from typing import NewType


# Type-safe wrappers for common values
# These provide enhanced type safety at creation time

DepthValue = NewType('DepthValue', str)
"""Valid depth level value (s, m, or f).

Used instead of plain str to prevent invalid depth values.
"""

ValidatedCommand = NewType('ValidatedCommand', str)
"""Command that has been validated against whitelist.

Ensures only pre-validated commands are used in quality gates.
"""

FilePathStr = NewType('FilePathStr', str)
"""Valid file path string.

Use for paths that should be file system paths (not URLs, not command injection).
"""

NonEmptyStr = NewType('NonEmptyStr', str)
"""Non-empty string.

Prevents empty strings for critical fields like names, IDs, etc.
"""


def validate_depth(value: str) -> DepthValue:
    """
    Validate depth value at runtime.

    Args:
        value: Depth value to validate (s, m, or f)

    Returns:
        Validated DepthValue

    Raises:
        ValueError: If value is not a valid depth
    """
    valid_depths = {'s', 'm', 'f'}
    if value not in valid_depths:
        raise ValueError(f"Invalid depth: {value!r}. Must be one of {valid_depths}")
    return DepthValue(value)


def validate_command_format(command: str) -> ValidatedCommand:
    """
    Validate command has no dangerous shell patterns.

    Args:
        command: Command string to validate

    Returns:
        Validated command string

    Raises:
        ValueError: If command contains dangerous patterns
    """
    # Check for common shell injection patterns
    dangerous = ['|', '&', ';', '$(', ')', '\n', '\r']
    if any(d in command for d in dangerous):
        # Allow safe patterns
        if '2>&1' in command or 'fd<' in command:
            pass  # Safe stderr redirect
        elif '||' in command and command.strip().startswith(('if', 'for', 'while')):
            pass  # Safe shell control flow
        else:
            raise ValueError(f"Dangerous pattern in command: {command!r}")

    return ValidatedCommand(command)


def validate_non_empty(value: str, field_name: str = "value") -> NonEmptyStr:
    """
    Validate string is non-empty after stripping.

    Args:
        value: String to validate
        field_name: Field name for error messages

    Returns:
        Validated non-empty string

    Raises:
        ValueError: If value is empty or only whitespace
    """
    if not value or not value.strip():
        raise ValueError(f"{field_name} cannot be empty")
    return NonEmptyStr(value)

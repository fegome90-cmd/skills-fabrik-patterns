#!/usr/bin/env python3
"""
Inject Context Script (UserPromptSubmit Hook)

Fuses TAGs System + EvidenceCLI:
1. Injects semantic context tags from Elle's memory
2. Validates project state before work begins

Input: JSON via stdin with user prompt
Output: JSON with additionalContext for Claude Code
"""

import json
import sys
import time
from pathlib import Path

# Add lib directory to path
lib_dir = Path(__file__).parent.parent / "lib"
sys.path.insert(0, str(lib_dir))

from tag_system import TagInjector
from evidence_cli import EvidenceCLI
from kpi_logger import KPILogger, KPIEvent
from fallback import create_fallback_manager


def main() -> int:
    """Inject context tags and validate evidence."""
    plugin_root = Path(__file__).parent.parent
    fallback_manager = create_fallback_manager(plugin_root)
    start_time = time.time()

    # Read input from Claude Code
    try:
        stdin_content = sys.stdin.read() if hasattr(sys.stdin, 'read') else str(sys.stdin)
        if not stdin_content or not stdin_content.strip():
            return 0
        input_data = json.loads(stdin_content)
    except (json.JSONDecodeError, ValueError, AttributeError, OSError) as e:
        action, message = fallback_manager.handle_failure('UserPromptSubmit', e)
        # UserPromptSubmit failures should never block - always return 0
        return 0

    user_prompt = input_data.get('prompt', '')
    project_path = Path(input_data.get('project_path', '.'))

    # Build output for Claude Code
    output: dict[str, list[dict[str, str]]] = {
        "additionalContext": []
    }

    tags_injected = False
    failed = []
    warnings = []

    # 1. Inject TAGs from Elle's context
    try:
        injector = TagInjector()
        enhanced_prompt = injector.inject(user_prompt)
        tags_injected = enhanced_prompt != user_prompt

        # Add TAGs summary if any were found
        if tags_injected:
            tag_lines = enhanced_prompt.split('\n\n')[0]  # Get TAGs section
            output["additionalContext"].append({
                "name": "TAGs Context",
                "description": "Semantic context from Elle's memory",
                "content": tag_lines
            })
    except Exception as e:
        action, message = fallback_manager.handle_failure('UserPromptSubmit', e)
        # Continue without TAGs on failure

    # 2. Run Evidence validation
    try:
        evidence_cli = EvidenceCLI(fail_fast=False)  # Don't block on warnings
        evidence_cli.add_default_checks()
        validation_results = evidence_cli.validate(project_path)

        failed = [r for r in validation_results if r.status.value == "failed"]
        warnings = [r for r in validation_results if r.status.value == "warning"]

        if failed or warnings:
            summary = evidence_cli.get_summary(validation_results)
            output["additionalContext"].append({
                "name": "Evidence Validation",
                "description": "Project state validation results",
                "content": summary
            })
    except Exception as e:
        action, message = fallback_manager.handle_failure('UserPromptSubmit', e)
        # Continue without validation on failure

    # Log KPI event
    try:
        duration_ms = int((time.time() - start_time) * 1000)
        kpi_logger = KPILogger()
        session_id = time.strftime('%Y%m%d-%H%M%S')
        event = KPIEvent(
            timestamp=time.strftime('%Y-%m-%dT%H:%M:%S'),
            session_id=session_id,
            event_type="context_injection",
            data={
                "duration_ms": duration_ms,
                "tags_injected": tags_injected,
                "validation_failures": len(failed),
                "validation_warnings": len(warnings),
                "project_path": str(project_path)
            }
        )
        kpi_logger.log_event(event)
    except Exception as e:
        action, message = fallback_manager.handle_failure('UserPromptSubmit', e)
        # KPI logging failures should not block

    # Print output for Claude Code
    print(json.dumps(output, indent=2))

    # Return 0 to never block session start
    return 0


if __name__ == "__main__":
    sys.exit(main())

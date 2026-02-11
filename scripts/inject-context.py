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
from pathlib import Path

# Add lib directory to path
lib_dir = Path(__file__).parent.parent / "lib"
sys.path.insert(0, str(lib_dir))

from tag_system import TagInjector
from evidence_cli import EvidenceCLI


def main() -> int:
    """Inject context tags and validate evidence."""
    # Read input from Claude Code
    try:
        input_data = json.load(sys.stdin)
    except json.JSONDecodeError:
        # No JSON input - might be direct invocation for testing
        print("⚠️ No JSON input received", file=sys.stderr)
        return 0

    user_prompt = input_data.get('prompt', '')
    project_path = Path(input_data.get('project_path', '.'))

    # 1. Inject TAGs from Elle's context
    injector = TagInjector()
    enhanced_prompt = injector.inject(user_prompt)

    # 2. Run Evidence validation
    evidence_cli = EvidenceCLI(fail_fast=False)  # Don't block on warnings
    evidence_cli.add_default_checks()
    validation_results = evidence_cli.validate(project_path)

    # Build output for Claude Code
    output: dict[str, list[dict[str, str]]] = {
        "additionalContext": []
    }

    # Add TAGs summary if any were found
    if enhanced_prompt != user_prompt:
        tag_lines = enhanced_prompt.split('\n\n')[0]  # Get TAGs section
        output["additionalContext"].append({
            "name": "TAGs Context",
            "description": "Semantic context from Elle's memory",
            "content": tag_lines
        })

    # Add evidence validation summary
    failed = [r for r in validation_results if r.status.value == "failed"]
    warnings = [r for r in validation_results if r.status.value == "warning"]

    if failed or warnings:
        summary = evidence_cli.get_summary(validation_results)
        output["additionalContext"].append({
            "name": "Evidence Validation",
            "description": "Project state validation results",
            "content": summary
        })

    # Print output for Claude Code
    print(json.dumps(output, indent=2))

    # Return 0 to never block session start
    return 0


if __name__ == "__main__":
    sys.exit(main())

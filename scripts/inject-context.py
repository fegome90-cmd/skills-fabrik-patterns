#!/usr/bin/env python3
"""
Inject Context Script (UserPromptSubmit Hook)

Injects semantic context tags from Elle's memory.
NOTE: EvidenceCLI validation moved to SessionStart (health-check.py) for performance.
See: P1 fix in hook-pathology-fix plan.

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
from kpi_logger import KPILogger, KPIEvent
from fallback import create_fallback_manager


def main() -> int:
    """Inject context tags and validate evidence."""
    plugin_root = Path(__file__).parent.parent
    fallback_manager = create_fallback_manager(plugin_root)
    start_time = time.time()

    # Read input from Claude Code
    # NOTE: We parse stdin manually instead of using get_project_path_from_stdin()
    # because we also need the 'prompt' field (line 44). The utility function
    # only returns the cwd and consumes stdin, making other fields inaccessible.
    try:
        stdin_content = sys.stdin.read()
        if not stdin_content or not stdin_content.strip():
            return 0
        input_data = json.loads(stdin_content)
    except (json.JSONDecodeError, ValueError, AttributeError, OSError) as e:
        action, message = fallback_manager.handle_failure('UserPromptSubmit', e)
        # UserPromptSubmit failures should never block - always return 0
        return 0

    user_prompt = input_data.get('prompt', '')
    # Use 'cwd' from hook payload (not 'project_path' which doesn't exist)
    project_path = Path(input_data.get('cwd', '.'))

    # Build output for Claude Code
    output: dict[str, list[dict[str, str]]] = {
        "additionalContext": []
    }

    tags_injected = False

    # Inject TAGs from Elle's context (technical only, with quality filtering)
    try:
        injector = TagInjector(
            technical_only=True,
            top_k=6,  # Limit to 6 high-value TAGs
            project_path=str(project_path) if project_path else None,
        )
        enhanced_prompt = injector.inject(user_prompt)
        tags_injected = enhanced_prompt != user_prompt

        # Add TAGs summary if any were found
        if tags_injected:
            # Extract TAGs section (everything before the original prompt)
            # TAGs section ends with double newline before the user prompt
            parts = enhanced_prompt.rsplit('\n\n', 1)
            tag_content = parts[0] if len(parts) > 1 else enhanced_prompt
            output["additionalContext"].append({
                "name": "TAGs Context",
                "description": "Semantic context from Elle's memory",
                "content": tag_content
            })
    except Exception as e:
        action, message = fallback_manager.handle_failure('UserPromptSubmit', e)
        # Continue without TAGs on failure

    # NOTE: EvidenceCLI validation removed - now runs once in SessionStart (health-check.py)
    # This saves ~200ms per message (P1 fix)

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

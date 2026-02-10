"""
TAGs System Module

Injects semantic context markers into prompts.
Pattern from: Skills-Fabrik prompt-builder-v2.ts

TAGs are context annotations with format: [TYPE:category] value

Types:
- K: Knowledge (facts about user, projects, relationships)
- C: Constraint (limitations, rules, preferences)
- U: Usage (how user prefers to work)
- EVIDENCIA: Evidence/proof statements
- PROPUESTA: Proposals/suggestions
- INTERNAL: Internal notes
- EXTERNAL: External context
"""

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
import re
from typing import Literal, cast


class TagType(Enum):
    """TAG types for semantic context."""
    KNOWLEDGE = "K"
    CONSTRAINT = "C"
    USAGE = "U"
    EVIDENCIA = "EVIDENCIA"
    PROPUESTA = "PROPUESTA"
    INTERNAL = "INTERNAL"
    EXTERNAL = "EXTERNAL"


@dataclass(frozen=True)
class PromptTag:
    """A single TAG annotation."""
    type: Literal['K', 'C', 'U', 'EVIDENCIA', 'PROPUESTA', 'INTERNAL', 'EXTERNAL']
    category: str
    value: str

    def format(self) -> str:
        """Format TAG as string."""
        return f"[{self.type}:{self.category}] {self.value}"


class TagExtractor:
    """Extract TAGs from context files."""

    # Patterns for extracting content from context files
    PATTERNS = {
        "identity": [
            (r"###?\s*Identity\s*\n+(.*?)(?=###|\n\n|\Z)", "K:identity"),
        ],
        "projects": [
            (r"###?\s*Projects\s*\n+(.*?)(?=###|\n\n|\Z)", "K:projects"),
        ],
        "relationships": [
            (r"###?\s*Relationships\s*\n+(.*?)(?=###|\n\n|\Z)", "K:relationships"),
        ],
        "rules": [
            (r"##?\s*Rules\s*\n+(.*?)(?=##|\Z)", "U:rules"),
        ],
        "preferences": [
            (r"###?\s*Preferences\s*\n+(.*?)(?=###|\n\n|\Z)", "U:preferences"),
        ],
        "triggers": [
            (r"###?\s*Triggers\s*\n+(.*?)(?=###|\n\n|\Z)", "C:triggers"),
        ],
        "constraints": [
            (r"###?\s*Constraints\s*\n+(.*?)(?=###|\n\n|\Z)", "C:constraints"),
        ],
    }

    def __init__(self, context_dir: Path | None = None):
        """
        Initialize TAG extractor.

        Args:
            context_dir: Path to Claude context directory. Defaults to ~/.claude/.context
        """
        self.context_dir = context_dir or Path.home() / ".claude" / ".context"

    def extract_from_file(self, file_path: Path) -> list[PromptTag]:
        """Extract TAGs from a specific context file."""
        tags: list[PromptTag] = []

        if not file_path.exists():
            return tags

        try:
            content = file_path.read_text()

            # Try each pattern
            for section_name, patterns in self.PATTERNS.items():
                for pattern, tag_prefix in patterns:
                    matches = re.findall(pattern, content, re.DOTALL | re.MULTILINE)
                    for match in matches:
                        # Clean up the matched content
                        value = match.strip()
                        # Take first line or first few words for brevity
                        lines = value.split('\n')
                        summary = lines[0][:100] if lines else value[:100]
                        if len(summary) < len(value):
                            summary += "..."

                        tag_type, category = tag_prefix.split(':')
                        # Validate tag_type against allowed literal values
                        valid_types = ('K', 'C', 'U', 'EVIDENCIA', 'PROPUESTA', 'INTERNAL', 'EXTERNAL')
                        if tag_type not in valid_types:
                            tag_type = 'K'  # Default to Knowledge type
                        # Cast to Literal type for mypy - runtime validation ensures safety
                        valid_tag_type: Literal['K', 'C', 'U', 'EVIDENCIA', 'PROPUESTA', 'INTERNAL', 'EXTERNAL'] = cast(
                            Literal['K', 'C', 'U', 'EVIDENCIA', 'PROPUESTA', 'INTERNAL', 'EXTERNAL'],
                            tag_type
                        )
                        tags.append(PromptTag(
                            type=valid_tag_type,
                            category=section_name,
                            value=summary
                        ))

        except (OSError, PermissionError, UnicodeDecodeError) as e:
            # Log but don't break session if TAG extraction fails
            import logging
            logging.warning(f"TAG extraction failed for {file_path}: {e}")

        return tags

    def extract_all(self) -> list[PromptTag]:
        """Extract TAGs from all context files."""
        tags = []

        # Standard context files to scan
        context_files = [
            "CLAUDE.md",
            "identity.md",
            "projects.md",
            "relationships.md",
            "preferences.md",
            "rules.md",
        ]

        for filename in context_files:
            file_path = self.context_dir / filename
            tags.extend(self.extract_from_file(file_path))

        return tags

    def format_tags_for_prompt(self, tags: list[PromptTag]) -> str:
        """Format TAGs for injection into prompt."""
        if not tags:
            return ""

        lines = ["## Context Tags\n"]
        for tag in tags:
            lines.append(f"{tag.format()}")

        return "\n".join(lines)


class TagInjector:
    """Injects TAGs into user prompts."""

    def __init__(self, extractor: TagExtractor | None = None):
        """
        Initialize TAG injector.

        Args:
            extractor: TagExtractor instance. Creates default if None.
        """
        self.extractor = extractor or TagExtractor()

    def inject(self, prompt: str) -> str:
        """
        Inject TAGs into prompt.

        Args:
            prompt: Original user prompt

        Returns:
            Prompt with TAGs prepended
        """
        tags = self.extractor.extract_all()

        if not tags:
            return prompt

        tag_block = self.extractor.format_tags_for_prompt(tags)

        # Insert TAGs at the beginning of prompt
        return f"{tag_block}\n\n{prompt}"

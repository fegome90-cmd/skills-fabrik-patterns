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
from functools import total_ordering
import hashlib
import logging
from pathlib import Path
import re
from typing import Literal, cast


# Configure module logger
logger = logging.getLogger(__name__)


class TagType(Enum):
    """TAG types for semantic context."""
    KNOWLEDGE = "K"
    CONSTRAINT = "C"
    USAGE = "U"
    EVIDENCIA = "EVIDENCIA"
    PROPUESTA = "PROPUESTA"
    INTERNAL = "INTERNAL"
    EXTERNAL = "EXTERNAL"


# Categories to include for technical context injection
TECHNICAL_CATEGORIES: frozenset[str] = frozenset({
    "tech_identity",   # Technical Identity - Scope Rule, Clean Arch, TDD
    "projects",        # Active Projects
    "rules",           # Coding rules
    "rules_critical",  # CRITICAL priority rules
    "rules_high",      # HIGH priority rules
    "workflows",       # Active Workflows
})

# Categories to skip (personal/temporal)
SKIP_CATEGORIES: frozenset[str] = frozenset({
    "identity",        # Personal identity (name, pets, location)
    "goals",           # Personal goals
    "relationships",   # Professional network
    "preferences",     # Communication style
    "triggers",        # Important dates, deadlines
    "constraints",     # Scheduling constraints
    "challenges",      # Current challenges
})

# Ranking keywords - boost score if content contains these
HIGH_VALUE_KEYWORDS: frozenset[str] = frozenset({
    # Architecture patterns
    "scope rule", "clean architecture", "tdd", "test-driven", "fail-closed",
    "ssot", "single source of truth", "immutable", "pure function",
    # Workflow keywords
    "work order", "ctx", "trifecta", "gates", "evidence", "validation",
    # Quality keywords
    "must", "should", "never", "always", "critical", "required",
    # Tech stack
    "python", "typescript", "react", "postgresql", "docker",
})

# Default limits for technical context
DEFAULT_TOP_K = 6
DEFAULT_MIN_CHARS = 50


# =============================================================================
# QUALITY FILTER FUNCTIONS (Pure, Unit-Testable)
# =============================================================================

def normalize(text: str) -> str:
    """Normalize text for comparison: lowercase, collapse whitespace."""
    return re.sub(r'\s+', ' ', text.lower().strip())


def content_hash(text: str) -> str:
    """Generate stable hash for deduplication."""
    normalized = normalize(text)
    return hashlib.sha256(normalized.encode()).hexdigest()[:12]


def is_header_only(text: str) -> bool:
    """
    Detect if text is only markdown headers (## or ###) with no actual content.

    Examples:
        "### Some Header" -> True
        "### Header\\nSome content" -> False
        "## Section\\n### Subsection" -> True (only headers)
    """
    lines = [line.strip() for line in text.strip().split('\n') if line.strip()]
    if not lines:
        return True

    # Check if ALL non-empty lines are headers
    header_pattern = re.compile(r'^(#{1,6})\s+\S')
    return all(header_pattern.match(line) for line in lines)


def is_empty_markdown_table(text: str) -> bool:
    """
    Detect if text contains only a markdown table header with no data rows.

    A markdown table has:
    - Header row: | Col1 | Col2 |
    - Separator row: |------|------|
    - Data rows: | val1 | val2 |

    Empty = only header + separator, no data rows.
    """
    lines = [line.strip() for line in text.strip().split('\n') if line.strip()]
    if len(lines) < 2:
        return False

    # Check if we have table-like structure
    table_lines = [line for line in lines if line.startswith('|') and line.endswith('|')]

    if len(table_lines) < 2:
        return False

    # Check for separator row (contains only |, -, :, spaces)
    separator_pattern = re.compile(r'^[\|:\-\s]+$')

    # Count non-separator table rows (these would be data rows)
    data_rows = [line for line in table_lines if not separator_pattern.match(line)]

    # If only 1 non-separator row (the header), table is empty
    return len(data_rows) <= 1


def has_minimum_content(text: str, min_chars: int = DEFAULT_MIN_CHARS) -> bool:
    """Check if text has minimum useful content length (excluding markdown syntax)."""
    # Strip markdown syntax for counting
    stripped = re.sub(r'[#*\-_`|>\[\]]', '', text)
    stripped = re.sub(r'\s+', ' ', stripped).strip()
    return len(stripped) >= min_chars


def calculate_info_density(text: str) -> float:
    """
    Calculate information density score (0.0 to 1.0+).

    Higher score = more dense, useful content.
    Considers:
    - Presence of high-value keywords
    - Ratio of content vs markdown syntax
    - Presence of lists/bullets (structured info)
    """
    score = 0.0
    normalized = normalize(text)

    # Keyword bonuses
    for keyword in HIGH_VALUE_KEYWORDS:
        if keyword in normalized:
            score += 0.15

    # Bullet/list bonus (indicates structured, actionable info)
    bullet_count = len(re.findall(r'^[\*\-\+]\s+', text, re.MULTILINE))
    score += min(bullet_count * 0.05, 0.3)  # Cap at 0.3

    # Penalize markdown-heavy content
    syntax_chars = len(re.findall(r'[#*\-_`|>\[\]]', text))
    content_chars = len(re.sub(r'[#*\-_`|>\[\]\s]', '', text))
    if content_chars > 0:
        syntax_ratio = syntax_chars / content_chars
        if syntax_ratio > 0.3:  # More than 30% syntax
            score -= 0.2

    # Penalize tables (often less dense than prose)
    if '|' in text:
        score -= 0.1

    return max(score, 0.0)


def calculate_tag_score(tag: 'PromptTag', project_path: str | None = None) -> float:
    """
    Calculate overall score for a TAG (used for ranking).

    Args:
        tag: The PromptTag to score
        project_path: Optional project path for relevance boosting

    Returns:
        Float score (higher = more valuable)
    """
    score = 0.0

    # Category priority (rules and tech_identity are most valuable)
    category_scores = {
        "rules_critical": 2.0,
        "rules_high": 1.8,
        "rules": 1.5,
        "tech_identity": 1.4,
        "workflows": 1.2,
        "projects": 1.0,
    }
    score += category_scores.get(tag.category, 0.5)

    # Information density
    score += calculate_info_density(tag.value)

    # Project relevance boost
    if project_path:
        normalized_path = normalize(project_path)
        if normalized_path in normalize(tag.value):
            score += 0.5

    return score


@dataclass(frozen=True)
class PromptTag:
    """A single TAG annotation."""
    type: Literal['K', 'C', 'U', 'EVIDENCIA', 'PROPUESTA', 'INTERNAL', 'EXTERNAL']
    category: str
    value: str

    def format(self) -> str:
        """Format TAG as string."""
        return f"[{self.type}:{self.category}] {self.value}"


@dataclass
@total_ordering
class ScoredTag:
    """A TAG with its quality score for ranking."""
    tag: PromptTag
    score: float
    discard_reason: str | None = None

    def __lt__(self, other: 'ScoredTag') -> bool:
        if not isinstance(other, ScoredTag):
            return NotImplemented
        # Sort by score descending, then by formatted tag for determinism
        if self.score != other.score:
            return self.score < other.score
        return self.tag.format() < other.tag.format()

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, ScoredTag):
            return NotImplemented
        return self.score == other.score and self.tag.format() == other.tag.format()


class TagExtractor:
    """Extract TAGs from context files."""

    # Patterns for extracting content from context files
    # Updated to match actual section headers in ~/.claude/.context/core/ files
    # Note: Lookahead uses (?=\n##\s|\Z) to match only ## headers, not ### subsections
    DEFAULT_PATTERNS = {
        "identity": [
            # Match all identity-related sections (actual headers in identity.md)
            (r"##\s*Basic Info\s*\n+(.*?)(?=\n##\s|\Z)", "K:identity"),
            (r"##\s*Personal Life\s*\n+(.*?)(?=\n##\s|\Z)", "K:identity"),
            (r"##\s*Professional\s*\n+(.*?)(?=\n##\s|\Z)", "K:identity"),
            (r"##\s*Goals\s*&\s*Aspirations\s*\n+(.*?)(?=\n##\s|\Z)", "K:goals"),
            (r"##\s*Technical Identity\s*\n+(.*?)(?=\n##\s|\Z)", "K:tech_identity"),
            (r"##\s*Current Challenges\s*\n+(.*?)(?=\n##\s|\Z)", "C:challenges"),
            # Legacy patterns for backward compatibility
            (r"##\s*Identity\s*\n+(.*?)(?=\n##\s|\Z)", "K:identity"),
        ],
        "projects": [
            (r"##\s*Active Projects\s*\n+(.*?)(?=\n##\s|\Z)", "K:projects"),
            (r"##\s*Projects\s*\n+(.*?)(?=\n##\s|\Z)", "K:projects"),
        ],
        "relationships": [
            (r"##\s*Professional Network\s*\n+(.*?)(?=\n##\s|\Z)", "K:relationships"),
            (r"##\s*Relationships\s*\n+(.*?)(?=\n##\s|\Z)", "K:relationships"),
        ],
        "rules": [
            # Rules file uses emoji-prefixed sections like ## 🔴 CRITICAL
            (r"##\s*[🔴🟠🟡].*?\s*\n+(.*?)(?=\n##\s*[🔴🟠🟢🟡]|\Z)", "U:rules"),
            (r"##\s*Rules\s*\n+(.*?)(?=\n##\s|\Z)", "U:rules"),
            (r"##\s*[🔴].*?CRITICAL.*?\s*\n+(.*?)(?=\n##\s*[🔴🟠🟡]|\Z)", "U:rules_critical"),
            (r"##\s*[🟠].*?HIGH.*?\s*\n+(.*?)(?=\n##\s*[🔴🟠🟡]|\Z)", "U:rules_high"),
        ],
        "preferences": [
            (r"##\s*Communication\s*\n+(.*?)(?=\n##\s|\Z)", "U:preferences"),
            (r"##\s*Working Style\s*\n+(.*?)(?=\n##\s|\Z)", "U:preferences"),
            (r"##\s*Decision-Making\s*\n+(.*?)(?=\n##\s|\Z)", "U:preferences"),
            (r"##\s*Preferences\s*\n+(.*?)(?=\n##\s|\Z)", "U:preferences"),
        ],
        "triggers": [
            (r"##\s*Important Dates\s*\n+(.*?)(?=\n##\s|\Z)", "C:triggers"),
            (r"##\s*Upcoming Deadlines\s*\n+(.*?)(?=\n##\s|\Z)", "C:triggers"),
            (r"##\s*Situational Triggers\s*\n+(.*?)(?=\n##\s|\Z)", "C:triggers"),
            (r"##\s*Periodic Check-Ins\s*\n+(.*?)(?=\n##\s|\Z)", "C:triggers"),
            (r"##\s*Triggers\s*\n+(.*?)(?=\n##\s|\Z)", "C:triggers"),
            # Legacy patterns with ### (subsection level)
            (r"###\s*Triggers\s*\n+(.*?)(?=##|\Z)", "C:triggers"),
        ],
        "constraints": [
            (r"##\s*Scheduling & Time\s*\n+(.*?)(?=\n##\s|\Z)", "C:constraints"),
            (r"##\s*Constraints\s*\n+(.*?)(?=\n##\s|\Z)", "C:constraints"),
        ],
        "workflows": [
            (r"##\s*Active Workflows\s*\n+(.*?)(?=\n##\s|\Z)", "U:workflows"),
            (r"##\s*Workflows\s*\n+(.*?)(?=\n##\s|\Z)", "U:workflows"),
        ],
    }

    def __init__(
        self,
        context_dir: Path | None = None,
        patterns: dict[str, list[tuple[str, str]]] | None = None,
        allowed_categories: set[str] | None = None,
        top_k: int = DEFAULT_TOP_K,
        min_chars: int = DEFAULT_MIN_CHARS,
        project_path: str | None = None,
        debug: bool = False,
    ):
        """
        Initialize TAG extractor.

        Args:
            context_dir: Path to Claude context directory.
                        Defaults to ~/.claude/.context/core (with fallback to ~/.claude/.context)
            patterns: Optional custom patterns dict to override defaults.
            allowed_categories: Set of categories to include. If None, includes all categories.
            top_k: Maximum number of TAGs to return after ranking.
            min_chars: Minimum characters for useful content.
            project_path: Optional project path for relevance boosting.
            debug: If True, log discard reasons.
        """
        if context_dir:
            self.context_dir = context_dir
        else:
            # Try core/ subdirectory first (new Elle structure)
            core_dir = Path.home() / ".claude" / ".context" / "core"
            legacy_dir = Path.home() / ".claude" / ".context"
            self.context_dir = core_dir if core_dir.exists() else legacy_dir

        self.PATTERNS = patterns or self.DEFAULT_PATTERNS
        self.allowed_categories = allowed_categories
        self.top_k = top_k
        self.min_chars = min_chars
        self.project_path = project_path
        self.debug = debug

    def _apply_quality_filters(self, raw_value: str) -> tuple[str, str | None]:
        """
        Apply quality filters to extracted content.

        Returns:
            Tuple of (cleaned_value, discard_reason or None)
        """
        # Filter out <guide> tags and empty lines
        lines = raw_value.split('\n')
        content_lines = []
        for line in lines:
            stripped = line.strip()
            if not stripped:
                continue
            if stripped.startswith('<guide>') or stripped.startswith('</guide>'):
                continue
            if stripped.startswith('<format>') or stripped.startswith('</format>'):
                continue
            content_lines.append(stripped)

        # Skip sections with no actual content
        if not content_lines:
            return "", "empty-content"

        # Reconstruct cleaned value
        cleaned = '\n'.join(content_lines)

        # Quality filter 1: Header-only content
        if is_header_only(cleaned):
            return "", "header-only"

        # Quality filter 2: Empty markdown table
        if is_empty_markdown_table(cleaned):
            return "", "empty-table"

        # Quality filter 3: Minimum content length
        if not has_minimum_content(cleaned, self.min_chars):
            return "", f"too-short (<{self.min_chars} chars)"

        return cleaned, None

    def _create_summary(self, cleaned_value: str, category: str) -> str:
        """
        Create a meaningful summary from cleaned content.

        For tables: extract first data row, not header.
        For lists: take first bullet points.
        For prose: take first meaningful sentence.
        For headers: skip to actual content.
        """
        lines = cleaned_value.split('\n')

        # For tables, skip ALL header rows and get first actual data row
        if '|' in lines[0]:
            separator_pattern = re.compile(r'^[\|:\-\s]+$')
            # Heuristic: a header row contains only simple words, a data row has:
            # - paths (/, ~), backticks, parentheses, special chars, or long text
            def is_likely_header(line: str) -> bool:
                """Check if line looks like a table header (not data)."""
                # Has backticks, paths, or parentheses = data
                if '`' in line or '/' in line or '(' in line:
                    return False
                # Has markdown formatting = data
                if '**' in line or '_' in line:
                    return False
                # Very short cells with only simple words = likely header
                cells = [c.strip() for c in line.split('|') if c.strip()]
                if not cells:
                    return True
                # Check if all cells are short, simple words
                simple_cells = [c for c in cells if len(c) <= 20 and c.replace(' ', '').isalnum()]
                return len(simple_cells) == len(cells)

            for line in lines:
                if '|' not in line:
                    continue
                if separator_pattern.match(line):
                    continue
                if is_likely_header(line):
                    continue
                # Found a data row!
                cells = [c.strip() for c in line.split('|') if c.strip()]
                if cells:
                    meaningful = [c[:35] for c in cells[:3] if c]
                    if meaningful:
                        return ' | '.join(meaningful) + "..."

        # Skip markdown headers at the start - look for actual content
        header_pattern = re.compile(r'^#{1,6}\s+')
        for line in lines:
            if header_pattern.match(line):
                continue
            # Found non-header line - use it as summary
            summary = line[:100]
            if len(summary) < len(line):
                summary += "..."
            return summary

        # If all lines were headers, return the first header (shouldn't happen after quality filters)
        first_line = lines[0][:100]
        if len(first_line) < len(lines[0]):
            return first_line + "..."
        return first_line

    def extract_from_file(self, file_path: Path) -> list[ScoredTag]:
        """Extract TAGs from a specific context file with quality filtering."""
        scored_tags: list[ScoredTag] = []

        if not file_path.exists():
            return scored_tags

        try:
            content = file_path.read_text()
            seen_hashes: set[str] = set()

            # Try each pattern
            for section_name, patterns in self.PATTERNS.items():
                for pattern, tag_prefix in patterns:
                    matches = re.findall(pattern, content, re.DOTALL | re.MULTILINE)
                    for match in matches:
                        raw_value = match.strip()

                        # Apply quality filters
                        cleaned_value, discard_reason = self._apply_quality_filters(raw_value)

                        if discard_reason:
                            logger.debug(f"Discarded tag from {file_path.name}: {discard_reason}")
                            continue

                        tag_type, category = tag_prefix.split(':')

                        # Skip if not in allowed categories (when filter is active)
                        if self.allowed_categories is not None:
                            if category not in self.allowed_categories:
                                logger.debug(f"Discarded tag: category '{category}' not allowed")
                                continue

                        # Create meaningful summary
                        summary = self._create_summary(cleaned_value, category)

                        # Deduplicate by content hash
                        tag_hash = content_hash(summary)
                        if tag_hash in seen_hashes:
                            logger.debug(f"Discarded tag: duplicate content")
                            continue
                        seen_hashes.add(tag_hash)

                        # Default unknown tag types to 'K' (Knowledge)
                        # Patterns define valid prefixes, so this is just a safety fallback
                        if tag_type not in ('K', 'C', 'U', 'EVIDENCIA', 'PROPUESTA', 'INTERNAL', 'EXTERNAL'):
                            tag_type = 'K'

                        tag = PromptTag(
                            type=cast(Literal['K', 'C', 'U', 'EVIDENCIA', 'PROPUESTA', 'INTERNAL', 'EXTERNAL'], tag_type),
                            category=category,
                            value=summary
                        )

                        score = calculate_tag_score(tag, self.project_path)
                        scored_tags.append(ScoredTag(tag=tag, score=score))

        except (OSError, PermissionError, UnicodeDecodeError) as e:
            logger.warning(f"TAG extraction failed for {file_path}: {e}")

        return scored_tags

    def extract_all(self) -> list[PromptTag]:
        """
        Extract TAGs from all context files with ranking and top_k limiting.

        Returns deterministic list sorted by score (descending) then by formatted tag.
        """
        all_scored: list[ScoredTag] = []

        # Standard context files in core/ directory
        context_files = [
            "identity.md",
            "preferences.md",
            "projects.md",
            "relationships.md",
            "rules.md",
            "triggers.md",
            "workflows.md",
        ]

        for filename in context_files:
            file_path = self.context_dir / filename
            all_scored.extend(self.extract_from_file(file_path))

        # Sort by score descending (using negative for descending), then by tag for determinism
        # Python's sort is stable, so equal scores maintain order
        all_scored.sort(key=lambda st: (-st.score, st.tag.format()))

        # Apply top_k limit
        top_scored = all_scored[:self.top_k]

        # Log summary if debug
        if self.debug and len(all_scored) > self.top_k:
            logger.debug(f"Ranked {len(all_scored)} tags, keeping top {self.top_k}")
            for st in all_scored[self.top_k:]:
                logger.debug(f"  Discarded (low score): {st.tag.format()} (score={st.score:.2f})")

        return [st.tag for st in top_scored]

    def format_tags_for_prompt(self, tags: list[PromptTag]) -> str:
        """Format TAGs for injection into prompt."""
        if not tags:
            return ""

        lines = ["## Context Tags\n"]
        for tag in tags:
            lines.append(f"{tag.format()}")

        return "\n".join(lines)


class TagInjector:
    """Injects TAGs into user prompts with quality filtering and ranking."""

    def __init__(
        self,
        extractor: TagExtractor | None = None,
        technical_only: bool = True,
        top_k: int = DEFAULT_TOP_K,
        min_chars: int = DEFAULT_MIN_CHARS,
        project_path: str | None = None,
        debug: bool = False,
    ):
        """
        Initialize TAG injector.

        Args:
            extractor: TagExtractor instance. Creates default if None.
            technical_only: If True, only inject technical context (tech_identity,
                           projects, rules, workflows). Default: True.
            top_k: Maximum number of TAGs to inject. Default: 6.
            min_chars: Minimum characters for useful content. Default: 50.
            project_path: Optional project path for relevance boosting.
            debug: If True, log discard reasons to DEBUG level.
        """
        if extractor is None:
            allowed = TECHNICAL_CATEGORIES if technical_only else None
            extractor = TagExtractor(
                allowed_categories=allowed,
                top_k=top_k,
                min_chars=min_chars,
                project_path=project_path,
                debug=debug,
            )
        self.extractor = extractor

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

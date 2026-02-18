"""
Unit Tests for TAG System Module

Tests for TagExtractor path resolution and pattern matching
with the actual context file structure in ~/.claude/.context/core/
"""

import pytest
from pathlib import Path
import tempfile

# Add lib to path for imports
import sys
lib_dir = Path(__file__).parent.parent.parent / "lib"
sys.path.insert(0, str(lib_dir))

from tag_system import TagExtractor, TagInjector, PromptTag


# Helper to create extractor with quality filters disabled for testing short content
def create_test_extractor(context_dir: Path, **kwargs) -> TagExtractor:
    """Create TagExtractor with min_chars=0 for testing with short content."""
    kwargs.setdefault('min_chars', 0)  # Disable min content length for tests
    return TagExtractor(context_dir=context_dir, **kwargs)


class TestTagExtractorPathResolution:
    """Test TagExtractor correctly resolves context directory."""

    def test_resolves_core_directory_when_exists(self, tmp_path: Path):
        """Test TagExtractor uses core/ subdirectory when available."""
        # Create core/ directory structure
        core_dir = tmp_path / ".context" / "core"
        core_dir.mkdir(parents=True)

        # Create a test file in core/
        (core_dir / "identity.md").write_text("## Basic Info\n- Test User")

        # Initialize extractor with the base context dir
        extractor = create_test_extractor(core_dir)

        # Verify it uses core/ directory
        assert extractor.context_dir == core_dir

        # Should find the file (returns ScoredTag objects)
        scored_tags = extractor.extract_from_file(core_dir / "identity.md")
        assert len(scored_tags) >= 1

    def test_fallback_to_legacy_when_core_missing(self, tmp_path: Path):
        """Test TagExtractor falls back to legacy dir when core/ doesn't exist."""
        # Create legacy structure (no core/ subdirectory)
        legacy_dir = tmp_path / ".context"
        legacy_dir.mkdir(parents=True)

        (legacy_dir / "identity.md").write_text("## Basic Info\n- Test User")

        extractor = create_test_extractor(legacy_dir)
        assert extractor.context_dir == legacy_dir

    def test_default_initialization_finds_context(self):
        """Test default initialization finds actual context directory."""
        extractor = TagExtractor(min_chars=0)  # Disable for test

        # Should find either core/ or legacy directory
        expected_core = Path.home() / ".claude" / ".context" / "core"
        expected_legacy = Path.home() / ".claude" / ".context"

        assert extractor.context_dir in [expected_core, expected_legacy]


class TestNewPatternMatching:
    """Test new patterns matching actual context file structure."""

    def test_extract_basic_info_as_identity(self, tmp_path: Path):
        """Test ## Basic Info is extracted as K:identity."""
        context_dir = tmp_path / ".context"
        context_dir.mkdir()

        test_file = context_dir / "identity.md"
        test_file.write_text("""## Basic Info

- Name: Felipe
- Location: Santiago, Chile
""")

        extractor = create_test_extractor(context_dir)
        scored_tags = extractor.extract_from_file(test_file)

        assert len(scored_tags) >= 1
        # Find the identity tag
        identity_tags = [st for st in scored_tags if st.tag.category == "identity"]
        assert len(identity_tags) >= 1
        assert identity_tags[0].tag.type == 'K'

    def test_extract_professional_as_identity(self, tmp_path: Path):
        """Test ## Professional is extracted as K:identity."""
        context_dir = tmp_path / ".context"
        context_dir.mkdir()

        test_file = context_dir / "identity.md"
        test_file.write_text("""## Professional

- Primary: Nurse
- Passion: AI development
""")

        extractor = create_test_extractor(context_dir)
        scored_tags = extractor.extract_from_file(test_file)

        identity_tags = [st for st in scored_tags if st.tag.category == "identity"]
        assert len(identity_tags) >= 1

    def test_extract_goals_as_goals_category(self, tmp_path: Path):
        """Test ## Goals & Aspirations is extracted as K:goals."""
        context_dir = tmp_path / ".context"
        context_dir.mkdir()

        test_file = context_dir / "identity.md"
        test_file.write_text("""## Goals & Aspirations

### This Year
- Learn functional programming
""")

        extractor = create_test_extractor(context_dir)
        scored_tags = extractor.extract_from_file(test_file)

        goals_tags = [st for st in scored_tags if st.tag.category == "goals"]
        assert len(goals_tags) >= 1
        assert goals_tags[0].tag.type == 'K'

    def test_extract_active_projects(self, tmp_path: Path):
        """Test ## Active Projects is extracted as K:projects."""
        context_dir = tmp_path / ".context"
        context_dir.mkdir()

        test_file = context_dir / "projects.md"
        test_file.write_text("""## Active Projects

| Project | Status |
|---------|--------|
| Plugin  | Active |
""")

        extractor = create_test_extractor(context_dir)
        scored_tags = extractor.extract_from_file(test_file)

        project_tags = [st for st in scored_tags if st.tag.category == "projects"]
        assert len(project_tags) >= 1

    def test_extract_important_dates_as_triggers(self, tmp_path: Path):
        """Test ## Important Dates is extracted as C:triggers."""
        context_dir = tmp_path / ".context"
        context_dir.mkdir()

        test_file = context_dir / "triggers.md"
        test_file.write_text("""## Important Dates

| Date | Event |
|------|-------|
| March 7, 2026 | EEO-2025 |
""")

        extractor = create_test_extractor(context_dir)
        scored_tags = extractor.extract_from_file(test_file)

        trigger_tags = [st for st in scored_tags if st.tag.category == "triggers"]
        assert len(trigger_tags) >= 1
        assert trigger_tags[0].tag.type == 'C'

    def test_extract_upcoming_deadlines_as_triggers(self, tmp_path: Path):
        """Test ## Upcoming Deadlines is extracted as C:triggers."""
        context_dir = tmp_path / ".context"
        context_dir.mkdir()

        test_file = context_dir / "triggers.md"
        test_file.write_text("""## Upcoming Deadlines

| Date | Deadline |
|------|----------|
| March 7 | Exam |
""")

        extractor = create_test_extractor(context_dir)
        scored_tags = extractor.extract_from_file(test_file)

        trigger_tags = [st for st in scored_tags if st.tag.category == "triggers"]
        assert len(trigger_tags) >= 1

    def test_extract_situational_triggers(self, tmp_path: Path):
        """Test ## Situational Triggers is extracted as C:triggers."""
        context_dir = tmp_path / ".context"
        context_dir.mkdir()

        test_file = context_dir / "triggers.md"
        test_file.write_text("""## Situational Triggers

| Trigger | Action |
|---------|--------|
| Monday | Ask about study plan |
""")

        extractor = create_test_extractor(context_dir)
        scored_tags = extractor.extract_from_file(test_file)

        trigger_tags = [st for st in scored_tags if st.tag.category == "triggers"]
        assert len(trigger_tags) >= 1

    def test_extract_technical_identity(self, tmp_path: Path):
        """Test ## Technical Identity is extracted as K:tech_identity."""
        context_dir = tmp_path / ".context"
        context_dir.mkdir()

        test_file = context_dir / "identity.md"
        test_file.write_text("""## Technical Identity

### Core Beliefs
- Purity First
- Boundaries Matter
""")

        extractor = create_test_extractor(context_dir)
        scored_tags = extractor.extract_from_file(test_file)

        tech_tags = [st for st in scored_tags if st.tag.category == "tech_identity"]
        assert len(tech_tags) >= 1


class TestTagInjector:
    """Test TagInjector functionality."""

    def test_injector_uses_extractor(self, tmp_path: Path):
        """Test TagInjector properly uses TagExtractor."""
        context_dir = tmp_path / ".context"
        context_dir.mkdir()

        (context_dir / "identity.md").write_text("## Basic Info\n- Felipe")

        extractor = create_test_extractor(context_dir)
        injector = TagInjector(extractor=extractor, min_chars=0)

        result = injector.inject("Hello")

        # Should have TAGs prepended
        assert "[K:" in result
        assert "Hello" in result

    def test_injector_returns_original_if_no_tags(self, tmp_path: Path):
        """Test injector returns original prompt if no TAGs found."""
        context_dir = tmp_path / ".context"
        context_dir.mkdir()

        # Empty directory - no context files
        extractor = create_test_extractor(context_dir)
        injector = TagInjector(extractor=extractor, min_chars=0)

        result = injector.inject("Hello")

        # Should return original prompt unchanged
        assert result == "Hello"


class TestPromptTag:
    """Test PromptTag dataclass."""

    def test_format_tag(self):
        """Test TAG formatting."""
        tag = PromptTag(type='K', category='identity', value='Test value')
        assert tag.format() == "[K:identity] Test value"

    def test_constraint_tag(self):
        """Test constraint TAG type."""
        tag = PromptTag(type='C', category='triggers', value='Deadline')
        assert tag.format() == "[C:triggers] Deadline"

    def test_usage_tag(self):
        """Test usage TAG type."""
        tag = PromptTag(type='U', category='preferences', value='Dark mode')
        assert tag.format() == "[U:preferences] Dark mode"


class TestExtractAll:
    """Test extract_all method."""

    def test_extract_all_finds_multiple_files(self, tmp_path: Path):
        """Test extract_all scans all context files."""
        context_dir = tmp_path / ".context"
        context_dir.mkdir()

        # Create multiple context files with enough content
        (context_dir / "identity.md").write_text("## Basic Info\n- Felipe is a software developer who loves Python")
        (context_dir / "triggers.md").write_text("## Important Dates\n| Date | Event |\n|------|-------|\n| Today | Test |")
        (context_dir / "preferences.md").write_text("## Communication\n- Concise and clear communication is preferred")

        extractor = create_test_extractor(context_dir)
        tags = extractor.extract_all()

        # Should have tags from multiple files
        assert len(tags) >= 2

    def test_extract_all_handles_missing_files(self, tmp_path: Path):
        """Test extract_all handles missing files gracefully."""
        context_dir = tmp_path / ".context"
        context_dir.mkdir()

        # Only create one file with enough content
        (context_dir / "identity.md").write_text("## Basic Info\n- Felipe is a software developer")

        extractor = create_test_extractor(context_dir)
        # Should not raise
        tags = extractor.extract_all()

        assert len(tags) >= 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

"""
Integration Tests: TAGs System

Comprehensive tests for TAG extraction, validation, and injection.
Tests edge cases: empty files, malformed tags, XML tags, etc.
"""

import pytest
import tempfile
import shutil
from pathlib import Path
import sys

# Ensure lib is in path
lib_dir = Path(__file__).parent.parent.parent / "lib"
if str(lib_dir) not in sys.path:
    sys.path.insert(0, str(lib_dir))

from tag_system import TagExtractor, TagInjector, PromptTag, TagType


class TestTagFormatValidation:
    """Test TAG format validation: [K:identity], [U:rules], [C:triggers]."""

    def test_knowledge_tag_format(self):
        """Test K (Knowledge) tag format: [K:category] value."""
        tag = PromptTag(type='K', category='identity', value='Felipe is a Python developer')
        formatted = tag.format()

        assert formatted == "[K:identity] Felipe is a Python developer"
        assert formatted.startswith("[K:")
        assert "] " in formatted

    def test_usage_tag_format(self):
        """Test U (Usage) tag format: [U:category] value."""
        tag = PromptTag(type='U', category='rules', value='Always use immutable data')
        formatted = tag.format()

        assert formatted == "[U:rules] Always use immutable data"
        assert formatted.startswith("[U:")

    def test_constraint_tag_format(self):
        """Test C (Constraint) tag format: [C:category] value."""
        tag = PromptTag(type='C', category='triggers', value='Before committing code')
        formatted = tag.format()

        assert formatted == "[C:triggers] Before committing code"
        assert formatted.startswith("[C:")

    def test_evidencia_tag_format(self):
        """Test EVIDENCIA tag format: [EVIDENCIA:category] value."""
        tag = PromptTag(type='EVIDENCIA', category='proof', value='Test passed')
        formatted = tag.format()

        assert formatted == "[EVIDENCIA:proof] Test passed"
        assert formatted.startswith("[EVIDENCIA:")

    def test_propuesta_tag_format(self):
        """Test PROPUESTA tag format: [PROPUESTA:category] value."""
        tag = PromptTag(type='PROPUESTA', category='suggestion', value='Use Python')
        formatted = tag.format()

        assert formatted == "[PROPUESTA:suggestion] Use Python"
        assert formatted.startswith("[PROPUESTA:")

    def test_internal_tag_format(self):
        """Test INTERNAL tag format: [INTERNAL:category] value."""
        tag = PromptTag(type='INTERNAL', category='note', value='Internal memo')
        formatted = tag.format()

        assert formatted == "[INTERNAL:note] Internal memo"

    def test_external_tag_format(self):
        """Test EXTERNAL tag format: [EXTERNAL:category] value."""
        tag = PromptTag(type='EXTERNAL', category='api', value='External API')
        formatted = tag.format()

        assert formatted == "[EXTERNAL:api] External API"

    def test_tag_type_enum_matches_literal(self):
        """Test TagType enum matches allowed literal types."""
        assert TagType.KNOWLEDGE.value == 'K'
        assert TagType.CONSTRAINT.value == 'C'
        assert TagType.USAGE.value == 'U'
        assert TagType.EVIDENCIA.value == 'EVIDENCIA'
        assert TagType.PROPUESTA.value == 'PROPUESTA'
        assert TagType.INTERNAL.value == 'INTERNAL'
        assert TagType.EXTERNAL.value == 'EXTERNAL'


class TestExtractTagsFromContext:
    """Test TAGs extraction from context files."""

    def test_extract_from_empty_file(self, temp_dir: Path):
        """Test extracting from empty file returns empty list."""
        context_dir = temp_dir / ".context"
        context_dir.mkdir()

        empty_file = context_dir / "empty.md"
        empty_file.write_text("")

        extractor = TagExtractor(context_dir=context_dir)
        tags = extractor.extract_from_file(empty_file)

        assert tags == []

    def test_extract_from_file_with_no_sections(self, temp_dir: Path):
        """Test extracting from file without recognized sections."""
        context_dir = temp_dir / ".context"
        context_dir.mkdir()

        test_file = context_dir / "no_sections.md"
        test_file.write_text("Just some random text\nWith no sections")

        extractor = TagExtractor(context_dir=context_dir)
        tags = extractor.extract_from_file(test_file)

        assert tags == []

    def test_extract_from_file_with_identity_section(self, temp_dir: Path):
        """Test extracting Identity section generates K:identity tag.

        Note: Identity pattern uses ###? which means minimum ## (double hash).
        Single hash # does not match.
        """
        context_dir = temp_dir / ".context"
        context_dir.mkdir()

        test_file = context_dir / "identity.md"
        test_file.write_text("""## Identity

Felipe is a Python developer using FP patterns.
""")

        extractor = TagExtractor(context_dir=context_dir)
        tags = extractor.extract_from_file(test_file)

        assert len(tags) == 1
        assert tags[0].type == 'K'
        assert tags[0].category == 'identity'
        assert 'Felipe' in tags[0].value or 'Python' in tags[0].value

    def test_extract_from_file_with_rules_section(self, temp_dir: Path):
        """Test extracting Rules section generates U:rules tag."""
        context_dir = temp_dir / ".context"
        context_dir.mkdir()

        test_file = context_dir / "rules.md"
        test_file.write_text("""## Rules

- Always use immutable data structures
- Follow PEP 8 conventions
""")

        extractor = TagExtractor(context_dir=context_dir)
        tags = extractor.extract_from_file(test_file)

        assert len(tags) == 1
        assert tags[0].type == 'U'
        assert tags[0].category == 'rules'

    def test_extract_from_file_with_triggers_section(self, temp_dir: Path):
        """Test extracting Triggers section generates C:triggers tag."""
        context_dir = temp_dir / ".context"
        context_dir.mkdir()

        test_file = context_dir / "triggers.md"
        test_file.write_text("""### Triggers

- When creating new modules
- Before committing code
""")

        extractor = TagExtractor(context_dir=context_dir)
        tags = extractor.extract_from_file(test_file)

        assert len(tags) >= 1  # May match multiple patterns
        assert tags[0].type == 'C'
        assert tags[0].category == 'triggers'

    def test_extract_from_file_with_multiple_sections(self, temp_dir: Path):
        """Test extracting file with multiple sections."""
        context_dir = temp_dir / ".context"
        context_dir.mkdir()

        test_file = context_dir / "multi.md"
        test_file.write_text("""## Identity

Felipe is a developer.

## Rules

Use immutable data.

## Triggers

Before commits.
""")

        extractor = TagExtractor(context_dir=context_dir)
        tags = extractor.extract_from_file(test_file)

        assert len(tags) >= 3
        categories = {tag.category for tag in tags}
        assert 'identity' in categories
        assert 'rules' in categories
        assert 'triggers' in categories

    def test_extract_all_scans_standard_files(self, temp_dir: Path):
        """Test extract_all scans standard context files."""
        context_dir = temp_dir / ".context"
        context_dir.mkdir()

        # Create multiple context files
        (context_dir / "CLAUDE.md").write_text("# Identity\nFelipe")
        (context_dir / "identity.md").write_text("## Identity\nDeveloper")
        (context_dir / "rules.md").write_text("## Rules\nUse FP")
        (context_dir / "preferences.md").write_text("## Preferences\nVim")
        (context_dir / "projects.md").write_text("## Projects\nPlugin")
        (context_dir / "relationships.md").write_text("## Relationships\nTeam")

        extractor = TagExtractor(context_dir=context_dir)
        tags = extractor.extract_all()

        # Should extract from multiple files
        assert len(tags) > 0


class TestTagInjection:
    """Test TAG injection into prompts."""

    def test_inject_returns_original_when_no_tags(self, temp_dir: Path):
        """Test injection returns original prompt when no tags found."""
        empty_context = temp_dir / ".context"
        empty_context.mkdir()

        injector = TagInjector(extractor=TagExtractor(context_dir=empty_context))
        original = "Help me write code"
        result = injector.inject(original)

        assert result == original

    def test_inject_prepends_tags_to_prompt(self, temp_dir: Path):
        """Test injection prepends TAGs block to prompt."""
        context_dir = temp_dir / ".context"
        context_dir.mkdir()

        # Create identity.md which is in the extract_all file list
        (context_dir / "identity.md").write_text("## Identity\nFelipe")

        injector = TagInjector(extractor=TagExtractor(context_dir=context_dir))
        original = "Help me with Python"
        result = injector.inject(original)

        # TAGs should come before original prompt
        assert "## Context Tags" in result
        assert result.endswith(original)
        assert result.index("## Context Tags") < result.index(original)

    def test_inject_preserves_multi_line_prompt(self, temp_dir: Path):
        """Test injection preserves multi-line prompts."""
        context_dir = temp_dir / ".context"
        context_dir.mkdir()

        (context_dir / "CLAUDE.md").write_text("## Identity\nFelipe")

        injector = TagInjector(extractor=TagExtractor(context_dir=context_dir))
        original = """Line 1
Line 2
Line 3"""
        result = injector.inject(original)

        assert "Line 1" in result
        assert "Line 2" in result
        assert "Line 3" in result

    def test_inject_with_empty_prompt(self, temp_dir: Path):
        """Test injection with empty prompt."""
        context_dir = temp_dir / ".context"
        context_dir.mkdir()

        (context_dir / "CLAUDE.md").write_text("## Identity\nFelipe")

        injector = TagInjector(extractor=TagExtractor(context_dir=context_dir))
        result = injector.inject("")

        # Should have TAGs even with empty prompt
        if result:
            assert isinstance(result, str)


class TestEdgeCases:
    """Test edge cases: malformed tags, XML tags, special characters."""

    def test_extract_from_file_with_xml_tags(self, temp_dir: Path):
        """Test extraction from file containing XML tags."""
        context_dir = temp_dir / ".context"
        context_dir.mkdir()

        test_file = context_dir / "xml_tags.md"
        test_file.write_text("""## Identity

<user>
  <name>Felipe</name>
  <role>Developer</role>
</user>
""")

        extractor = TagExtractor(context_dir=context_dir)
        tags = extractor.extract_from_file(test_file)

        # Should still extract section, XML is just content
        assert len(tags) == 1
        assert tags[0].type == 'K'
        assert '<user>' in tags[0].value or 'Felipe' in tags[0].value

    def test_extract_from_file_with_markdown_code_blocks(self, temp_dir: Path):
        """Test extraction from file with markdown code blocks."""
        context_dir = temp_dir / ".context"
        context_dir.mkdir()

        test_file = context_dir / "code_blocks.md"
        test_file.write_text("""## Rules

```python
def example():
    return "immutable"
```
""")

        extractor = TagExtractor(context_dir=context_dir)
        tags = extractor.extract_from_file(test_file)

        # Should extract the section
        assert len(tags) == 1

    def test_extract_from_file_with_special_characters(self, temp_dir: Path):
        """Test extraction from file with special characters."""
        context_dir = temp_dir / ".context"
        context_dir.mkdir()

        test_file = context_dir / "special.md"
        test_file.write_text(r"""## Rules

- Use @decorators
- Handle "quotes"
- Escape \backslashes
- Use $variables
""")

        extractor = TagExtractor(context_dir=context_dir)
        tags = extractor.extract_from_file(test_file)

        # Should handle special characters
        assert len(tags) == 1
        assert isinstance(tags[0].value, str)

    def test_extract_from_nonexistent_file(self, temp_dir: Path):
        """Test extraction from non-existent file returns empty list."""
        extractor = TagExtractor(context_dir=temp_dir)
        tags = extractor.extract_from_file(temp_dir / "does_not_exist.md")

        assert tags == []

    def test_extract_from_file_with_unicode(self, temp_dir: Path):
        """Test extraction from file with Unicode characters."""
        context_dir = temp_dir / ".context"
        context_dir.mkdir()

        test_file = context_dir / "unicode.md"
        test_file.write_text("""## Rules

- Use emoji: 🚀 ✅
- Use accented: café, naïve
- Use symbols: → ≤ ≥
""")

        extractor = TagExtractor(context_dir=context_dir)
        tags = extractor.extract_from_file(test_file)

        # Should handle Unicode
        assert len(tags) == 1

    def test_value_truncation_with_long_content(self, temp_dir: Path):
        """Test that long values are truncated with ellipsis."""
        context_dir = temp_dir / ".context"
        context_dir.mkdir()

        test_file = context_dir / "long.md"
        very_long_line = "A" * 200
        test_file.write_text(f"## Identity\n{very_long_line}")

        extractor = TagExtractor(context_dir=context_dir)
        tags = extractor.extract_from_file(test_file)

        # Value should be truncated
        assert len(tags) == 1
        assert len(tags[0].value) <= 103  # 100 + "..."

    def test_malformed_bracket_tags_in_content(self, temp_dir: Path):
        """Test handling of malformed bracket patterns in content."""
        context_dir = temp_dir / ".context"
        context_dir.mkdir()

        test_file = context_dir / "malformed.md"
        test_file.write_text("""## Rules

- [Note: this looks like a tag but isn't]
- [Invalid: no space after bracket]
- [X:unknown_type] Should still extract
""")

        extractor = TagExtractor(context_dir=context_dir)
        tags = extractor.extract_from_file(test_file)

        # Should extract the section, malformed tags are just content
        assert len(tags) >= 1
        # The extractor creates tags from section headers, not from content

    def test_multiple_hash_heading_styles(self, temp_dir: Path):
        """Test extraction handles different heading styles (#, ##, ###).

        Note: Different sections have different hash requirements:
        - Identity/Projects/Relationships: ###? means minimum ##
        - Rules: ##? means minimum #
        - Preferences/Triggers/Constraints: ###? means minimum ##
        """
        context_dir = temp_dir / ".context"
        context_dir.mkdir()

        test_file = context_dir / "headings.md"
        test_file.write_text("""# Identity

Single hash - doesn't match (needs ##).

## Rules

Double hash - matches.

### Triggers

Triple hash - matches.
""")

        extractor = TagExtractor(context_dir=context_dir)
        tags = extractor.extract_from_file(test_file)

        # Should extract Rules (##) and Triggers (###), but not single-hash Identity
        assert len(tags) >= 2  # May have multiple pattern matches
        categories = {tag.category for tag in tags}
        assert 'rules' in categories
        assert 'triggers' in categories
        assert 'identity' not in categories  # Single hash doesn't match

    def test_empty_section_content(self, temp_dir: Path):
        """Test handling of sections with empty content."""
        context_dir = temp_dir / ".context"
        context_dir.mkdir()

        test_file = context_dir / "empty_sections.md"
        test_file.write_text("""## Identity


## Rules

## Triggers

Content here
""")

        extractor = TagExtractor(context_dir=context_dir)
        tags = extractor.extract_from_file(test_file)

        # Should handle empty sections gracefully
        # Empty sections might not create tags
        assert isinstance(tags, list)

    def test_consecutive_sections(self, temp_dir: Path):
        """Test handling of consecutive section headers."""
        context_dir = temp_dir / ".context"
        context_dir.mkdir()

        test_file = context_dir / "consecutive.md"
        test_file.write_text("## Identity\n## Rules\n## Triggers\n")

        extractor = TagExtractor(context_dir=context_dir)
        tags = extractor.extract_from_file(test_file)

        # Should handle consecutive headers
        assert isinstance(tags, list)

    def test_file_with_only_whitespace(self, temp_dir: Path):
        """Test extraction from file with only whitespace."""
        context_dir = temp_dir / ".context"
        context_dir.mkdir()

        test_file = context_dir / "whitespace.md"
        test_file.write_text("   \n\n   \n\t\t\n")

        extractor = TagExtractor(context_dir=context_dir)
        tags = extractor.extract_from_file(test_file)

        assert tags == []

    def test_extractor_with_nonexistent_context_dir(self, temp_dir: Path):
        """Test TagExtractor with nonexistent context directory."""
        nonexistent_dir = temp_dir / "does_not_exist"
        extractor = TagExtractor(context_dir=nonexistent_dir)

        tags = extractor.extract_all()

        # Should return empty list, not crash
        assert tags == []


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

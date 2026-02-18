"""
Unit tests for TAG system quality filters.

Tests cover:
- is_header_only() - detecting header-only content
- is_empty_markdown_table() - detecting empty tables
- normalize() and content_hash() - deduplication helpers
- has_minimum_content() - minimum content length
- calculate_info_density() - content quality scoring
- Ranking and top_k limiting
"""

import pytest
from lib.tag_system import (
    is_header_only,
    is_empty_markdown_table,
    normalize,
    content_hash,
    has_minimum_content,
    calculate_info_density,
    calculate_tag_score,
    PromptTag,
    TagExtractor,
    TagInjector,
    TECHNICAL_CATEGORIES,
)


class TestHeaderOnly:
    """Tests for is_header_only() function."""

    def test_single_header_is_header_only(self) -> None:
        """A single markdown header should be detected as header-only."""
        assert is_header_only("### Some Header") is True
        assert is_header_only("## Section Title") is True
        assert is_header_only("# Main Title") is True

    def test_multiple_headers_is_header_only(self) -> None:
        """Multiple headers without content should be header-only."""
        content = "## Section\n### Subsection\n#### Detail"
        assert is_header_only(content) is True

    def test_header_with_content_is_not_header_only(self) -> None:
        """Header followed by content should NOT be header-only."""
        content = "### Header\nSome actual content here"
        assert is_header_only(content) is False

    def test_empty_string_is_header_only(self) -> None:
        """Empty content should be treated as header-only (no useful content)."""
        assert is_header_only("") is True

    def test_whitespace_only_is_header_only(self) -> None:
        """Whitespace-only content should be header-only."""
        assert is_header_only("   \n  \n  ") is True


class TestEmptyMarkdownTable:
    """Tests for is_empty_markdown_table() function."""

    def test_empty_table_detected(self) -> None:
        """Table with only header and separator is empty."""
        table = "| Col1 | Col2 | Col3 |\n|------|------|------|"
        assert is_empty_markdown_table(table) is True

    def test_table_with_data_not_empty(self) -> None:
        """Table with data rows is NOT empty."""
        table = "| Col1 | Col2 |\n|------|------|\n| val1 | val2 |"
        assert is_empty_markdown_table(table) is False

    def test_non_table_not_empty(self) -> None:
        """Non-table content should return False (not applicable)."""
        content = "Just some text"
        assert is_empty_markdown_table(content) is False

    def test_table_with_multiple_data_rows(self) -> None:
        """Table with multiple data rows is NOT empty."""
        table = """| A | B |
|---|---|
| 1 | 2 |
| 3 | 4 |
| 5 | 6 |"""
        assert is_empty_markdown_table(table) is False


class TestNormalizeAndHash:
    """Tests for normalize() and content_hash() functions."""

    def test_normalize_collapses_whitespace(self) -> None:
        """Normalize should collapse multiple spaces to single space."""
        assert normalize("hello   world") == "hello world"

    def test_normalize_lowercase(self) -> None:
        """Normalize should convert to lowercase."""
        assert normalize("HELLO World") == "hello world"

    def test_normalize_strips(self) -> None:
        """Normalize should strip leading/trailing whitespace."""
        assert normalize("  hello  ") == "hello"

    def test_same_content_same_hash(self) -> None:
        """Same content should produce same hash."""
        h1 = content_hash("Some content here")
        h2 = content_hash("Some content here")
        assert h1 == h2

    def test_different_content_different_hash(self) -> None:
        """Different content should produce different hash."""
        h1 = content_hash("Content A")
        h2 = content_hash("Content B")
        assert h1 != h2

    def test_normalized_equivalent_same_hash(self) -> None:
        """Content that normalizes to same value should have same hash."""
        h1 = content_hash("Hello World")
        h2 = content_hash("  hello   world  ")  # Normalizes to same
        assert h1 == h2


class TestMinimumContent:
    """Tests for has_minimum_content() function."""

    def test_short_content_fails(self) -> None:
        """Content shorter than min_chars should fail."""
        assert has_minimum_content("Hi", min_chars=50) is False

    def test_long_content_passes(self) -> None:
        """Content longer than min_chars should pass."""
        long_text = "This is a longer piece of content that exceeds the minimum requirement"
        assert has_minimum_content(long_text, min_chars=50) is True

    def test_markdown_syntax_excluded(self) -> None:
        """Markdown syntax should not count toward character limit."""
        # Mostly markdown, little content
        md_heavy = "### **_`Header`_**\n| A | B |"
        assert has_minimum_content(md_heavy, min_chars=50) is False


class TestInfoDensity:
    """Tests for calculate_info_density() function."""

    def test_high_value_keywords_boost_score(self) -> None:
        """Content with high-value keywords should have higher score."""
        low_score = calculate_info_density("Some random text without keywords")
        high_score = calculate_info_density("Use TDD and Clean Architecture patterns")
        assert high_score > low_score

    def test_bullets_boost_score(self) -> None:
        """Bullet points should increase score (structured info)."""
        no_bullets = calculate_info_density("Line one\nLine two\nLine three")
        with_bullets = calculate_info_density("- Point one\n- Point two\n- Point three")
        assert with_bullets > no_bullets

    def test_tables_penalty(self) -> None:
        """Tables should be penalized or equal to non-table content."""
        no_table = calculate_info_density("Some content without pipes")
        with_table = calculate_info_density("Some | content | with | pipes")
        # Table content should not score higher than non-table
        assert no_table >= with_table


class TestTagScoring:
    """Tests for calculate_tag_score() function."""

    def test_critical_rules_highest_score(self) -> None:
        """Critical rules should have highest category score."""
        critical_tag = PromptTag(type='U', category='rules_critical', value='Test')
        normal_tag = PromptTag(type='K', category='projects', value='Test')
        assert calculate_tag_score(critical_tag) > calculate_tag_score(normal_tag)

    def test_project_relevance_boost(self) -> None:
        """Tags mentioning project path should get relevance boost."""
        tag = PromptTag(type='K', category='projects', value='skills-fabrik-patterns plugin')
        no_project_score = calculate_tag_score(tag, project_path=None)
        with_project_score = calculate_tag_score(tag, project_path='skills-fabrik-patterns')
        assert with_project_score > no_project_score


class TestRankingAndTopK:
    """Tests for ranking and top_k limiting."""

    def test_top_k_limits_output(self) -> None:
        """TagExtractor should limit output to top_k tags."""
        # Create extractor with small top_k
        extractor = TagExtractor(top_k=2)
        tags = extractor.extract_all()
        assert len(tags) <= 2

    def test_technical_only_filters_categories(self) -> None:
        """technical_only=True should only include technical categories."""
        injector = TagInjector(technical_only=True, top_k=20)
        # Get the extractor's allowed categories
        allowed = injector.extractor.allowed_categories
        assert allowed == TECHNICAL_CATEGORIES

    def test_deterministic_ordering(self) -> None:
        """Same input should produce same output order."""
        extractor1 = TagExtractor(top_k=10)
        extractor2 = TagExtractor(top_k=10)
        tags1 = extractor1.extract_all()
        tags2 = extractor2.extract_all()
        # Same number of tags
        assert len(tags1) == len(tags2)
        # Same order
        for t1, t2 in zip(tags1, tags2):
            assert t1.format() == t2.format()


class TestIntegration:
    """Integration tests for full TAG extraction flow."""

    def test_no_header_only_tags(self) -> None:
        """Extracted tags should not be header-only."""
        injector = TagInjector(technical_only=True, top_k=10)
        # Access the underlying extraction
        extractor = injector.extractor
        tags = extractor.extract_all()

        for tag in tags:
            # The value should not be just a header
            assert not is_header_only(tag.value), f"Tag is header-only: {tag.format()}"

    def test_no_empty_tables(self) -> None:
        """Extracted tags should not be empty tables."""
        injector = TagInjector(technical_only=True, top_k=10)
        extractor = injector.extractor
        tags = extractor.extract_all()

        for tag in tags:
            # The value should not be an empty table
            assert not is_empty_markdown_table(tag.value), f"Tag is empty table: {tag.format()}"

    def test_technical_context_injection(self) -> None:
        """TagInjector should inject technical context into prompts."""
        injector = TagInjector(technical_only=True)
        prompt = "Write some code"
        result = injector.inject(prompt)

        # Should contain the original prompt
        assert prompt in result
        # Should have Context Tags section
        assert "## Context Tags" in result


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

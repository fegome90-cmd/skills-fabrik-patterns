"""
Property tests for fail-closed behavior.

Core invariant: ONE corrupt line NEVER breaks parsing.
"""

import json
import pytest
from pathlib import Path
import tempfile

# Add lib to path
import sys
lib_dir = Path(__file__).parent.parent / "lib"
sys.path.insert(0, str(lib_dir))

from jsonl_typed import (
    parse_line,
    parse_jsonl_file,
    MetaLine,
    RefLine,
    serialize_line,
    SCHEMA_VERSION,
)


class TestFailClosedProperty:
    """
    Property: Fail-closed behavior is guaranteed.

    No matter what corruption exists, parse_line returns None
    and parse_jsonl_file continues processing remaining lines.
    """

    @pytest.mark.parametrize(
        "corrupt_input",
        [
            # Missing closing brace
            '{"t":"meta","id":"test',
            # Invalid JSON syntax
            '{t: "meta", "id": "test"}',
            # Random text
            "this is not json at all",
            # Truncated in middle
            '{"t":"ref","p":"test.',
            # Control characters
            '{"t":"\x00meta"}',
            # Unicode decode error simulation (already decoded, but malformed)
            '{"t":"meta","id":"\ud800"}',
        ],
    )
    def test_corrupt_input_returns_none(self, corrupt_input):
        """Property: Any corrupt input returns None."""
        result = parse_line(corrupt_input)
        assert result is None

    def test_empty_input_returns_none(self):
        """Property: Empty string returns None."""
        assert parse_line("") is None
        assert parse_line("   ") is None
        assert parse_line("\n\t") is None

    def test_valid_input_parses(self):
        """Property: Valid input returns TypedLine."""
        valid = '{"t":"meta","id":"test123","c":"2026-02-11T14:30:22Z","r":"/tmp","w":"."}'
        result = parse_line(valid)
        assert result is not None
        assert isinstance(result, MetaLine)

    def test_partial_valid_data_still_parses(self):
        """Property: Missing optional fields doesn't break parsing."""
        # Minimal valid meta (optional fields missing)
        minimal = '{"t":"meta","id":"x","c":"x","r":"x","w":"."}'
        result = parse_line(minimal)
        assert result is not None
        assert isinstance(result, MetaLine)

    @pytest.mark.parametrize(
        "missing_field",
        ["id", "c", "r", "w"],  # All required for meta
    )
    def test_missing_required_field_returns_none(self, missing_field):
        """Property: Missing required field returns None."""
        # Create meta missing one required field
        data = {
            "t": "meta",
            "id": "test123",
            "c": "2026-02-11T14:30:22Z",
            "r": "/tmp",
            "w": ".",
        }
        del data[missing_field]
        result = parse_line(json.dumps(data))
        assert result is None

    def test_multiple_corrupt_lines_in_file(self, tmp_path):
        """Property: Multiple corrupt lines in file don't break parsing."""
        content = """{"t":"meta","id":"test","c":"x","r":"/tmp","w":"."}
corrupt line 1
{"t":"ref","p":"a.py","h":"abc123","s":100,"m":1,"l":"s","o":"read"}
also corrupt
{"t":"audit","ts":1,"run":"test","ok":true}
"""
        test_file = tmp_path / "test.jsonl"
        test_file.write_text(content)

        lines = list(parse_jsonl_file(test_file))
        # Should get 3 valid lines (meta, ref, audit)
        # and skip 2 corrupt lines
        assert len(lines) == 3
        assert all(line is not None for line in lines)

    def test_corrupt_at_start_of_file(self, tmp_path):
        """Property: Corrupt line at file start doesn't prevent parsing rest."""
        content = """totally broken json
{"t":"meta","id":"test","c":"x","r":"/tmp","w":"."}
{"t":"ref","p":"b.py","h":"def456","s":200,"m":2,"l":"m","o":"edit"}
"""
        test_file = tmp_path / "test.jsonl"
        test_file.write_text(content)

        lines = list(parse_jsonl_file(test_file))
        assert len(lines) == 2  # meta and ref parsed

    def test_corrupt_at_end_of_file(self, tmp_path):
        """Property: Corrupt line at file end doesn't affect earlier lines."""
        content = """{"t":"meta","id":"test","c":"x","r":"/tmp","w":"."}
{"t":"ref","p":"c.py","h":"789xyz","s":300,"m":3,"l":"f","o":"write"}
truncated final line without closing brace
"""
        test_file = tmp_path / "test.jsonl"
        test_file.write_text(content)

        lines = list(parse_jsonl_file(test_file))
        assert len(lines) == 2  # meta and ref parsed

    def test_empty_file_returns_empty_iterator(self, tmp_path):
        """Property: Empty file yields no lines."""
        test_file = tmp_path / "test.jsonl"
        test_file.write_text("")
        lines = list(parse_jsonl_file(test_file))
        assert len(lines) == 0

    def test_file_with_only_newlines(self, tmp_path):
        """Property: File with only newlines yields no lines."""
        test_file = tmp_path / "test.jsonl"
        test_file.write_text("\n\n\n\n")
        lines = list(parse_jsonl_file(test_file))
        assert len(lines) == 0

    def test_mixed_valid_and_corrupt(self, tmp_path):
        """Property: Valid and corrupt lines intermixed - all valid parsed."""
        content = """{"t":"meta","id":"x","c":"x","r":"/tmp","w":"."}
{"t":"ref","p":"1.py","h":"a","s":1,"m":1,"l":"s","o":"read"}
bad json here
{"t":"ref","p":"2.py","h":"b","s":2,"m":2,"l":"m","o":"edit"}
still bad
{"t":"ref","p":"3.py","h":"c","s":3,"m":3,"l":"f","o":"write"}
more bad json
{"t":"audit","ts":9,"run":"compact","ok":true}
"""
        test_file = tmp_path / "test_mixed.jsonl"
        test_file.write_text(content)

        lines = list(parse_jsonl_file(test_file))
        # Should parse: 1 meta + 3 refs + 1 audit = 5 lines
        assert len(lines) == 5

        # Verify order preserved
        assert isinstance(lines[0], MetaLine)
        assert lines[1].p == "1.py"
        assert lines[2].p == "2.py"
        assert lines[3].p == "3.py"

    def test_unknown_type_field_returns_none(self):
        """Property: Unknown 't' value returns None."""
        unknown = '{"t":"unknown_type","x":"y"}'
        result = parse_line(unknown)
        assert result is None

    def test_missing_type_field_returns_none(self):
        """Property: Missing 't' field returns None."""
        no_type = '{"id":"test","x":"y"}'
        result = parse_line(no_type)
        assert result is None

    def test_extra_fields_ignored(self):
        """Property: Extra fields in valid line don't break parsing."""
        # Valid meta with extra fields
        with_extra = '{"t":"meta","id":"x","c":"x","r":"/tmp","w":".","extra":"field","another":123}'
        result = parse_line(with_extra)
        assert result is not None
        assert isinstance(result, MetaLine)

    def test_null_values_in_optional_fields(self):
        """Property: Null values in optional fields are handled."""
        with_nulls = '{"t":"meta","id":"x","c":"x","r":"/tmp","w":".","rid":null,"fc":null}'
        result = parse_line(with_nulls)
        assert result is not None
        assert result.rid is None
        assert result.fc == 0


class TestStressProperty:
    """
    Stress tests for fail-closed property.

    Test edge cases and unusual inputs.
    """

    def test_very_long_line(self, tmp_path):
        """Property: Very long line that's corrupt returns None."""
        # Create a very long truncated JSON
        long_corrupt = '{"t":"meta","id":"' + "x" * 10000  # Very long without closing
        assert parse_line(long_corrupt) is None

    def test_deeply_nested_json(self):
        """Property: Deeply nested but valid JSON parses."""
        # This is valid JSON, just deeply nested
        nested = '{"t":"meta","id":"test","c":"x","r":"/tmp","w":".","nested":{"a":{"b":{"c":"d"}}}}'
        result = parse_line(nested)
        assert result is not None  # Valid structure, extra fields ignored

    def test_unicode_in_valid_line(self):
        """Property: Unicode characters in valid line parse correctly."""
        with_unicode = '{"t":"meta","id":"test","c":"x","r":"/tmp","w":".","note":"日本語"}'
        result = parse_line(with_unicode)
        assert result is not None

    def test_special_characters_in_string(self):
        """Property: Special characters in string values handled correctly."""
        with_special = r'{"t":"meta","id":"test","c":"x","r":"/tmp","w":".","path":"C:\\new\\file.txt"}'
        result = parse_line(with_special)
        assert result is not None

    def test_comma_separated_values(self):
        """Property: Comma-separated list in field doesn't break parsing."""
        # Tags as comma-separated string
        with_commas = '{"t":"meta","id":"test","c":"x","r":"/tmp","w":".","tags":"core,config,important"}'
        result = parse_line(with_commas)
        assert result is not None


# No custom fixture needed - use pytest's built-in tmp_path directly
# Tests create files inside tmp_path directory

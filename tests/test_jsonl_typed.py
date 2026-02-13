"""
Unit tests for JSONL typed parser.

Tests fail-closed behavior: corrupt lines return None, parsing continues.
"""

import json
import pytest
from pathlib import Path

# Add lib to path
import sys
lib_dir = Path(__file__).parent.parent / "lib"
sys.path.insert(0, str(lib_dir))

from jsonl_typed import (
    parse_line,
    serialize_line,
    MetaLine,
    RefLine,
    ExLine,
    AuditLine,
    LineType,
    DepthLevel,
    OperationType,
    SCHEMA_VERSION,
    create_meta_line,
    parse_jsonl_file,
)


class TestMetaLine:
    """Tests for MetaLine parsing and serialization."""

    def test_parse_valid_meta(self):
        """Test parsing valid meta line."""
        data = {
            "t": "meta",
            "id": "20260211-143022",
            "c": "2026-02-11T14:30:22Z",
            "r": "/Users/user/project",
            "w": "src",
            "rid": "abc123",
            "fc": 2,
            "sc": False,
            "v": "1.0",
        }
        line = parse_line(json.dumps(data))
        assert isinstance(line, MetaLine)
        assert line.id == "20260211-143022"
        assert line.rid == "abc123"
        assert line.fc == 2

    def test_parse_minimal_meta(self):
        """Test parsing minimal meta (optional fields missing)."""
        data = {
            "t": "meta",
            "id": "20260211-143022",
            "c": "2026-02-11T14:30:22Z",
            "r": "/Users/user/project",
            "w": ".",
        }
        line = parse_line(json.dumps(data))
        assert isinstance(line, MetaLine)
        assert line.rid is None
        assert line.fc == 0
        assert line.sc is False

    def test_parse_invalid_meta_returns_none(self):
        """Test that invalid meta returns None (fail-closed)."""
        data = {"t": "meta", "id": 123}  # Missing required fields
        line = parse_line(json.dumps(data))
        assert line is None

    def test_serialize_meta(self):
        """Test serializing meta line."""
        meta = MetaLine(
            t="meta",
            id="20260211-143022",
            c="2026-02-11T14:30:22Z",
            r="/Users/user/project",
            w="src",
            rid="abc123",
            fc=2,
            sc=False,
            v="1.0",
        )
        serialized = serialize_line(meta)
        parsed = json.loads(serialized)

        assert parsed["t"] == "meta"
        assert parsed["id"] == "20260211-143022"
        assert parsed["rid"] == "abc123"


class TestRefLine:
    """Tests for RefLine parsing and serialization."""

    def test_parse_valid_ref(self):
        """Test parsing valid ref line."""
        data = {
            "t": "ref",
            "p": "src/app.py",
            "h": "a1b2c3d4",
            "s": 1234,
            "m": 1738312345,
            "l": "m",
            "o": "edit",
        }
        line = parse_line(json.dumps(data))
        assert isinstance(line, RefLine)
        assert line.p == "src/app.py"
        assert line.h == "a1b2c3d4"
        assert line.s == 1234

    def test_parse_invalid_ref_returns_none(self):
        """Test that invalid ref returns None (fail-closed)."""
        data = {"t": "ref", "p": "test.py"}  # Missing required fields
        line = parse_line(json.dumps(data))
        assert line is None

    def test_serialize_ref(self):
        """Test serializing ref line."""
        ref = RefLine(
            t="ref",
            p="lib/utils.py",
            h="x9y8z7w6",
            s=5678,
            m=1738312400,
            l=DepthLevel.SHALLOW,
            o=OperationType.READ,
        )
        serialized = serialize_line(ref)
        parsed = json.loads(serialized)

        assert parsed["t"] == "ref"
        assert parsed["p"] == "lib/utils.py"
        assert parsed["l"] == "s"
        assert parsed["o"] == "read"


class TestExLine:
    """Tests for ExLine (secret exclusion)."""

    def test_parse_valid_ex(self):
        """Test parsing valid ex line."""
        data = {
            "t": "ex",
            "k": "secret_patterns",
            "n": 3,
            "why": ".env,*.key",
        }
        line = parse_line(json.dumps(data))
        assert isinstance(line, ExLine)
        assert line.k == "secret_patterns"
        assert line.n == 3

    def test_serialize_ex(self):
        """Test serializing ex line."""
        ex = ExLine(
            t="ex",
            k="secret_patterns",
            n=5,
            why=".env,secret.py",
        )
        serialized = serialize_line(ex)
        parsed = json.loads(serialized)

        assert parsed["t"] == "ex"
        assert parsed["n"] == 5
        assert parsed["why"] == ".env,secret.py"


class TestAuditLine:
    """Tests for AuditLine."""

    def test_parse_valid_audit(self):
        """Test parsing valid audit line."""
        data = {
            "t": "audit",
            "ts": 1738312345,
            "run": "compact",
            "ok": True,
            "d": False,
        }
        line = parse_line(json.dumps(data))
        assert isinstance(line, AuditLine)
        assert line.run == "compact"

    def test_parse_audit_with_depth(self):
        """Test parsing audit with depth field."""
        data = {
            "t": "audit",
            "ts": 1738312345,
            "run": "hydrate",
            "ok": True,
            "depth": "m",
        }
        line = parse_line(json.dumps(data))
        assert isinstance(line, AuditLine)
        assert line.depth == "m"


class TestFailClosed:
    """Tests for fail-closed behavior."""

    def test_corrupt_json_returns_none(self):
        """Test that corrupt JSON returns None."""
        line = parse_line('{"t":"meta", invalid json')
        assert line is None

    def test_empty_line_returns_none(self):
        """Test that empty line returns None."""
        line = parse_line("")
        assert line is None

    def test_whitespace_only_returns_none(self):
        """Test that whitespace-only line returns None."""
        line = parse_line("   \n  \t  ")
        assert line is None

    def test_unknown_type_returns_none(self):
        """Test that unknown type returns None."""
        data = {"t": "unknown", "x": "y"}
        line = parse_line(json.dumps(data))
        assert line is None

    def test_parse_jsonl_file_with_corrupt_lines(self, tmp_path):
        """Test parsing file with corrupt lines continues."""
        content = """{"t":"meta","id":"test123","c":"2026-02-11T14:30:22Z","r":"/tmp","w":"."}
{"t":"ref","p":"app.py","h":"abc123","s":100,"m":123,"l":"s","o":"read"}
invalid json here
{"t":"audit","ts":123456,"run":"compact","ok":true}
"""
        # Create a file inside tmp_path directory
        test_file = tmp_path / "test.jsonl"
        test_file.write_text(content)

        lines = list(parse_jsonl_file(test_file))
        # Should skip corrupt line, yield 3 valid lines
        assert len(lines) == 3
        assert isinstance(lines[0], MetaLine)
        assert isinstance(lines[1], RefLine)
        assert isinstance(lines[2], AuditLine)


class TestCreateMetaLine:
    """Tests for create_meta_line helper."""

    def test_create_meta_line_generates_id(self):
        """Test that ID is generated from timestamp."""
        meta = create_meta_line(
            repo_root="/tmp/test",
            working_dir="src",
        )
        assert meta.id is not None
        assert len(meta.id) == 15  # YYYYMMDD-HHMMSS format
        assert "-" in meta.id

    def test_create_meta_line_with_all_params(self):
        """Test create_meta_line with all parameters."""
        meta = create_meta_line(
            repo_root="/tmp/test",
            working_dir="src",
            repo_id="abc123",
            files_changed=5,
            secrets_changed=True,
        )
        assert meta.rid == "abc123"
        assert meta.fc == 5
        assert meta.sc is True


class TestSerialization:
    """Tests for serialization round-trip."""

    def test_meta_round_trip(self):
        """Test meta serializes and parses back correctly."""
        original = MetaLine(
            t="meta",
            id="20260211-143022",
            c="2026-02-11T14:30:22Z",
            r="/tmp/test",
            w="src",
            rid="xyz",
        )
        serialized = serialize_line(original)
        parsed = parse_line(serialized)

        assert isinstance(parsed, MetaLine)
        assert parsed.id == original.id
        assert parsed.rid == original.rid

    def test_ref_round_trip(self):
        """Test ref serializes and parses back correctly."""
        original = RefLine(
            t="ref",
            p="lib/test.py",
            h="deadbeef",
            s=999,
            m=111111,
            l=DepthLevel.MEDIUM,
            o=OperationType.EDIT,
        )
        serialized = serialize_line(original)
        parsed = parse_line(serialized)

        assert isinstance(parsed, RefLine)
        assert parsed.p == original.p
        assert parsed.h == original.h

    @pytest.mark.parametrize("line_type", ["meta", "ref", "ex", "audit"])
    def test_all_line_types_have_t_field(self, line_type):
        """Test all serialized lines have 't' field."""
        # Create minimal valid line for each type
        if line_type == "meta":
            line = MetaLine(t="meta", id="x", c="x", r="x", w="x")
        elif line_type == "ref":
            line = RefLine(t="ref", p="x", h="x", s=1, m=1, l=DepthLevel.SHALLOW, o=OperationType.READ)
        elif line_type == "ex":
            line = ExLine(t="ex", k="x", n=1, why="x")
        else:  # audit
            line = AuditLine(t="audit", ts=1, run="x", ok=True)

        serialized = serialize_line(line)
        data = json.loads(serialized)
        assert "t" in data
        assert data["t"] == line_type

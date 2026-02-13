"""
JSONL Typed Parser - Fail-Closed with Discriminated Lines

Implements typed JSONL format for CAS handoffs:
- meta: Handoff metadata
- ref: File reference
- audit: Operation log
- ex: Secret exclusion (count only, no paths/hashes/sizes)

Design: Fail-closed - one corrupted line returns None, continues parsing.
"""

import json
import sys
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Iterator, Optional, Literal

# Add parent lib to path for imports
lib_dir = Path(__file__).parent
if str(lib_dir) not in sys.path:
    sys.path.insert(0, str(lib_dir))


class LineType(Enum):
    """Types of JSONL lines."""
    META = "meta"
    REF = "ref"
    AUDIT = "audit"
    EX = "ex"


class DepthLevel(Enum):
    """Depth levels for file references."""
    SHALLOW = "s"
    MEDIUM = "m"
    FULL = "f"


class OperationType(Enum):
    """Operation types for file references."""
    READ = "read"
    EDIT = "edit"
    WRITE = "write"
    MULTI_EDIT = "multi_edit"


SCHEMA_VERSION = "1.0"


@dataclass(frozen=True)
class MetaLine:
    """
    Header metadata line for a handoff.

    Immutable snapshot of handoff metadata.
    """
    t: Literal["meta"]
    id: str  # Handoff ID (YYYYMMDD-HHMMSS format)
    c: str  # Created timestamp (ISO 8601)
    r: str  # Repo root path (absolute)
    w: str  # Working directory relative to repo root
    rid: Optional[str] = None  # Repo ID from context-memory
    fc: int = 0  # Files changed count
    sc: bool = False  # Secrets changed flag
    v: str = SCHEMA_VERSION  # Schema version


@dataclass(frozen=True)
class RefLine:
    """
    File reference line in a handoff.

    CRITICAL: For security, NEVER include RefLines for secrets.
    Only counts are recorded in ExLines.
    """
    t: Literal["ref"]
    p: str  # Path (relative to repo root)
    h: str  # SHA256 hash (8 chars)
    s: int  # Size in bytes
    m: int  # Unix timestamp (mtime)
    l: DepthLevel  # Level: s/m/f
    o: OperationType  # Operation: read/edit/write/multi_edit


@dataclass(frozen=True)
class ExLine:
    """
    Secret exclusion line - counts only, NO sensitive data.

    Security: Contains ONLY count and pattern reasons.
    NEVER includes: actual paths, hashes, sizes, or content.
    """
    t: Literal["ex"]
    k: str  # Key: "secret_patterns"
    n: int  # Count of excluded secrets
    why: str  # Reasons: comma-separated patterns matched


@dataclass(frozen=True)
class AuditLine:
    """
    Audit log line for operations.
    """
    t: Literal["audit"]
    ts: int  # Unix timestamp
    run: str  # Operation: compact, hydrate
    ok: bool  # Success flag
    d: bool = False  # Degraded flag (non-fatal error)
    depth: Optional[str] = None  # Depth used (hydrate only)


# Union type for all line types
TypedLine = MetaLine | RefLine | ExLine | AuditLine


def parse_line(line: str) -> Optional[TypedLine]:
    """
    Parse a single JSONL line into its typed representation.

    Fail-closed: Returns None for invalid/corrupt lines, continues parsing.

    Args:
        line: Raw JSONL line

    Returns:
        TypedLine object, or None if line is invalid/corrupt
    """
    # Skip empty lines (graceful)
    stripped = line.strip()
    if not stripped:
        return None

    try:
        data = json.loads(stripped)
    except json.JSONDecodeError:
        # Corrupt JSON - return None (fail-closed)
        return None

    # Discriminate by 't' field
    line_type = data.get("t")

    if line_type == LineType.META.value:
        return _parse_meta(data)
    elif line_type == LineType.REF.value:
        return _parse_ref(data)
    elif line_type == LineType.EX.value:
        return _parse_ex(data)
    elif line_type == LineType.AUDIT.value:
        return _parse_audit(data)
    else:
        # Unknown type - fail-closed
        return None


def _parse_meta(data: dict[str, Any]) -> Optional[MetaLine]:
    """Parse meta line."""
    try:
        # Handle optional fields - null values should use defaults
        rid_val = data.get("rid")
        fc_val = data.get("fc")
        sc_val = data.get("sc")

        return MetaLine(
            t="meta",
            id=str(data["id"]),
            c=str(data["c"]),
            r=str(data["r"]),
            w=str(data["w"]),
            rid=rid_val if rid_val is not None else None,
            fc=int(fc_val) if fc_val is not None else 0,
            sc=bool(sc_val) if sc_val is not None else False,
            v=str(data.get("v", SCHEMA_VERSION)),
        )
    except (KeyError, TypeError, ValueError):
        return None


def _parse_ref(data: dict[str, Any]) -> Optional[RefLine]:
    """Parse ref line."""
    try:
        return RefLine(
            t="ref",
            p=str(data["p"]),
            h=str(data["h"]),
            s=int(data["s"]),
            m=int(data["m"]),
            l=DepthLevel(data["l"]),
            o=OperationType(data["o"]),
        )
    except (KeyError, TypeError, ValueError):
        return None


def _parse_ex(data: dict[str, Any]) -> Optional[ExLine]:
    """Parse ex line."""
    try:
        return ExLine(
            t="ex",
            k=str(data["k"]),
            n=int(data["n"]),
            why=str(data["why"]),
        )
    except (KeyError, TypeError, ValueError):
        return None


def _parse_audit(data: dict[str, Any]) -> Optional[AuditLine]:
    """Parse audit line."""
    try:
        return AuditLine(
            t="audit",
            ts=int(data["ts"]),
            run=str(data["run"]),
            ok=bool(data["ok"]),
            d=bool(data.get("d", False)),
            depth=data.get("depth"),
        )
    except (KeyError, TypeError, ValueError):
        return None


def parse_jsonl_file(path: Path) -> Iterator[TypedLine]:
    """
    Parse a JSONL file, yielding typed lines.

    Fail-closed: Continues parsing even if individual lines are corrupt.

    Args:
        path: Path to JSONL file

    Yields:
        TypedLine objects (skips None for corrupt lines)
    """
    if not path.exists():
        return

    with open(path, "r") as f:
        for line in f:
            parsed = parse_line(line)
            if parsed is not None:
                yield parsed


def serialize_line(line: TypedLine) -> str:
    """
    Serialize a typed line to JSONL format.

    Args:
        line: TypedLine to serialize

    Returns:
        JSON string (without newline)
    """
    if isinstance(line, MetaLine):
        data = {
            "t": "meta",
            "id": line.id,
            "c": line.c,
            "r": line.r,
            "w": line.w,
            "v": line.v,
        }
        if line.rid is not None:
            data["rid"] = line.rid
        if line.fc > 0:
            data["fc"] = line.fc
        if line.sc:
            data["sc"] = True

    elif isinstance(line, RefLine):
        data = {
            "t": "ref",
            "p": line.p,
            "h": line.h,
            "s": line.s,
            "m": line.m,
            "l": line.l.value,
            "o": line.o.value,
        }

    elif isinstance(line, ExLine):
        data = {
            "t": "ex",
            "k": line.k,
            "n": line.n,
            "why": line.why,
        }

    elif isinstance(line, AuditLine):
        data = {
            "t": "audit",
            "ts": line.ts,
            "run": line.run,
            "ok": line.ok,
        }
        if line.d:
            data["d"] = True
        if line.depth is not None:
            data["depth"] = line.depth

    else:
        raise TypeError(f"Unknown line type: {type(line)}")

    return json.dumps(data, separators=(",", ":"))


def create_meta_line(
    repo_root: str,
    working_dir: str,
    repo_id: Optional[str] = None,
    files_changed: int = 0,
    secrets_changed: bool = False,
) -> MetaLine:
    """
    Create a new MetaLine for a handoff.

    Args:
        repo_root: Absolute path to repository root
        working_dir: Working directory relative to repo root
        repo_id: Optional repository ID
        files_changed: Number of files changed
        secrets_changed: Whether secrets were detected

    Returns:
        MetaLine with generated ID and timestamp
    """
    # Generate handoff ID from timestamp
    handoff_id = datetime.now().strftime("%Y%m%d-%H%M%S")
    created = datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ")

    return MetaLine(
        t="meta",
        id=handoff_id,
        c=created,
        r=repo_root,
        w=working_dir,
        rid=repo_id,
        fc=files_changed,
        sc=secrets_changed,
    )

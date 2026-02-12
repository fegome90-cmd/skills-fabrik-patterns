"""
Handoff CAS Model - Content-Addressed Storage for Handoffs

Implements the core handoff data structures:
- HandoffCAS: Complete handoff with metadata and references
- FileRef: File reference with hash and depth classification
- Depth: Enumeration for depth levels (shallow/medium/full)
- Security: Explicit secret exclusion handling
"""

import hashlib
import sys
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from fnmatch import fnmatch
from pathlib import Path
from typing import Optional, Mapping, Any

# Import lib setup (automatically adds lib to sys.path)
from lib import setup_lib_path
setup_lib_path()

from jsonl_typed import (
    MetaLine,
    RefLine,
    ExLine,
    AuditLine,
    TypedLine,
    DepthLevel,
    OperationType,
    SCHEMA_VERSION,
    serialize_line,
    create_meta_line,
    parse_jsonl_file,
)
from utils import estimate_tokens_for_size


class Depth(Enum):
    """
    Depth levels for handoff packs.

    SHALLOW: ~5 files, minimal context (~150 tokens)
    MEDIUM: ~20 files, standard context (~600 tokens)
    FULL: ~50 files, complete context (~1500 tokens)
    """
    SHALLOW = "s"
    MEDIUM = "m"
    FULL = "f"

    @property
    def max_refs(self) -> int:
        """Maximum number of refs for this depth."""
        return {Depth.SHALLOW: 5, Depth.MEDIUM: 20, Depth.FULL: 50}[self]

    @property
    def max_bytes(self) -> int:
        """Maximum bytes budget for this depth."""
        return {Depth.SHALLOW: 30_000, Depth.MEDIUM: 120_000, Depth.FULL: 300_000}[self]


# Secret patterns - NEVER include these in handoffs
SECRET_PATTERNS = (
    "*.key",
    "*.pem",
    "*.cert",
    ".env*",
    "secret*",
    "*password*",
    "*credential*",
    "*token*",
    "*.credentials",
    "*.secrets",
)


def is_secret_path(path: str) -> bool:
    """
    Check if a path matches secret patterns.

    Args:
        path: File path to check (relative)

    Returns:
        True if path appears to be a secret file
    """
    path_lower = path.lower()
    return any(fnmatch(path_lower, p) for p in SECRET_PATTERNS)


def obfuscate_path(path: str) -> str:
    """
    Obfuscate a path for logging/debugging (never log secret paths directly).

    Args:
        path: Path to obfuscate

    Returns:
        Obfuscated path (preserves structure, hides name)
    """
    if is_secret_path(path):
        parts = path.split("/")
        filename = parts[-1] if parts else ""
        ext = Path(filename).suffix or ""
        return f"<SECRET>{ext}"
    return path


@dataclass(frozen=True)
class FileRef:
    """
    Reference to a file in a handoff.

    Immutable by design. Contains path, hash, and metadata.
    """
    path: str  # Relative path from repo root
    sha256: str  # SHA256 hash (8 chars)
    size: int  # File size in bytes
    mtime: int  # Unix timestamp
    depth: Depth  # Classification depth
    operation: OperationType  # Operation that created this ref

    def __post_init__(self):
        """Validate invariants after construction."""
        import re
        import time

        # Validate path is not empty
        if not self.path or not self.path.strip():
            raise ValueError("path cannot be empty")

        # Validate sha256 format (8 hex chars)
        if not re.match(r"^[a-f0-9]{8}$", self.sha256):
            raise ValueError(
                f"sha256 must be 8 hexadecimal characters: '{self.sha256}'"
            )

        # Validate size is non-negative
        if self.size < 0:
            raise ValueError(f"size must be non-negative: {self.size}")

        # Validate mtime is reasonable (not too far in future)
        current_time = time.time()
        if self.mtime <= 0:
            raise ValueError(f"mtime must be positive: {self.mtime}")
        if self.mtime > current_time + 86400:  # More than 1 day in future
            raise ValueError(
                f"mtime is too far in the future: {self.mtime} "
                f"(current: {current_time})"
            )

    def to_ref_line(self) -> RefLine:
        """Convert to RefLine for JSONL serialization."""
        return RefLine(
            t="ref",
            p=self.path,
            h=self.sha256,
            s=self.size,
            m=self.mtime,
            l=DepthLevel[self.depth.name],
            o=self.operation,
        )

    @classmethod
    def from_ref_line(cls, line: RefLine) -> "FileRef":
        """Create from RefLine."""
        return cls(
            path=line.p,
            sha256=line.h,
            size=line.s,
            mtime=line.m,
            depth=Depth[line.l.name],
            operation=line.o,
        )

    @property
    def estimated_tokens(self) -> int:
        """Estimate tokens this ref contributes to context."""
        # Use centralized token estimation utility
        return estimate_tokens_for_size(self.size)


@dataclass
class HandoffMetrics:
    """
    Metrics for handoff operations.
    """
    handoff_bytes: int = 0
    refs_count_s: int = 0  # Shallow refs
    refs_count_m: int = 0  # Medium refs
    refs_count_f: int = 0  # Full refs
    refs_count_x: int = 0  # Excluded secrets
    hydrate_depth_used: Optional[str] = None


@dataclass
class HandoffCAS:
    """
    Content-Addressed Storage Handoff.

    Mutable builder for collecting refs, with frozen snapshot capability.

    Design notes:
    - Builder is mutable (for collecting refs)
    - snapshot() returns frozen HandoffCASSnapshot
    - Not using frozen=True directly due to field mutation requirements
    - refs field is private with immutable public property
    """
    meta: MetaLine
    _refs: list[FileRef] = field(default_factory=list, repr=False, compare=False)
    excluded_secrets: int = 0
    excluded_reasons: list[str] = field(default_factory=list)
    audit_lines: list[AuditLine] = field(default_factory=list)

    @property
    def refs(self) -> tuple[FileRef, ...]:
        """Return immutable view of refs."""
        return tuple(self._refs)

    def add_ref(self, ref: FileRef) -> None:
        """Add a file reference."""
        # Security check: Never add secret paths
        if is_secret_path(ref.path):
            self.excluded_secrets += 1
            return
        self._refs.append(ref)

    def add_secret_exclusion(self, pattern: str, count: int = 1) -> None:
        """Record a secret exclusion pattern."""
        self.excluded_secrets += count
        if pattern not in self.excluded_reasons:
            self.excluded_reasons.append(pattern)

    def add_audit(self, audit: AuditLine) -> None:
        """Add an audit line."""
        self.audit_lines.append(audit)

    def classify_depth_for_path(self, path: str) -> Depth:
        """
        Classify a file path into depth level.

        Uses heuristics similar to context-memory pruning:
        - Tests, config → SHALLOW
        - src, lib, app → MEDIUM
        - Everything else → FULL (or based on depth budget)
        """
        # Shallow patterns (high value, low cost)
        shallow_patterns = ("tests/", "test_", "_test.py", ".toml", ".json", "config/")
        if any(p in path.lower() for p in shallow_patterns):
            return Depth.SHALLOW

        # Medium patterns (core source)
        medium_patterns = ("src/", "lib/", "app/", "api/")
        if any(p in path.lower() for p in medium_patterns):
            return Depth.MEDIUM

        # Default to full
        return Depth.FULL

    def create_pack(self, depth: Depth) -> list[RefLine]:
        """
        Create a pack at specified depth.

        Args:
            depth: Depth level (SHALLOW, MEDIUM, FULL)

        Returns:
            List of RefLine objects for the pack
        """
        # Filter refs by depth (using max_refs as budget)
        selected_refs: list[FileRef] = []

        # Priority: Higher depth first, then by recency
        depth_priority = {Depth.FULL: 3, Depth.MEDIUM: 2, Depth.SHALLOW: 1}

        # Sort by depth priority, then by mtime (newest first)
        sorted_refs = sorted(
            self._refs,
            key=lambda r: (
                depth_priority.get(r.depth, 0),
                -r.mtime,
            ),
            reverse=True,
        )

        # Apply budget
        total_bytes = 0
        max_bytes = depth.max_bytes
        max_count = depth.max_refs

        for ref in sorted_refs:
            if len(selected_refs) >= max_count:
                break
            if total_bytes + ref.size > max_bytes:
                break
            selected_refs.append(ref)
            total_bytes += ref.size

        # Convert to RefLine
        return [r.to_ref_line() for r in selected_refs]

    def to_jsonl_lines(self) -> list[str]:
        """
        Convert handoff to JSONL lines.

        Returns:
            List of JSON strings (without newlines)
        """
        lines: list[str] = []

        # Header meta
        lines.append(serialize_line(self.meta))

        # Refs
        for ref in self._refs:
            if not is_secret_path(ref.path):
                lines.append(serialize_line(ref.to_ref_line()))

        # Secret exclusions
        if self.excluded_secrets > 0:
            lines.append(serialize_line(ExLine(
                t="ex",
                k="secret_patterns",
                n=self.excluded_secrets,
                why=",".join(self.excluded_reasons or SECRET_PATTERNS),
            )))

        # Audit lines
        for audit in self.audit_lines:
            lines.append(serialize_line(audit))

        return lines

    def calculate_metrics(self) -> HandoffMetrics:
        """Calculate handoff metrics."""
        metrics = HandoffMetrics()

        for ref in self._refs:
            if ref.depth == Depth.SHALLOW:
                metrics.refs_count_s += 1
            elif ref.depth == Depth.MEDIUM:
                metrics.refs_count_m += 1
            elif ref.depth == Depth.FULL:
                metrics.refs_count_f += 1

        metrics.refs_count_x = self.excluded_secrets
        metrics.handoff_bytes = sum(r.size for r in self._refs)

        return metrics


def compute_sha256(path: Path) -> str:
    """
    Compute SHA256 hash of a file (first 8 chars).

    Args:
        path: Path to file

    Returns:
        First 8 characters of SHA256 hex digest
    """
    sha256 = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            sha256.update(chunk)
    return sha256.hexdigest()[:8]


def create_handoff_cas(
    repo_root: str,
    working_dir: str = ".",
    repo_id: Optional[str] = None,
) -> HandoffCAS:
    """
    Create a new HandoffCAS instance.

    Args:
        repo_root: Absolute path to repository root
        working_dir: Working directory relative to repo root
        repo_id: Optional repository ID

    Returns:
        HandoffCAS with initialized metadata
    """
    meta = create_meta_line(
        repo_root=repo_root,
        working_dir=working_dir,
        repo_id=repo_id,
    )

    return HandoffCAS(meta=meta)


def load_handoff_cas(path: Path) -> Optional[HandoffCAS]:
    """
    Load a HandoffCAS from a JSONL file.

    Args:
        path: Path to JSONL file

    Returns:
        HandoffCAS or None if file invalid
    """
    meta: Optional[MetaLine] = None
    refs: list[FileRef] = []
    excluded_secrets = 0
    excluded_reasons: list[str] = []
    audit_lines: list[AuditLine] = []

    for line in parse_jsonl_file(path):
        if isinstance(line, MetaLine):
            meta = line
        elif isinstance(line, RefLine):
            refs.append(FileRef.from_ref_line(line))
        elif isinstance(line, ExLine):
            excluded_secrets += line.n
            if line.why:
                excluded_reasons.extend(line.why.split(","))
        elif isinstance(line, AuditLine):
            audit_lines.append(line)

    if meta is None:
        return None

    handoff = HandoffCAS(
        meta=meta,
        _refs=refs,  # Use private field for internal initialization
        excluded_secrets=excluded_secrets,
        excluded_reasons=excluded_reasons,
        audit_lines=audit_lines,
    )

    return handoff

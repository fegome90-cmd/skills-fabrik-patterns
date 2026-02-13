"""
Pack Generator - Creates injectable packs from HandoffCAS

Generates three pack levels:
- pack_s: Shallow (~5 refs, ~150 tokens)
- pack_m: Medium (~20 refs, ~600 tokens)
- pack_f: Full (~50 refs, ~1500 tokens, optional)

Packs are injectable JSON files for SessionStart hook.
"""

# Depth level constants (from Depth enum max_refs)
MAX_REFS_SHALLOW = 5
MAX_REFS_MEDIUM = 20
MAX_REFS_FULL = 50

import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

# Import lib setup (automatically adds lib to sys.path)
from lib import setup_lib_path
setup_lib_path()

from handoff_cas_model import (
    HandoffCAS,
    Depth,
    FileRef,
    RefLine,
    serialize_line,
    DepthLevel,
    OperationType,
)
from utils import estimate_tokens_for_size


@dataclass(frozen=True)
class Pack:
    """
    An injectable pack with metadata and references.

    Contains everything needed for injection:
    - Header info (id, created, repo, working_dir)
    - File references (path, hash, operation)
    - Stats (count, estimated tokens)
    """
    id: str
    created: str
    repo: str
    working_dir: str
    refs: list[RefLine]
    depth_used: str
    tokens_estimated: int

    def to_injectable_dict(self) -> dict:
        """
        Convert to injectable format for SessionStart.

        Returns dictionary with all injection data.
        """
        return {
            "id": self.id,
            "created": self.created,
            "repo": self.repo,
            "working_dir": self.working_dir,
            "refs": [
                {
                    "path": r.p,
                    "hash": r.h,
                    "operation": r.o.value,
                }
                for r in self.refs
            ],
            "stats": {
                "count": len(self.refs),
                "tokens": self.tokens_estimated,
                "depth": self.depth_used,
            },
        }

    def to_json_file(self, path: Path) -> None:
        """
        Write pack as JSON file.

        Args:
            path: Output file path
        """
        data = self.to_injectable_dict()
        with open(path, "w") as f:
            json.dump(data, f, indent=2)


@dataclass(frozen=True)
class PackSet:
    """
    Complete set of packs (s, m, f) for a handoff.
    """
    handoff_id: str
    pack_s: Optional[Pack] = None
    pack_m: Optional[Pack] = None
    pack_f: Optional[Pack] = None

    def get_best_pack(self, max_tokens: int = 1000) -> Optional[Pack]:
        """
        Get best pack for token budget.

        Args:
            max_tokens: Maximum tokens allowed

        Returns:
            Best fitting pack, or None if none fit
        """
        # Try medium first (default)
        if self.pack_m and self.pack_m.tokens_estimated <= max_tokens:
            return self.pack_m

        # Fallback to shallow
        if self.pack_s and self.pack_s.tokens_estimated <= max_tokens:
            return self.pack_s

        # Last resort: full if it fits
        if self.pack_f and self.pack_f.tokens_estimated <= max_tokens:
            return self.pack_f

        return None

    def get_pack_by_depth(self, depth: str) -> Optional[Pack]:
        """
        Get pack by depth identifier.

        Args:
            depth: One of 's', 'm', 'f'

        Returns:
            Corresponding pack or None
        """
        mapping = {"s": self.pack_s, "m": self.pack_m, "f": self.pack_f}
        return mapping.get(depth)


def estimate_tokens_for_ref(ref: RefLine) -> int:
    """
    Estimate tokens for a file reference.

    Args:
        ref: File reference line

    Returns:
        Estimated tokens
    """
    # Use centralized token estimation utility
    return estimate_tokens_for_size(ref.s)


def create_pack_from_handoff(handoff: HandoffCAS, depth: Depth) -> Pack:
    """
    Create a pack at specified depth from handoff.

    Args:
        handoff: Source HandoffCAS
        depth: Target depth level

    Returns:
        Pack with references at that depth
    """
    # Get refs for this depth
    ref_lines = handoff.create_pack(depth)

    # Calculate tokens
    tokens = sum(estimate_tokens_for_ref(r) for r in ref_lines)

    return Pack(
        id=handoff.meta.id,
        created=handoff.meta.c,
        repo=handoff.meta.r,
        working_dir=handoff.meta.w,
        refs=ref_lines,
        depth_used=depth.value,
        tokens_estimated=tokens,
    )


def create_all_packs(handoff: HandoffCAS) -> PackSet:
    """
    Create all three pack levels from a handoff.

    Args:
        handoff: Source HandoffCAS

    Returns:
        PackSet with all three packs
    """
    pack_s = create_pack_from_handoff(handoff, Depth.SHALLOW)
    pack_m = create_pack_from_handoff(handoff, Depth.MEDIUM)
    pack_f = create_pack_from_handoff(handoff, Depth.FULL)

    return PackSet(
        handoff_id=handoff.meta.id,
        pack_s=pack_s,
        pack_m=pack_m,
        pack_f=pack_f,
    )


def load_pack_from_file(path: Path) -> Optional[Pack]:
    """
    Load a pack from JSON file.

    Args:
        path: Path to pack JSON file

    Returns:
        Pack or None if file invalid
    """
    if not path.exists():
        return None

    try:
        with open(path, "r") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError):
        return None

    try:
        refs = [
            RefLine(
                t="ref",
                p=r["path"],
                h=r["hash"],
                s=0,  # Size not stored in pack format
                m=0,  # mtime not stored
                l=DepthLevel.SHALLOW,  # Default depth
                o=OperationType(r["operation"]),
            )
            for r in data.get("refs", [])
        ]

        return Pack(
            id=data.get("id", ""),
            created=data.get("created", ""),
            repo=data.get("repo", ""),
            working_dir=data.get("working_dir", "."),
            refs=refs,
            depth_used=data.get("stats", {}).get("depth", "m"),
            tokens_estimated=data.get("stats", {}).get("tokens", 0),
        )
    except (KeyError, TypeError, ValueError):
        return None


def format_pack_for_injection(pack: Pack) -> str:
    """
    Format pack as injectable message for SessionStart.

    Args:
        pack: Pack to format

    Returns:
        Formatted string ready for injection
    """
    lines = [
        f"📂 Contexto cargado: {pack.id}",
        f"📁 {len(pack.refs)} archivos (depth: {pack.depth_used})",
        f"🔢 {pack.tokens_estimated} tokens estimados",
        "",
        "Archivos:",
    ]

    for ref in pack.refs:
        op_emoji = {
            "read": "📖",
            "write": "✏️",
            "edit": "✏️",
            "multi_edit": "📝",
        }.get(ref.o.value, "📄")

        lines.append(f"  {op_emoji} {ref.p}")

    return "\n".join(lines)

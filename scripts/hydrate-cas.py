#!/usr/bin/env python3
"""
Hydrate CAS - Manual command to load and inject handoff

Usage:
    /hydrate-cas [--depth=s|m|f] [--handoff-id=ID]

Options:
    --depth=s|m|f    Pack depth (default: m)
    --handoff-id=ID    Specific handoff ID (default: latest)
    --allow-content     Include truncated source code (off by default)
    --output-only      Output pack without injection formatting
"""

import argparse
import json
import sys
from pathlib import Path

# Add lib to path
lib_dir = Path(__file__).parent.parent / "lib"
sys.path.insert(0, str(lib_dir))

from pack import load_pack_from_file, create_all_packs, format_pack_for_injection
from handoff_cas_model import load_handoff_cas


def _validate_handoff_id(handoff_id: str) -> str:
    """
    Validate handoff ID to prevent path traversal attacks.

    Args:
        handoff_id: ID to validate

    Returns:
        Validated handoff ID

    Raises:
        ValueError: If handoff_id contains invalid characters
    """
    import re

    # Check for path traversal patterns
    if ".." in handoff_id or handoff_id.startswith("/"):
        raise ValueError(
            f"Invalid handoff_id: path traversal detected. "
            f"handoff_id must not contain '..' or start with '/'"
        )

    # Only allow alphanumeric, hyphens, underscores
    if not re.match(r"^[a-zA-Z0-9-_]+$", handoff_id):
        raise ValueError(
            f"Invalid handoff_id: '{handoff_id}'. "
            f"Only alphanumeric characters, hyphens, and underscores are allowed."
        )

    return handoff_id


def get_handoff_dir() -> Path:
    """Get handoffs CAS directory."""
    claude_dir = Path.home() / ".claude"
    handoff_dir = claude_dir / "handoffs-cas"
    return handoff_dir


def get_latest_handoff_id() -> str | None:
    """Get latest handoff ID from latest.jsonl pointer."""
    latest_path = get_handoff_dir() / "latest.jsonl"

    if not latest_path.exists():
        return None

    try:
        with open(latest_path, "r") as f:
            data = json.loads(f.readline().strip())
            return data.get("id")
    except (json.JSONDecodeError, OSError):
        return None


def list_handoffs() -> list[tuple[str, Path]]:
    """List available handoffs."""
    handoff_dir = get_handoff_dir()

    if not handoff_dir.exists():
        return []

    handoffs = []
    for path in handoff_dir.glob("handoff-*.jsonl"):
        # Extract ID from filename
        handoff_id = path.stem.replace("handoff-", "")
        handoffs.append((handoff_id, path))

    return sorted(handoffs, reverse=True)


def hydrate_handoff(
    handoff_id: str,
    depth: str = "m",
    allow_content: bool = False,
    output_only: bool = False,
) -> str:
    """
    Hydrate a handoff at specified depth.

    Args:
        handoff_id: Handoff ID
        depth: Depth level (s/m/f)
        allow_content: Include source code
        output_only: Output without formatting

    Returns:
        Formatted output string
    """
    # Validate handoff_id to prevent path traversal
    handoff_id = _validate_handoff_id(handoff_id)

    handoff_dir = get_handoff_dir()
    handoff_path = handoff_dir / f"handoff-{handoff_id}.jsonl"

    if not handoff_path.exists():
        return f"❌ Handoff no encontrado: {handoff_id}"

    # Load handoff
    from handoff_cas_model import load_handoff_cas
    handoff = load_handoff_cas(handoff_path)

    if handoff is None:
        return f"❌ Error al cargar handoff: {handoff_id}"

    # Check if packs exist
    packs_dir = handoff_dir / f"handoff-{handoff_id}" / "packs"

    if not packs_dir.exists():
        # Generate packs on-demand
        from pack import create_all_packs, PackSet

        pack_set = create_all_packs(handoff)

        # Ensure packs directory exists
        packs_dir.mkdir(parents=True, exist_ok=True)

        # Save packs
        if pack_set.pack_s:
            pack_set.pack_s.to_json_file(packs_dir / "pack_s.json")
        if pack_set.pack_m:
            pack_set.pack_m.to_json_file(packs_dir / "pack_m.json")
        if pack_set.pack_f:
            pack_set.pack_f.to_json_file(packs_dir / "pack_f.json")
    else:
        from pack import PackSet
        pack_set = PackSet(handoff_id=handoff_id)
        if (packs_dir / "pack_s.json").exists():
            from pack import load_pack_from_file
            pack_set.pack_s = load_pack_from_file(packs_dir / "pack_s.json")
        if (packs_dir / "pack_m.json").exists():
            from pack import load_pack_from_file
            pack_set.pack_m = load_pack_from_file(packs_dir / "pack_m.json")
        if (packs_dir / "pack_f.json").exists():
            from pack import load_pack_from_file
            pack_set.pack_f = load_pack_from_file(packs_dir / "pack_f.json")

    # Get requested pack
    pack = pack_set.get_pack_by_depth(depth)

    if pack is None:
        return f"❌ Pack no disponible: depth={depth}"

    if output_only:
        return json.dumps(pack.to_injectable_dict(), indent=2)

    return format_pack_for_injection(pack)


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Hydrate CAS - Load and inject handoff context",
        add_help=True,
    )

    parser.add_argument(
        "--depth",
        choices=["s", "m", "f"],
        default="m",
        help="Pack depth (default: m)",
    )

    parser.add_argument(
        "--handoff-id",
        type=str,
        default=None,
        help="Specific handoff ID (default: latest)",
    )

    parser.add_argument(
        "--allow-content",
        action="store_true",
        help="Include truncated source code",
    )

    parser.add_argument(
        "--output-only",
        action="store_true",
        help="Output pack without injection formatting",
    )

    parser.add_argument(
        "--list",
        action="store_true",
        help="List available handoffs",
    )

    args = parser.parse_args()

    # List handoffs
    if args.list:
        handoffs = list_handoffs()
        if not handoffs:
            print("No hay handoffs disponibles.")
            return 0

        print("Handoffs disponibles:")
        for handoff_id, path in handoffs:
            stat = path.stat()
            mtime = stat.st_mtime
            from datetime import datetime
            mtime_str = datetime.fromtimestamp(mtime).strftime("%Y-%m-%d %H:%M")
            print(f"  {handoff_id} ({mtime_str})")
        return 0

    # Get handoff ID
    handoff_id = args.handoff_id
    if handoff_id is None:
        handoff_id = get_latest_handoff_id()
        if handoff_id is None:
            print("❌ No hay handoffs disponibles.")
            print("Usa --list para ver handoffs disponibles.")
            return 1

    # Hydrate
    output = hydrate_handoff(
        handoff_id=handoff_id,
        depth=args.depth,
        allow_content=args.allow_content,
        output_only=args.output_only,
    )

    print(output)
    return 0


if __name__ == "__main__":
    sys.exit(main() or 0)

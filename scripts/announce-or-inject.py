#!/usr/bin/env python3
"""
Announce or Inject - SessionStart Hook

Auto-injects pack_m on session start, with automatic downgrade if needed.

Environment:
- CLAUDE_DIR: Claude directory (defaults to ~/.claude)
- HANDOFF_MAX_TOKENS: Maximum tokens for injection (default: 1000)
"""

import json
import os
import sys
from pathlib import Path

# Add lib to path
lib_dir = Path(__file__).parent.parent / "lib"
sys.path.insert(0, str(lib_dir))

from pack import load_pack_from_file, create_all_packs, PackSet, format_pack_for_injection


def get_handoff_dir() -> Path:
    """Get handoffs CAS directory."""
    claude_dir = Path.home() / ".claude"
    return claude_dir / "handoffs-cas"


def get_latest_handoff_id() -> str | None:
    """
    Get latest handoff ID from latest.jsonl pointer.

    Returns:
        Handoff ID or None if no pointer exists
    """
    handoff_dir = get_handoff_dir()
    latest_path = handoff_dir / "latest.jsonl"

    if not latest_path.exists():
        return None

    try:
        with open(latest_path, "r") as f:
            data = json.loads(f.readline().strip())
            return data.get("id")
    except (json.JSONDecodeError, OSError):
        return None


def get_packs_dir(handoff_id: str) -> Path:
    """Get packs directory for a handoff."""
    handoff_dir = get_handoff_dir()
    packs_dir = handoff_dir / f"handoff-{handoff_id}" / "packs"
    return packs_dir


def load_best_pack(handoff_id: str, max_tokens: int = 1000) -> str | None:
    """
    Load best pack for token budget.

    Strategy:
    1. Try pack_m first (default)
    2. Downgrade to pack_s if pack_m exceeds budget
    3. Last resort: pack_f if available and fits

    Args:
        handoff_id: Handoff ID
        max_tokens: Maximum tokens allowed

    Returns:
        Formatted injection message, or None if no pack fits
    """
    packs_dir = get_packs_dir(handoff_id)

    if not packs_dir.exists():
        return None

    # Load pack_m
    pack_m_path = packs_dir / "pack_m.json"
    pack_s_path = packs_dir / "pack_s.json"
    pack_f_path = packs_dir / "pack_f.json"

    # Try to load available packs
    packs_loaded: dict[str, "Pack"] = {}

    if pack_m_path.exists():
        from pack import load_pack_from_file
        pack = load_pack_from_file(pack_m_path)
        if pack:
            packs_loaded["m"] = pack

    if pack_s_path.exists():
        from pack import load_pack_from_file
        pack = load_pack_from_file(pack_s_path)
        if pack:
            packs_loaded["s"] = pack

    if pack_f_path.exists():
        from pack import load_pack_from_file
        pack = load_pack_from_file(pack_f_path)
        if pack:
            packs_loaded["f"] = pack

    if not packs_loaded:
        return None

    # Get best pack
    pack = packs_loaded.get("m")  # Default to medium
    if pack is None or pack.tokens_estimated > max_tokens:
        pack = packs_loaded.get("s")  # Downgrade to shallow

    if pack is None:
        pack = packs_loaded.get("f")  # Last resort

    if pack is None or pack.tokens_estimated > max_tokens:
        # No pack fits within budget
        return None

    return format_pack_for_injection(pack)


def main() -> int:
    """
    Main entry point for SessionStart hook.

    Outputs injectable pack content or summary message.
    """
    # Get max tokens from env
    max_tokens = int(os.environ.get("HANDOFF_MAX_TOKENS", "1000"))

    # Get latest handoff
    handoff_id = get_latest_handoff_id()

    if not handoff_id:
        # No handoff available
        print("📭 No hay contexto previo disponible.")
        return 0

    # Load best pack
    injection = load_best_pack(handoff_id, max_tokens)

    if injection:
        # SUCCESS - Pack injected (output goes to session)
        print(injection)
        return 0
    else:
        # No pack fits within budget
        print(f"📋 Contexto disponible pero excede budget de {max_tokens} tokens.")
        print(f"Usa /hydrate-cas --depth=s para inyectar manualmente.")
        return 0


if __name__ == "__main__":
    sys.exit(main() or 0)

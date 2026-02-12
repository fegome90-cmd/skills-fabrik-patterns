"""
Events Processor - Converts context-memory events to HandoffCAS

Processes context-memory events from JSONL storage into HandoffCAS format.
Integrates with existing context-memory modules (repo, pruning).
"""

import hashlib
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterator, Optional

# Import lib setup (automatically adds lib to sys.path)
from lib import setup_lib_path
setup_lib_path()

from handoff_cas_model import (
    HandoffCAS,
    FileRef,
    Depth,
    OperationType,
    create_handoff_cas,
    compute_sha256,
    is_secret_path,
    obfuscate_path,
    ExLine,
    AuditLine,
    SCHEMA_VERSION,
)

# Add context-memory src to path
context_memory_src = Path.home() / ".claude" / "plugins" / "context-memory" / "src"
if str(context_memory_src) not in sys.path:
    sys.path.insert(0, str(context_memory_src))

from infrastructure.storage_jsonl import JSONLStorage
from infrastructure.repo import detect_repo_from_file_path, RepoInfo
from domain.events import ContextEvent, OperationType as CMOperationType
from domain.pruning import (
    dedupe_by_path,
    sort_by_priority,
    apply_budget,
    PruningConfig,
)


@dataclass(frozen=True)
class HashResult:
    """
    Result of hash computation.

    Provides explicit error/success tracking instead of magic strings.
    """
    value: str
    is_error: bool
    error_message: str = ""

    @property
    def is_skip(self) -> bool:
        """Check if this result represents a skipped file (secret)."""
        return self.value == "skip" and not self.is_error


@dataclass
class ProcessingResult:
    """Result of processing events."""
    handoff: HandoffCAS
    events_processed: int
    events_filtered: int
    secrets_excluded: int
    working_dir: str


def compute_file_hash(file_path: Path, repo_root: Path) -> HashResult:
    """
    Compute SHA256 hash of a file.

    Security: Only computes hash for non-secret files.

    Args:
        file_path: Absolute path to file
        repo_root: Repository root path

    Returns:
        HashResult with hash value or error information
    """
    try:
        # Check if secret BEFORE computing hash
        rel_path = str(file_path.relative_to(repo_root))
        if is_secret_path(rel_path):
            return HashResult(value="skip", is_error=False)

        hash_value = compute_sha256(file_path)
        return HashResult(value=hash_value, is_error=False)
    except (OSError, ValueError) as e:
        return HashResult(value="", is_error=True, error_message=str(e))


def map_operation_type(cm_op: CMOperationType) -> OperationType:
    """Map context-memory operation type to handoff operation type."""
    mapping = {
        CMOperationType.READ: OperationType.READ,
        CMOperationType.WRITE: OperationType.WRITE,
        CMOperationType.EDIT: OperationType.EDIT,
        CMOperationType.MULTI_EDIT: OperationType.MULTI_EDIT,
    }
    return mapping.get(cm_op, OperationType.READ)


def process_events_to_handoff(
    events: list[ContextEvent],
    repo_info: RepoInfo,
    working_dir: str = ".",
    max_refs: int = 50,
    max_bytes: int = 120_000,
) -> ProcessingResult:
    """
    Process context-memory events into a HandoffCAS.

    Args:
        events: List of context-memory events
        repo_info: Repository information
        working_dir: Working directory relative to repo root
        max_refs: Maximum file references to include
        max_bytes: Maximum bytes budget

    Returns:
        ProcessingResult with handoff and metrics
    """
    # Create handoff
    handoff = create_handoff_cas(
        repo_root=str(repo_info.root),
        working_dir=working_dir,
        repo_id=repo_info.repo_id,
    )

    # Apply pruning strategy from context-memory
    config = PruningConfig(max_ops=max_refs, max_bytes_est=max_bytes)

    # Step 1: Dedupe by path
    deduped = dedupe_by_path(events)

    # Step 2: Sort by priority
    sorted_events = sort_by_priority(deduped, config)

    # Step 3: Apply budget
    budgeted = apply_budget(sorted_events, config)

    # Track metrics
    events_processed = len(events)
    events_filtered = events_processed - len(budgeted)
    secrets_excluded = 0

    # Convert events to FileRefs
    for event in budgeted:
        if not event.file_path:
            continue

        # Skip secrets (count only)
        if is_secret_path(event.file_path):
            secrets_excluded += 1
            handoff.add_secret_exclusion(event.file_path.split("/")[-1], 1)
            continue

        # Get file stats
        abs_path = repo_info.root / event.file_path
        try:
            mtime = int(abs_path.stat().st_mtime)
            size = abs_path.stat().st_size
            hash_result = compute_file_hash(abs_path, repo_info.root)

            # Handle error/skip results
            if hash_result.is_error:
                # Hash computation failed - skip this file
                continue
            elif hash_result.is_skip:
                # Secret file - already counted in secrets_excluded
                continue
            sha256 = hash_result.value
        except (OSError, ValueError):
            # File may have been deleted
            mtime = int(time.time())
            size = 0
            sha256 = "deleted"

        # Classify depth
        depth = handoff.classify_depth_for_path(event.file_path)

        # Map operation
        op = map_operation_type(event.operation)

        # Create FileRef
        ref = FileRef(
            path=event.file_path,
            sha256=sha256,
            size=size,
            mtime=mtime,
            depth=depth,
            operation=op,
        )
        handoff.add_ref(ref)

    # Update metadata
    handoff.meta.fc = len(handoff.refs)
    handoff.meta.sc = secrets_excluded > 0

    # Add audit line
    audit = AuditLine(
        t="audit",
        ts=int(time.time()),
        run="compact",
        ok=True,
        d=False,
    )
    handoff.add_audit(audit)

    return ProcessingResult(
        handoff=handoff,
        events_processed=events_processed,
        events_filtered=events_filtered,
        secrets_excluded=secrets_excluded,
        working_dir=working_dir,
    )


def load_events_from_context_memory(
    session_file: Optional[Path] = None,
) -> tuple[list[ContextEvent], Optional[RepoInfo]]:
    """
    Load events from context-memory JSONL file.

    Args:
        session_file: Path to session file (default: current.jsonl)

    Returns:
        Tuple of (events list, repo_info or None)
    """
    if session_file is None:
        session_file = (
            Path.home()
            / ".claude"
            / "context-memory"
            / "sessions"
            / "current.jsonl"
        )

    if not session_file.exists():
        return [], None

    storage = JSONLStorage(session_file)
    events = list(storage.read_all())

    if not events:
        return [], None

    # Detect repo from first event with file path
    repo_info: Optional[RepoInfo] = None
    for event in events:
        if event.file_path:
            # Convert to absolute path for detection
            # Note: event.file_path is relative, need to resolve
            # Use current directory as fallback
            try:
                abs_path = Path(event.file_path).resolve()
                repo_info = detect_repo_from_file_path(abs_path)
                if repo_info:
                    break
            except (OSError, ValueError):
                continue

    return events, repo_info


def create_handoff_from_session(
    session_file: Optional[Path] = None,
    max_refs: int = 50,
    max_bytes: int = 120_000,
) -> Optional[ProcessingResult]:
    """
    Create handoff from current context-memory session.

    Args:
        session_file: Path to session file (default: current.jsonl)
        max_refs: Maximum file references
        max_bytes: Maximum bytes budget

    Returns:
        ProcessingResult or None if no events/repo detected
    """
    # Load events
    events, repo_info = load_events_from_context_memory(session_file)

    if not events or not repo_info:
        return None

    # Get working dir (relative to repo root)
    working_dir = "."
    try:
        working_dir = str(Path.cwd().relative_to(repo_info.root))
    except (OSError, ValueError):
        working_dir = "."

    # Process events
    result = process_events_to_handoff(
        events=events,
        repo_info=repo_info,
        working_dir=working_dir,
        max_refs=max_refs,
        max_bytes=max_bytes,
    )

    return result

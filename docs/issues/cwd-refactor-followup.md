# Issue: Consolidate Duplicate Patterns in Hook Scripts

## Status: ✅ COMPLETED (2026-02-18)

## Priority
Medium - Technical Debt

## Context
During CWD extraction fix, identified ~45 lines of duplicate code across 3 scripts.

## Duplicate Patterns

### 1. Recent Files Discovery (~15 lines each)
**Files:**
- `scripts/quality-gates.py` L94-105
- `scripts/pre-compact-rescue.py` L35-49
- `scripts/stop-handoff.py` L60-71

**Pattern:**
- Same 3600-second cutoff
- Similar file extension filtering
- Same exception handling (OSError, PermissionError)

### 2. Inconsistent Extension Lists
- `quality-gates.py`, `pre-compact-rescue.py`: `.py`, `.ts`, `.tsx`, `.js`, `.jsx`, `.md`
- `stop-handoff.py`: adds `.json`

## Solution Implemented

Enhanced `get_recent_files()` in `lib/utils.py`:

```python
DEFAULT_SOURCE_EXTENSIONS: tuple[str, ...] = (
    '.py', '.ts', '.tsx', '.js', '.jsx', '.md', '.json'
)

DEFAULT_EXCLUDE_DIRS: frozenset[str] = frozenset({
    '__pycache__', '.venv', 'venv', 'node_modules', '.git', '.mypy_cache'
})

def get_recent_files(
    cwd: Path,
    hours: int = 1,
    extensions: tuple[str, ...] | list[str] | None = None,
    exclude_dirs: frozenset[str] = DEFAULT_EXCLUDE_DIRS,
    max_files: int | None = 20
) -> list[str]:
    """Get files modified within specified hours, sorted by mtime desc."""
```

**Improvements:**
- ✅ All 3 scripts now use shared `get_recent_files()`
- ✅ Added `DEFAULT_SOURCE_EXTENSIONS` constant (includes `.json`)
- ✅ Added `exclude_dirs` to skip node_modules, .venv, etc.
- ✅ Results sorted by mtime descending (most recent first)
- ✅ `max_files=None` for unlimited results
- ✅ 14 new tests added in `tests/test_utils.py`

## Benefits
- Eliminates ~45 lines of duplicate code ✅
- Standardizes behavior across hooks ✅
- Easier maintenance ✅
- Better performance (excludes heavy directories) ✅

## Related
- Completed: CWD extraction fix (get_project_path_from_stdin)

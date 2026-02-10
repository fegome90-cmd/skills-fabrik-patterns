# Skills-Fabrik Patterns Plugin

> Patterns extracted from Skills-Fabrik, injected as Claude Code hooks.

## Overview

This plugin implements proven patterns from Skills-Fabrik as non-intrusive hooks:

| Hook | Pattern | Purpose |
|------|---------|---------|
| **SessionStart** | Health Check | Verify Claude Code integrity before session |
| **UserPromptSubmit** | TAGs + Evidence | Inject semantic context + pre-validate project |
| **Stop** | Quality Gates | Parallel gate execution with alert escalation |
| **PreCompact** | Handoff + Backup | Preserve state + enable rollback |

## Installation

```bash
cd ~/.claude/plugins/skills-fabrik-patterns
python3 setup.py
```

Then enable in `~/.claude/settings.json`:

```json
{
  "enabledPlugins": {
    "skills-fabrik-patterns@local": true
  }
}
```

## Configuration

### Quality Gates (`config/gates.yaml`)

Define which quality checks run before session end:

```yaml
gates:
  - name: typescript-check
    description: TypeScript compilation check
    command: npx tsc --noEmit
    required: true
    critical: true
```

### Evidence Validation (`config/evidence.yaml`)

Pre-flight checks before starting work:

```yaml
checks:
  - name: project-structure
    description: Verify project structure is valid
    critical: true
```

### Alert Thresholds (`config/alerts.yaml`)

Configure escalation levels:

```yaml
thresholds:
  critical:
    failure_rate: 0.5  # 50% gates failed
```

## Patterns Explained

### TAGs System

Injects semantic context markers into prompts:
- `[K:identity]` - Knowledge about user identity
- `[K:projects]` - Current project context
- `[U:rules]` - User rules and preferences
- `[C:constraint]` - Known constraints

### EvidenceCLI

Validates project state before activation:
- Project structure integrity
- Dependencies installed
- Required config files present

### Quality Gates

Parallel execution of quality checks:
- TypeScript/Python compilation
- Code formatting
- Security scanning
- Custom project gates

### Handoff Protocol

Creates `.claude/handoffs/handoff-YYYYMMDD-HHMMSS.md` with:
- Completed tasks
- Next steps
- Artifacts produced
- Context snapshot

### Backup/Rollback

Deterministic state backup to `~/.claude/backups/`:
- Timestamped snapshots
- Metadata with restore commands
- One-command rollback

## Troubleshooting

### Hooks not firing

Check logs in `~/.claude/logs/` for hook execution errors.

### Quality gates timing out

Increase timeout in `.claude-plugin/hooks.json`:
```json
"timeout": 180  # 3 minutes
```

### Evidence validation failing

Run manually to debug:
```bash
echo '{"project_path": "."}' | \
  python3 ~/.claude/plugins/skills-fabrik-patterns/scripts/inject-context.py
```

## Development

Run tests:
```bash
cd ~/.claude/plugins/skills-fabrik-patterns
pytest --cov=lib --cov-report=term-missing
```

Type checking:
```bash
mypy lib/ scripts/
```

## License

MIT

## Author

Felipe González - https://github.com/felipegonzalez

# Contributing to Skills-Fabrik Patterns Plugin

> Development workflow and contribution guide for the Skills-Fabrik Patterns plugin.

---

## Overview

This plugin implements proven patterns from Skills-Fabrik as non-intrusive Claude Code hooks:

| Hook | Pattern | Purpose |
|------|---------|---------|
| **SessionStart** | Health Check | Verify Claude Code integrity before session |
| **UserPromptSubmit** | TAGs + Evidence | Inject semantic context + pre-validate project |
| **Stop** | Quality Gates | Parallel gate execution with alert escalation |
| **PreCompact** | Handoff + Backup | Preserve state + enable rollback |

---

## Prerequisites

- **Python**: 3.10 or higher
- **Git**: For version control
- **Claude Code**: Installed and configured

---

## Development Setup

### 1. Clone and Install

```bash
# Clone the repository
cd ~/.claude/plugins
git clone https://github.com/fegome90-cmd/skills-fabrik-patterns.git
cd skills-fabrik-patterns

# Run the installer
python3 setup.py
```

### 2. Enable Plugin

Add to `~/.claude/settings.json`:

```json
{
  "enabledPlugins": {
    "skills-fabrik-patterns@local": true
  }
}
```

### 3. Verify Installation

```bash
# Run health check manually
python3 scripts/health-check.py

# Expected output:
# {
#   "status": "healthy",
#   "checks": [...]
# }
```

---

## Available Scripts

| Script | Purpose | Usage |
|--------|---------|-------|
| `setup.py` | Install plugin dependencies | `python3 setup.py` |
| `scripts/health-check.py` | Run health checks | `python3 scripts/health-check.py` |
| `scripts/inject-context.py` | Test TAGs injection | `echo '{"prompt":"test"}' \| python3 scripts/inject-context.py` |
| `scripts/quality-gates.py` | Run quality gates | `python3 scripts/quality-gates.py` |
| `scripts/handoff-backup.py` | Create handoff+backup | `python3 scripts/handoff-backup.py` |

### Manual Script Testing

```bash
# Test health check
python3 ~/.claude/plugins/skills-fabrik-patterns/scripts/health-check.py

# Test inject context
echo '{"prompt": "test", "project_path": "."}' | \
  python3 ~/.claude/plugins/skills-fabrik-patterns/scripts/inject-context.py

# Test quality gates
cd /your/project
python3 ~/.claude/plugins/skills-fabrik-patterns/scripts/quality-gates.py

# Test handoff+backup
python3 ~/.claude/plugins/skills-fabrik-patterns/scripts/handoff-backup.py

# List backups
ls -la ~/.claude/backups/

# List handoffs
ls -la ~/.claude/handoffs/
```

---

## Testing

### Run Tests

```bash
# Run all tests
pytest tests/

# Run with coverage report
pytest --cov=lib --cov-report=term-missing

# Run specific test file
pytest tests/test_unit.py -v

# Run with verbose output
pytest -v
```

### Test Organization

```
tests/
├── test_unit.py           # Unit tests for individual modules
├── test_integration.py    # Integration tests for hook workflows
└── conftest.py           # Shared pytest fixtures
```

### Coverage Requirements

- **Minimum coverage**: 80%
- Use `pytest --cov` to verify before committing

---

## Type Checking

```bash
# Run mypy in strict mode
mypy lib/ scripts/

# Check specific module
mypy lib/quality_gates.py

# Continuous mode (watch for changes)
mypy lib/ --watch
```

### Type Requirements

- All function signatures must have type annotations
- `mypy --strict` must pass without errors
- Use `typing` module for complex types

---

## Code Style

### Standards

- **PEP 8** compliance (enforced by ruff)
- Maximum line length: 100 characters
- Type annotations on all functions
- Immutable data structures preferred (`@dataclass(frozen=True)`)

### Formatting

```bash
# Format code with black (if installed)
black lib/ scripts/ --line-length 100

# Sort imports with isort
isort lib/ scripts/
```

### Linting

```bash
# Run ruff linter
ruff check lib/ scripts/

# Auto-fix issues
ruff check --fix lib/ scripts/
```

---

## Project Structure

```
skills-fabrik-patterns/
├── lib/                    # Core modules
│   ├── alerts.py          # Alert escalation logic
│   ├── backup.py          # State backup/restore
│   ├── evidence_cli.py    # Evidence validation
│   ├── handoff.py         # Handoff protocol
│   ├── health.py          # Health checks
│   ├── quality_gates.py   # Quality gates orchestration
│   ├── tag_system.py      # TAG system for context
│   └── utils.py           # Shared utilities
├── scripts/               # Hook entry points
├── config/                # YAML configurations
├── tests/                 # Unit and integration tests
├── docs/                  # Documentation
├── .claude-plugin/        # Plugin manifest
├── setup.py              # Installation script
├── requirements.txt      # Python dependencies
└── README.md            # User-facing documentation
```

---

## Adding New Features

### Adding a New Hook

1. Create script in `scripts/`:
   ```python
   #!/usr/bin/env python3
   """Your hook description."""

   import sys
   from pathlib import Path

   lib_dir = Path(__file__).parent.parent / "lib"
   sys.path.insert(0, str(lib_dir))

   from your_module import your_function

   def main() -> int:
       result = your_function()
       return 0 if result else 1

   if __name__ == "__main__":
       sys.exit(main())
   ```

2. Make executable: `chmod +x scripts/your-hook.py`
3. Register in `.claude-plugin/hooks/hooks.json`
4. Add tests in `tests/`

### Adding a New Quality Gate

Edit `config/gates.yaml`:

```yaml
gates:
  - name: your-gate
    description: Your quality check description
    command: echo "running check..."
    required: false
    critical: false
    timeout: 30000
    file_patterns: ["*.py"]
```

### Adding a New Evidence Check

Edit `config/evidence.yaml`:

```yaml
checks:
  - name: your-check
    description: Your validation check
    critical: false
```

Implement check logic in `lib/evidence_cli.py`.

---

## Configuration

All configuration is file-based in `config/`:

| File | Purpose |
|------|---------|
| `alerts.yaml` | Alert escalation thresholds |
| `gates.yaml` | Quality gate definitions |
| `evidence.yaml` | Evidence validation rules |

See `docs/CONFIGURATION.md` for detailed reference.

---

## Debugging

### Enable Debug Logging

```bash
# Set environment variable
export DEBUG=1

# Run script with debug output
python3 scripts/quality-gates.py
```

### Check Hook Logs

```bash
# Claude Code logs
tail -f ~/.claude/logs/*.log

# Plugin-specific logs
tail -f ~/.claude/plugins/skills-fabrik-patterns/.claude-plugin/logs/*.log
```

### Common Issues

| Issue | Solution |
|-------|----------|
| Hooks not firing | Check `enabledPlugins` in settings.json |
| Scripts not executable | Run `chmod +x scripts/*.py` |
| Import errors | Verify lib/ is in PYTHONPATH |
| Config not loading | Check YAML syntax with `python3 -c "import yaml; yaml.safe_load(open('config/gates.yaml'))"` |

---

## Pull Request Process

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/my-feature`
3. Make changes following code style guidelines
4. Add tests for new functionality
5. Ensure all tests pass: `pytest --cov=lib`
6. Ensure type checking passes: `mypy lib/`
7. Update documentation if needed
8. Submit pull request with description

### PR Checklist

- [ ] Tests pass (`pytest`)
- [ ] Coverage ≥80% (`pytest --cov`)
- [ ] Type checking passes (`mypy --strict`)
- [ ] Code follows PEP 8
- [ ] Documentation updated
- [ ] Changelog updated (if applicable)

---

## Dependencies

### Runtime Dependencies

```
pyyaml>=6.0      # YAML configuration parsing
psutil>=5.9.0    # System resource monitoring
```

### Development Dependencies

```
pytest>=7.4.0         # Testing framework
pytest-cov>=4.1.0     # Coverage reporting
pytest-asyncio>=0.21.0 # Async test support
mypy>=1.5.0           # Type checking
```

---

## License

By contributing, you agree that your contributions will be licensed under the MIT License.

---

## Questions?

- Open an issue on GitHub
- Check existing documentation in `docs/`
- Review `README.md` for user-facing docs

# Contributing to Skills-Fabrik Patterns Plugin

Thank you for your interest in contributing!

## Development Setup

### Prerequisites

- Python 3.10+
- pytest for testing
- mypy for type checking

### Installation

```bash
# Clone the repository
git clone https://github.com/fegome90-cmd/skills-fabrik-patterns.git
cd skills-fabrik-patterns

# Install dependencies (optional - plugin uses stdlib)
pip install -r requirements.txt
```

### Running Tests

```bash
# Run all tests
pytest tests/

# Run with coverage
pytest tests/ --cov=lib --cov-report=term-missing

# Run specific test file
pytest tests/test_unit.py -v
```

### Type Checking

```bash
# Run mypy in strict mode
mypy --strict lib/
```

## Code Style

- Follow PEP 8 conventions
- Use type annotations on all function signatures
- Prefer immutable data structures (dataclasses with frozen=True)
- Maximum line length: 100 characters

## Project Structure

```
skills-fabrik-patterns/
├── lib/                    # Core modules
│   ├── alerts.py          # Alert escalation
│   ├── backup.py          # State backup/restore
│   ├── evidence_cli.py    # Evidence validation
│   ├── handoff.py         # Handoff protocol
│   ├── health.py          # Health checks
│   ├── quality_gates.py   # Quality gates orchestration
│   ├── tag_system.py      # TAG system for context
│   └── utils.py           # Shared utilities
├── scripts/               # Hook scripts
├── config/                # YAML configurations
├── tests/                 # Unit and integration tests
└── docs/                  # Documentation
```

## Adding New Hooks

1. Create script in `scripts/`
2. Add shebang: `#!/usr/bin/env python3`
3. Import from `lib/` modules
4. Return appropriate exit code (0 = success, 1 = failure)

## Adding New Quality Gates

Edit `config/gates.yaml`:

```yaml
gates:
  - name: my-gate
    description: My quality check
    command: echo "running check..."
    required: false
    critical: false
    timeout: 30000
    file_patterns: ["*.py"]
```

## Pull Request Process

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Ensure tests pass
5. Submit a pull request

## License

By contributing, you agree that your contributions will be licensed under the MIT License.

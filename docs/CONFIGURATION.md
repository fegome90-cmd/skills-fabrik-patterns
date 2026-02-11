# Configuration Reference

This document describes all configuration files for the skills-fabrik-patterns plugin.

## Overview

The plugin uses YAML configuration files in the `config/` directory:

- `alerts.yaml` - Quality alert thresholds
- `gates.yaml` - Quality gate definitions
- `evidence.yaml` - Evidence validation rules

---

## Alerts Configuration (`config/alerts.yaml`)

Defines thresholds for alert escalation based on quality gate results.

### Structure

```yaml
thresholds:
  critical:
    failure_rate: 0.5    # 50% gates failed
    timeout_rate: 0.3    # 30% gates timed out
  
  high:
    failure_rate: 0.2    # 20% gates failed
    timeout_rate: 0.1    # 10% timed out
  
  medium:
    failure_rate: 0.1    # 10% gates failed
    timeout_rate: 0.05   # 5% timed out
  
  low:
    failure_rate: 0.05   # 5% gates failed
    timeout_rate: 0.02   # 2% timed out
```

### Threshold Behavior

Alerts are generated when metrics exceed thresholds. The system checks in order:
1. **Critical** → Blocks session end
2. **High** → Warning displayed
3. **Medium** → Info displayed
4. **Low** → Minimal notification

### Severity Levels

| Level | Emoji | Session Block | Use Case |
|-------|-------|---------------|----------|
| CRITICAL | 🔴 | Yes | >50% failures, security issues |
| HIGH | 🟠 | No | >20% failures, performance degradation |
| MEDIUM | 🟡 | No | >10% failures, code quality concerns |
| LOW | 🟢 | No | >5% failures, minor issues |
| INFO | 🔵 | No | Informational only |

---

## Gates Configuration (`config/gates.yaml`)

Defines quality checks that run before session end.

### Gate Definition

```yaml
gates:
  - name: gate-name
    description: Human-readable description
    command: shell command to execute
    required: true/false        # Must pass for session end
    critical: true/false         # Failure blocks session
    timeout: milliseconds        # Max execution time
    file_patterns: ["*.py"]      # Files that trigger this gate
```

### Built-in Gates

| Name | Description | Critical | Timeout |
|------|-------------|----------|---------|
| `typescript-check` | TypeScript compilation | No | 60s |
| `python-type-check` | Mypy type checking | No | 30s |
| `format-check` | Code formatting validation | No | 20s |
| `security-check` | Hardcoded secrets detection | Yes | 10s |

### Execution Modes

- **Parallel**: Gates run simultaneously (default)
- **Fail-fast**: Stops on first critical gate failure
- **Timeout**: Global timeout for all gates (default: 120s)

### File Pattern Matching

Gates only run when matching files are detected:

```yaml
file_patterns:
  - "*.py"      # Python files
  - "*.ts"      # TypeScript files
  - "*.tsx"     # TypeScript JSX files
```

---

## Evidence Configuration (`config/evidence.yaml`)

Defines validation rules for project evidence.

### Check Types

1. **ProjectStructureCheck** - Validates required project files
2. **DependencyCheck** - Validates dependency presence
3. **ConfigFileCheck** - Validates configuration files

### Example

```yaml
checks:
  - name: project-structure
    type: project_structure
    critical: true
    indicators:
      - package.json
      - tsconfig.json
      - README.md
```

---

## Environment Variables

No environment variables required. All configuration is file-based.

---

## Reloading Configuration

Configuration files are read on each hook execution. No restart needed.

To test configuration changes:

```bash
# Run quality gates manually
python3 scripts/quality-gates.py

# Run health check
python3 scripts/health-check.py
```

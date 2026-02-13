# AB Testing Framework: Skills-Fabrik-Patterns Plugin

## Overview

This document defines the AB testing approach for validating the skills-fabrik-patterns plugin. Two groups will test the plugin using different approaches:

- **Group A (Structured)**: Agents explicitly test each pattern with focused test cases
- **Group B (Real-World)**: Agents perform natural tasks that trigger plugin functionality

## Plugin Architecture

### 11 Patterns Implemented

| # | Pattern | File | Purpose |
|---|---------|------|----------|
| 1 | TAGs System | `lib/tag_system.py` | Context injection with `[K:identity]`, `[U:rules]`, `[C:triggers]` |
| 2 | EvidenceCLI | `lib/evidence_cli.py` | Pre-activation project validation |
| 3 | Quality Gates | `lib/quality_gates.py` | Parallel checks with timeout/fail-fast |
| 4 | Handoff Protocol | `lib/handoff.py` | Session state preservation |
| 5 | Health Check | `lib/health.py` | Claude Code integrity verification |
| 6 | Structured Logger | `lib/logger.py` | Context-aware logging |
| 7 | State Backup | `lib/backup.py` | Backup with rollback capability |
| 8 | Quality Alerts | `lib/alerts.py` | Alert escalation by severity |
| 9 | KPI Logger | `lib/kpi_logger.py` | Session metrics in `~/.claude/kpis/events.jsonl` |
| 10 | Ruff Formatter | `lib/ruff_formatter.py` | Python auto-formatting |
| 11 | FP Utils | `lib/fp_utils.py` | Functional programming utilities |

### Existing Test Suite

```
Total Tests: ~170
├── Integration Tests: 30/31 (97% pass rate)
│   ├── test_tags_evidence_integration.py
│   ├── test_quality_gates_config.py
│   ├── test_handoff_backup_coordination.py
│   └── test_logger_kpi_integration.py
├── Hooks Tests: 50/50+ passing
│   ├── test_session_start_hook.py
│   ├── test_user_prompt_submit_hook.py
│   ├── test_pre_compact_hook.py
│   ├── test_post_tool_use_hook.py
│   └── test_stop_hook.py
├── E2E Tests: 20/25+ passing
│   ├── test_full_lifecycle.py
│   ├── test_quality_gates_e2e.py
│   └── test_handoff_e2e.py
└── Performance Tests: Executing
    ├── test_hooks_performance.py
    └── test_quality_gates_performance.py
```

## AB Testing Design

### Group A: Structured Pattern Testing

Agents focus on explicitly testing each pattern with targeted test cases.

**Task List:**
```python
GROUP_A_TASKS = [
    "Extrae TAGs del contexto y valida formato",
    "Ejecuta Quality Gates con config personalizada",
    "Valida proyecto con EvidenceCLI antes de trabajar",
    "Crea Handoff con sesión completa",
    "Verifica Health Check al inicio de sesión",
    "Ejecuta backup de archivos críticos",
    "Genera alertas de calidad",
    "Loguea KPIs de sesión",
]
```

**Prompt Template:**
```
Tu tarea es probar el patrón [PATTERN_NAME] del plugin skills-fabrik-patterns.

Ejecuta específicamente:
1. [Pasos específicos del test]
2. [Validaciones esperadas]

Referencias:
- Archivo: lib/[pattern_file].py
- Tests: tests/integration/test_[pattern].py

Reportea:
- Resultado del test (PASSED/FAILED)
- Tiempo de ejecución
- Cualquier error encontrado
```

### Group B: Real-World Task Scenarios

Agents perform natural tasks that trigger plugin functionality automatically.

**Task List:**
```python
GROUP_B_TASKS = [
    "Inicia una sesión y trabaja en un feature simple",
    "Escribe código Python y deja que se auto-formatee",
    "Cierra la sesión y verifica que se creó handoff",
    "Corrige un bug en código existente",
    "Añade una nueva regla de contexto",
    "Valida un proyecto Python antes de modificarlo",
    "Revisa métricas de calidad de sesión anterior",
]
```

**Prompt Template:**
```
Necesito [TAREA COTIDIANA].

Por favor:
1. Compreta la tarea
2. Ejecútala usando las herramientas disponibles
3. Reportea el resultado

El plugin skills-fabrik-patterns está activo y debería ayudarte automáticamente.
```

## Metrics Capture

| Metric | Group A | Group B | Measurement |
|--------|----------|----------|-------------|
| Completion Time | ⏱️ | ⏱️ | Time per task |
| Tasks Completed | ✅ | ✅ | Success rate |
| Errors Found | 🐛 | 🐛 | Bug discovery |
| Plugin Features Used | 📊 | 📊 | Feature coverage |
| User Satisfaction | 😊 | 😊 | Perceived UX |

## Execution Plan

### Phase 1: Setup (Completed)
- [x] Create team structure
- [x] Define AB testing framework
- [x] Create task list

### Phase 2: Parallel Execution (Current)
- [ ] Assign tasks to Group A agents (structured)
- [ ] Assign tasks to Group B agents (real-world)
- [ ] Execute in parallel to avoid time bias

### Phase 3: Analysis
- [ ] Compare results between groups
- [ ] Analyze efficiency, quality, coverage
- [ ] Identify patterns that work best in each approach

### Phase 4: Report
- [ ] Generate validation report
- [ ] Provide recommendations based on findings

## Success Criteria

1. ✅ AB testing executed with both groups
2. ✅ Comparative report generated
3. ✅ Metrics captured for both groups
4. ✅ All 11 patterns involved (Group A) or touched naturally (Group B)
5. ✅ Recommendations based on results

## References

- Plugin Location: `~/.claude/plugins/skills-fabrik-patterns/`
- Test Directory: `~/.claude/plugins/skills-fabrik-patterns/tests/`
- Team Config: `~/.claude/teams/skills-fabrik-patterns-test-team/config.json`
- Tasks Directory: `~/.claude/tasks/skills-fabrik-patterns-test-team/`

---

*Created: 2025-02-11*
*Status: READY FOR EXECUTION*

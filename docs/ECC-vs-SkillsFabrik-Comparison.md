# Comparación: Hook PreCompact (ECC) vs Handoff (Skills-Fabrik)

## Contexto

Análisis comparativo entre el sistema de hooks PreCompact de Everything Claude Code (ECC) y el sistema de Handoff con PreCompact del plugin Skills-Fabrik Patterns.

## Tabla Comparativa

| Aspecto | ECC - PreCompact | Skills-Fabrik - Handoff PreCompact |
|---------|-----------------|-------------------------------------|
| **Propósito** | No tiene hook PreCompact nativo - solo usa PreToolUse, PostToolUse, Stop | Preservar estado de sesión antes del compactado para continuación seamless |
| **Trigger** | N/A (no existe) | `PreCompact` - antes de que Claude Code compacte el contexto |
| **Archivo** | `ecc-hooks.ts` (OpenCode plugin) | `scripts/handoff-backup.py` |
| **Tecnología** | TypeScript (OpenCode plugin system) | Python 3 |
| **Funcionalidad Principal** | N/A | 1. Crear documento handoff para próxima sesión<br>2. Backup del estado de contexto con capacidad de rollback<br>3. Limpieza de backups antiguos |
| **Datos Preservados** | - Session tracking via `editedFiles` Set | - Session ID (timestamp)<br>- Completed tasks<br>- Next steps<br>- Artifacts (archivos recientes)<br>- Context snapshot (CLAUDE.md)<br>- Notes |
| **Formato Salida** | Logging a consola via `client.app.log()` | Markdown (`.md`) + JSON (`.json`) |
| **Ubicación Handoffs** | N/A | `~/.claude/handoffs/` |
| **Ubicación Backups** | N/A | `~/.claude/backups/` |
| **Cleanup Strategy** | `editedFiles.clear()` al terminar sesión | Mantiene últimos 30 handoffs, últimos 10 backups |
| **Rollback Capability** | No | Sí - comando restore incluido en metadata |
| **Integración Contexto** | Detecta CLAUDE.md al inicio sesión | Lee archivos de contexto:<br>- CLAUDE.md<br>- identity.md<br>- projects.md<br>- preferences.md<br>- rules.md |
| **Async Execution** | No | Sí (`"async": true` en quality gates) |
| **Timeout** | N/A | 30s para handoff, 120s para quality gates |
| **Handoff Protocol** | No | Sí - estructura `Handoff` dataclass con:<br>- from_session<br>- to_session<br>- completed_tasks<br>- next_steps<br>- artifacts<br>- timestamp<br>- context_snapshot<br>- notes |
| **Backup System** | No | Sí - `StateBackup` class con:<br>- create_backup()<br>- restore_backup()<br>- list_backups()<br>- cleanup_old_backups() |

---

## Archivos Clave

### Everything Claude Code (ECC)
- `/Users/felipe_gonzalez/.claude/plugins/marketplaces/everything-claude-code/.opencode/plugins/ecc-hooks.ts`
- Hooks: `file.edited`, `tool.execute.after`, `tool.execute.before`, `session.created`, `session.idle`, `session.deleted`

### Skills-Fabrik Patterns
- `/Users/felipe_gonzalez/.claude/plugins/skills-fabrik-patterns/.claude-plugin/hooks/hooks.json`
- `/Users/felipe_gonzalez/.claude/plugins/skills-fabrik-patterns/scripts/handoff-backup.py`
- `/Users/felipe_gonzalez/.claude/plugins/skills-fabrik-patterns/lib/handoff.py`
- `/Users/felipe_gonzalez/.claude/plugins/skills-fabrik-patterns/lib/backup.py`

---

## Hooks Configurados (Skills-Fabrik)

```json
{
  "SessionStart": ["health-check.py"],
  "UserPromptSubmit": ["inject-context.py"],
  "Stop": ["quality-gates.py"],
  "PreCompact": ["handoff-backup.py"],
  "PostToolUse": ["auto-fix.py"]
}
```

---

## Diferencias Arquitectónicas

### ECC (OpenCode)
- **Más simple**: Solo logging y validaciones en tiempo real
- **Event-driven**: Reacciona a eventos específicos de archivos
- **Sin persistencia**: No guarda estado entre sesiones

### Skills-Fabrik
- **Más completo**: Sistema completo de handoff + backup
- **Stateful**: Preserva estado completo para recuperación
- **Protocolo estructurado**: Handoff dataclass con formato definido
- **Rollback capability**: Puede restaurar estado anterior

---

## Análisis Técnico Profundo

### 1. Arquitectura de Datos

#### Skills-Fabrik: Handoff Dataclass

```python
@dataclass(frozen=True)
class Handoff:
    from_session: str      # ID sesión origen
    to_session: str         # ID sesión destino
    completed_tasks: list[str] # Tareas completadas
    next_steps: list[str]    # Próximos pasos
    artifacts: list[str]      # Archivos creados
    timestamp: str           # ISO format
    context_snapshot: dict[str, Any]  # Estado contexto
    notes: str = ""         # Notas adicionales
```

**Patrón**: Inmutabilidad (`frozen=True`) + tipo fuerte
**Ventaja**: Previene mutaciones accidentales, facilita serialización

#### ECC: EditedFiles Tracking

```typescript
const editedFiles = new Set<string>()  // Mutable!
```

**Patrón**: Mutable Set, tracking en memoria
**Limitación**: Se pierde al terminar sesión, no hay persistencia

---

### 2. Protocolo de Serialización

#### Skills-Fabrik: Dual Format

```python
# Markdown para human reading
handoff_path.write_text(handoff.format())

# JSON para programmatic access
json_path.write_text(json.dumps(asdict(handoff), indent=2))
```

**Estrategia**: Write-through caching dual
**Beneficio**: Human-readable + machine-readable

#### ECC: Console Logging Only

```typescript
client.app.log("info", `[ECC] Session idle - running console.log audit`)
```

**Estrategia**: Logging transciente
**Limitación**: No hay recoverabilidad posterior

---

### 3. Sistema de Backup

#### Skills-Fabrik: Deterministic Backup

```python
@dataclass(frozen=True)
class BackupMetadata:
    timestamp: str
    backup_id: str           # YYYYMMDD-HHMMSS
    files_backed_up: list[str]
    reason: str                # "pre-compact", "manual", etc.
    restore_command: str         # Self-documenting!
```

**Características únicas**:
- **Self-documenting restore**: El comando de restauración está en el metadata
- **Timestamp deterministic**: Formato que permite sorting cronológico
- **Reason tracking**: Saber por qué se creó cada backup

#### ECC: Sin Backup

No existe implementación de backup.

---

### 4. Cleanup Strategy

#### Skills-Fabrik: Configurable Retention

```python
# Handoffs: 30 días
removed_handoffs = handoff_protocol.cleanup_old_handoffs(keep=30)

# Backups: 10 unidades
removed_backups = backup_system.cleanup_old_backups(keep=10)
```

**Design decision**: Retención diferente por tipo de dato
**Rationale**: Handoffs son más valiosos para contexto histórico

#### ECC: Simple Clear

```typescript
editedFiles.clear()  // Solo limpia tracking en memoria
```

---

### 5. Extracción de Tareas (NLP)

#### Skills-Fabrik: Regex Multi-Patrón

```python
def _extract_tasks(self, text: str) -> list[str]:
    # Patrón 1: Items numerados
    numbered = re.findall(r'^\d+\.?\s+(.+)$', text, re.MULTILINE)

    # Patrón 2: Bullet points
    bulleted = re.findall(r'^[-*]\s+(.+)$', text, re.MULTILINE)

    # Patrón 3: Delimitadores comunes
    for delimiter in ['\n', ';', ',']:
        # Split logic
```

**Capacidad**: Parsing de lenguaje natural para estructuras de tareas
**Fallback**: Retorna texto completo como single task

#### ECC: Sin extracción

No hay parsing de tareas en ECC.

---

### 6. Hook Lifecycle Comparison

| Phase | ECC (OpenCode) | Skills-Fabrik |
|-------|-----------------|----------------|
| **SessionStart** | `session.created` → Load CLAUDE.md | `health-check.py` → Validate plugin |
| **UserPromptSubmit** | N/A | `inject-context.py` → TAGs + Evidence |
| **PreToolUse** | `tool.execute.before` → Security checks | N/A |
| **PostToolUse** | `tool.execute.after` → TSC check | `auto-fix.py` → Auto-corrections |
| **PreCompact** | ❌ No existe | ✅ `handoff-backup.py` → State preservation |
| **Stop** | `session.idle` → Console audit | `quality-gates.py` → Final validation |

---

### 7. Error Handling

#### Skills-Fabrik: Graceful Degradation

```python
try:
    # File operations
except (OSError, PermissionError) as e:
    logging.warning(f"Failed to discover: {e}")
    # Continue execution, don't fail
```

**Estrategia**: Never block session start
**Log level**: Warning para problemas recuperables

#### ECC: Try-Catch with Silent Continue

```typescript
try {
    await $`prettier --write ${event.path}`
    client.app.log("info", `[ECC] Formatted: ${event.path}`)
} catch {
    // Prettier not installed or failed - silently continue
}
```

**Estrategia**: Similar - silent continue en errores
**Diferencia**: No hay logging del error

---

### 8. Timeout Configuration

```json
{
  "PreCompact": {
    "timeout": 30  // 30s para handoff + backup
  },
  "Stop": {
    "timeout": 120,  // 120s para quality gates
    "async": true    // No bloquea sesión
  }
}
```

**Rationale**: Quality gates pueden ser más lentos (validaciones extensas)

---

## Conclusión

**Skills-Fabrik's PreCompact Handoff es significativamente más robusto** que el sistema de hooks de ECC:

1. **Preservación de estado**: ECC no tiene mecanismo de preservación entre sesiones
2. **Rollback**: Solo Skills-Fabrik tiene capacidad de rollback
3. **Handoff Protocol**: Estructura formal para transferir contexto entre sesiones
4. **Backup system**: Doble safety (handoff + backup)
5. **Dataclass inmutable**: Previene corrupción de datos
6. **Dual format storage**: Human + machine readable
7. **Self-documenting restore**: Comando de recuperación incluido
8. **NLP task extraction**: Parsing inteligente de lenguaje natural

ECC se enfoca en **validación en tiempo real** (formatting, type checking, console.log detection), mientras Skills-Fabrik se enfoca en **continuidad de sesión a largo plazo** con recovery capability.

---

## Código de Referencia

### ECC Hook (TypeScript)

```typescript
// ECC Session Idle Hook (equivalente a Stop)
"session.idle": async () => {
  if (editedFiles.size === 0) return

  client.app.log("info", "[ECC] Session idle - running console.log audit")

  // Audit logic...
  editedFiles.clear()
}
```

### Skills-Fabrik Handoff (Python)

```python
# Handoff Protocol
@dataclass(frozen=True)
class Handoff:
    from_session: str
    to_session: str
    completed_tasks: list[str]
    next_steps: list[str]
    artifacts: list[str]
    timestamp: str
    context_snapshot: dict[str, Any]
    notes: str = ""

    def format(self) -> str:
        """Format handoff as markdown document."""
        # Formato markdown con secciones
```

---

**Fecha**: 2025-02-11
**Versión**: 1.0
**Autor**: Análisis técnico comparativo

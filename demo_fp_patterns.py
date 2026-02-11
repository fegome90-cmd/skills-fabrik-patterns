#!/usr/bin/env python3
"""Demo de patrones FP con Result/Either types."""

import sys
from pathlib import Path

# Add lib to path
lib_dir = Path(__file__).parent / "lib"
sys.path.insert(0, str(lib_dir))

from returns.result import Success, Failure
from fp_utils import (
    load_config,
    validate_project_structure,
    safe_execute_command,
    safe_write_file,
    get_or_log
)
from logger import get_logger, LogLevel

logger = get_logger(__name__)


def demo_result_types():
    """Demo del sistema Result/Either."""
    print("\n" + "="*60)
    print("🎯 DEMO: Patrones Funcionales (Result/Either)")
    print("="*60 + "\n")

    # Demo 1: Cargar configuración con Result type
    print("1️⃣ Demo: load_config() → Result[dict, ConfigError]")
    print("-" * 55)

    result = load_config(Path("config/gates.yaml"))

    def procesar_config(resultado):
        """Pattern matching con Result type."""
        match resultado:
            case Success(config):
                logger.info(f"✅ Config cargada: {len(config.get('gates', []))} gates")
                return config
            case Failure(error):
                logger.error(f"❌ Error cargando config: {error.reason}")
                return {}

    config = procesar_config(result)

    # Demo 2: Validar estructura con Result type
    print("\n2️⃣ Demo: validate_project_structure() → Result[dict, ValidationError]")
    print("-" * 55)

    result = validate_project_structure(Path.cwd())

    def procesar_validacion(resultado):
        """Pattern matching con Result type."""
        match resultado:
            case Success(metadata):
                logger.info(f"✅ Estructura válida")
                logger.info(f"   Indicadores: {metadata['indicators_found']}")
            case Failure(error):
                logger.warning(f"⚠️ Validación falló: {error.reason}")

    procesar_validacion(result)

    # Demo 3: Recuperación con get_or_log
    print("\n3️⃣ Demo: get_or_log() → Recuperación con default")
    print("-" * 55)

    # Crear un Result que falla
    failure_result: Failure = load_config(Path("nonexistent.yaml"))

    # Usar get_or_log para recuperar con default
    default_config = {"gates": [], "version": "1.0"}
    config_recuperado = get_or_log(
        failure_result,
        default_config,
        "load_config_nonexistent"
    )

    logger.info(f"Config recuperado: {len(config_recuperado.get('gates', []))} gates")

    # Demo 4: Operaciones seguras con Result type
    print("\n4️⃣ Demo: safe_write_file() → Result[Path, FileSystemError]")
    print("-" * 55)

    write_result = safe_write_file(
        Path("/tmp/demo_result.txt"),
        "Contenido de prueba desde skills-fabrik-patterns"
    )

    match write_result:
        case Success(path):
            logger.info(f"✅ Archivo escrito: {path}")
            # Limpiar
            path.unlink()
        case Failure(error):
            logger.error(f"❌ Error escribiendo: {error.reason}")


def demo_pattern_matching():
    """Demo de pattern matching con Result types."""
    print("\n" + "="*60)
    print("🎯 DEMO: Pattern Matching con Result")
    print("="*60 + "\n")

    def dividir_con_result(a: int, b: int) -> float | None:
        """División que retorna Result en lugar de excepción."""
        if b == 0:
            from fp_utils import ExecutionError
            return Failure(ExecutionError("división", "División por cero"))

        return Success(a / b)

    # Probar diferentes casos
    print("5️⃣ Demo: División con Result type")
    print("-" * 55)

    # Caso exitoso
    resultado1 = dividir_con_result(10, 2)
    match resultado1:
        case Success(valor):
            print(f"   ✅ 10 / 2 = {valor}")
        case Failure(error):
            print(f"   ❌ Error: {error.reason}")

    # Caso fallido
    resultado2 = dividir_con_result(10, 0)
    match resultado2:
        case Success(valor):
            print(f"   ✅ Resultado: {valor}")
        case Failure(error):
            print(f"   ❌ Error esperado: {error.reason}")


def demo():
    """Ejecutar todas las demos FP."""
    # Configurar logging para ver resultados
    from logger import configure_global_logging
    configure_global_logging(level=LogLevel.INFO)

    demo_result_types()
    demo_pattern_matching()

    print("\n" + "="*60)
    print("✅ Demo FP completada!")
    print("="*60 + "\n")


if __name__ == "__main__":
    demo()

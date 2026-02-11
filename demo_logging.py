#!/usr/bin/env python3
"""Demo del sistema de logging estructurado."""

import sys
from pathlib import Path

# Add lib to path
lib_dir = Path(__file__).parent / "lib"
sys.path.insert(0, str(lib_dir))

from logger import (
    get_logger,
    LogLevel,
    log_execution,
    log_async_execution,
    configure_global_logging
)
import asyncio


# Configurar logging global
configure_global_logging(level=LogLevel.INFO, json_format=False)

# Obtener logger
logger = get_logger(__name__)


@log_execution(level=LogLevel.INFO, log_args=True, log_result=True)
def procesar_usuario(user_id: str, accion: str) -> str:
    """Función de ejemplo con decorator de logging."""
    logger.info(f"Procesando acción: {accion} para usuario: {user_id}")
    return f"Usuario {user_id} procesado exitosamente"


@log_async_execution(level=LogLevel.DEBUG, log_args=True)
async def async_query_database(query: str) -> str:
    """Función async de ejemplo con decorator de logging."""
    logger.debug(f"Ejecutando query: {query[:30]}...")
    await asyncio.sleep(0.01)  # Simular DB call
    return "Resultados de la query"


def demo_context_manager():
    """Demo del context manager para logs."""
    logger.info("=== Iniciando demo de context manager ===")

    # Usar contexto con metadatos adicionales
    with logger.context(request_id="req-123", user_id="user-456"):
        logger.info("Procesando request con contexto")

    logger.info("=== Context manager demo completada ===")


def demo_log_levels():
    """Demo de todos los niveles de log."""
    logger.debug("Este es un mensaje DEBUG")
    logger.info("Este es un mensaje INFO")
    logger.warning("Este es un mensaje WARNING")
    logger.error("Este es un mensaje ERROR")
    logger.critical("Este es un mensaje CRITICAL")


def demo():
    """Ejecutar todas las demos."""
    print("\n" + "="*60)
    print("🎯 DEMO: Sistema de Logging Estructurado")
    print("="*60 + "\n")

    # Demo 1: Log levels
    print("1️⃣ Demo: Niveles de Log")
    print("-" * 40)
    demo_log_levels()

    # Demo 2: Context manager
    print("\n2️⃣ Demo: Context Manager")
    print("-" * 40)
    demo_context_manager()

    # Demo 3: Decorator de ejecución
    print("\n3️⃣ Demo: Decorator @log_execution")
    print("-" * 40)
    resultado = procesar_usuario("user-123", "login")
    print(f"   Resultado: {resultado}")

    # Demo 4: Decorator async
    print("\n4️⃣ Demo: Decorator @log_async_execution")
    print("-" * 40)
    async def run_async_demo():
        result = await async_query_database("SELECT * FROM users")
        print(f"   Resultado async: {result}")

    asyncio.run(run_async_demo())

    print("\n" + "="*60)
    print("✅ Demo completada!")
    print("="*60 + "\n")


if __name__ == "__main__":
    demo()

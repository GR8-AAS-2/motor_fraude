"""Cálculo determinístico del hash de integridad de una póliza.

El hash se calcula sobre 8 campos clave, normalizando su representación para que
el mismo dato produzca siempre el mismo hash sin importar si viene de una
petición HTTP directa (con tipos Python/Pydantic) o de un `detalle` JSON
recuperado de un log de auditoría (con tipos JSON crudos).
"""

import hashlib
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

# Orden fijo: es parte del contrato del hash, nunca debe cambiar sin
# invalidar (y volver a calcular) todos los hashes ya almacenados.
CAMPOS_HASH = [
    "numero_poliza",
    "tipo_documento",
    "documento_identidad",
    "ramo",
    "tipo_cobertura",
    "monto_asegurado",
    "fecha_inicio_vigencia",
    "fecha_fin_vigencia",
]


def _normalizar_monto(valor: Any) -> str:
    try:
        # Decimal(str(valor)) evita los problemas de precisión de float.
        # Se fuerza a 2 decimales (estándar monetario) para que "500000",
        # "500000.0" y "500000.00" normalicen todos al mismo valor: el
        # formato "f" de Decimal, a diferencia de normalize(), no colapsa
        # ceros decimales por sí solo.
        decimal_valor = Decimal(str(valor)).quantize(Decimal("0.01"))
        return format(decimal_valor, "f")
    except (InvalidOperation, ValueError, TypeError):
        return str(valor).strip()


def _normalizar_fecha(valor: Any) -> str:
    if isinstance(valor, datetime):
        return valor.date().isoformat()
    if isinstance(valor, date):
        return valor.isoformat()
    # Se asume string; si viene con hora (ISO datetime), nos quedamos solo
    # con la parte de fecha (YYYY-MM-DD) para que sea consistente.
    return str(valor).strip()[:10]


def _normalizar_valor(campo: str, valor: Any) -> str:
    if valor is None:
        return ""
    if campo == "monto_asegurado":
        return _normalizar_monto(valor)
    if campo in ("fecha_inicio_vigencia", "fecha_fin_vigencia"):
        return _normalizar_fecha(valor)
    return str(valor).strip()


def calcular_hash_poliza(datos: dict[str, Any]) -> str:
    """Calcula el SHA-256 canónico de los 8 campos de una póliza."""
    partes = [_normalizar_valor(campo, datos.get(campo)) for campo in CAMPOS_HASH]
    cadena_canonica = "|".join(partes)
    return hashlib.sha256(cadena_canonica.encode("utf-8")).hexdigest()

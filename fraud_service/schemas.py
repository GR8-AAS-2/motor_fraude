"""Modelos de validación de entrada."""

from datetime import date
from decimal import Decimal

from pydantic import BaseModel, Field


class DatosPoliza(BaseModel):
    """Los 8 campos que identifican y describen una póliza para efectos de
    cálculo de hash (registro y validación)."""

    numero_poliza: str = Field(..., min_length=1, max_length=100)
    tipo_documento: str = Field(..., min_length=1, max_length=50)
    documento_identidad: str = Field(..., min_length=1, max_length=50)
    ramo: str = Field(..., min_length=1, max_length=100)
    tipo_cobertura: str = Field(..., min_length=1, max_length=100)
    monto_asegurado: Decimal
    fecha_inicio_vigencia: date
    fecha_fin_vigencia: date

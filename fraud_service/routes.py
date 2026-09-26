"""Endpoints del servicio de motor de fraude."""

import hmac
import json
import logging

from flask import Blueprint, jsonify, request
from pydantic import ValidationError

from .audit_client import AuditClientError, obtener_log_creacion_poliza
from .auth import require_api_key
from .hashing import CAMPOS_HASH, calcular_hash_poliza
from .schemas import DatosPoliza
from .supabase_client import TABLE_NAME, SupabaseConfigError, get_supabase_client

logger = logging.getLogger(__name__)

bp = Blueprint("fraude", __name__)


def _validation_errors(exc: ValidationError) -> list:
    """Ver nota equivalente en poliza_seguridad: exc.errors() puede incluir
    objetos no serializables en `ctx`; exc.json() sí es JSON-safe."""
    return json.loads(exc.json())


def _parse_datos_poliza(payload) -> tuple[DatosPoliza | None, tuple | None]:
    """Valida el payload. Devuelve (datos, None) o (None, (response, status))."""
    if payload is None:
        return None, (jsonify({"error": "Body JSON inválido o ausente"}), 400)
    try:
        return DatosPoliza(**payload), None
    except ValidationError as exc:
        return None, (
            jsonify({"error": "Datos inválidos", "detalles": _validation_errors(exc)}),
            400,
        )


@bp.get("/api/health")
def health():
    return jsonify({"status": "ok"})


@bp.post("/api/polizas/hash")
@require_api_key
def registrar_hash():
    datos, error = _parse_datos_poliza(request.get_json(silent=True))
    if error:
        return error

    hash_valor = calcular_hash_poliza(datos.model_dump(mode="json"))

    try:
        client = get_supabase_client()
        existente = (
            client.table(TABLE_NAME)
            .select("id")
            .eq("numero_poliza", datos.numero_poliza)
            .execute()
        )
        if existente.data:
            return (
                jsonify(
                    {
                        "error": (
                            f"Ya existe un hash registrado para la póliza "
                            f"'{datos.numero_poliza}'. No se sobrescribe."
                        )
                    }
                ),
                409,
            )

        result = (
            client.table(TABLE_NAME)
            .insert({"numero_poliza": datos.numero_poliza, "hash": hash_valor})
            .execute()
        )
    except SupabaseConfigError as exc:
        return jsonify({"error": str(exc)}), 500
    except Exception:
        logger.exception("Error al registrar hash de póliza")
        return jsonify({"error": "Error al guardar el hash en la base de datos"}), 502

    return jsonify(result.data[0]), 201


@bp.post("/api/polizas/validar")
@require_api_key
def validar_poliza():
    datos, error = _parse_datos_poliza(request.get_json(silent=True))
    if error:
        return error

    hash_recibido = calcular_hash_poliza(datos.model_dump(mode="json"))

    try:
        client = get_supabase_client()
        result = (
            client.table(TABLE_NAME)
            .select("hash")
            .eq("numero_poliza", datos.numero_poliza)
            .execute()
        )
    except SupabaseConfigError as exc:
        return jsonify({"error": str(exc)}), 500
    except Exception:
        logger.exception("Error al consultar hash de póliza")
        return jsonify({"error": "Error al consultar la base de datos"}), 502

    if not result.data:
        return (
            jsonify(
                {
                    "numero_poliza": datos.numero_poliza,
                    "hash_coincide": False,
                    "verificacion": "sin_registro",
                    "datos_correctos": None,
                    "mensaje": "No hay un hash registrado para esta póliza.",
                }
            ),
            404,
        )

    hash_guardado = result.data[0]["hash"]

    if hmac.compare_digest(hash_recibido, hash_guardado):
        return jsonify(
            {
                "numero_poliza": datos.numero_poliza,
                "hash_coincide": True,
                "verificacion": "directo",
                "datos_correctos": datos.model_dump(mode="json"),
                "mensaje": "Los datos de la póliza son correctos.",
            }
        )

    # Fallback: el hash recibido no coincide con el almacenado. Se consulta
    # el log de auditoría original (Poliza / Create) para intentar recuperar
    # y confirmar los datos correctos.
    log = None
    try:
        log = obtener_log_creacion_poliza(datos.numero_poliza)
    except AuditClientError:
        logger.exception("Error al consultar el servicio de auditoría")

    if log is not None:
        detalle = log.get("detalle") or {}
        datos_log = {campo: detalle.get(campo) for campo in CAMPOS_HASH}
        hash_log = calcular_hash_poliza(datos_log)

        if hmac.compare_digest(hash_log, hash_guardado):
            return jsonify(
                {
                    "numero_poliza": datos.numero_poliza,
                    "hash_coincide": False,
                    "verificacion": "log_auditoria",
                    "datos_correctos": datos_log,
                    "mensaje": (
                        "Los datos recibidos no coinciden con el hash almacenado, "
                        "pero se recuperaron y confirmaron los datos correctos "
                        "desde el log de auditoría."
                    ),
                }
            )

    return jsonify(
        {
            "numero_poliza": datos.numero_poliza,
            "hash_coincide": False,
            "verificacion": "sin_confirmar",
            "datos_correctos": None,
            "mensaje": (
                "El hash no coincide y no se pudo confirmar contra el log de "
                "auditoría. Posible alteración de los datos de la póliza."
            ),
        }
    )

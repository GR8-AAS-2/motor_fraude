"""Cliente HTTP hacia el servicio de auditoría `poliza_seguridad`, usado
como fallback para recuperar/confirmar los datos originales de una póliza
cuando el hash almacenado localmente no coincide con lo recibido."""

import os
from typing import Any, Optional

import requests

TIMEOUT_SEGUNDOS = 10


class AuditClientError(Exception):
    """Error al comunicarse con el servicio de auditoría (config o red)."""


def obtener_log_creacion_poliza(numero_poliza: str) -> Optional[dict[str, Any]]:
    """Busca el log de auditoría `tipo_evento=Poliza, evento=Create` para el
    número de póliza dado. Devuelve el log más reciente que coincida, o
    None si no hay ninguno.
    """
    base_url = os.environ.get("AUDIT_SERVICE_URL")
    api_key = os.environ.get("AUDIT_SERVICE_API_KEY")

    if not base_url or not api_key:
        raise AuditClientError(
            "Faltan las variables de entorno AUDIT_SERVICE_URL y/o AUDIT_SERVICE_API_KEY."
        )

    try:
        resp = requests.get(
            f"{base_url.rstrip('/')}/api/logs",
            params={
                "tipo_evento": "Poliza",
                "evento": "Create",
                "identificador": numero_poliza,
                "page_size": 1,
            },
            headers={"X-API-Key": api_key},
            timeout=TIMEOUT_SEGUNDOS,
        )
        resp.raise_for_status()
    except requests.RequestException as exc:
        raise AuditClientError(f"Error consultando el servicio de auditoría: {exc}") from exc

    registros = resp.json().get("data", [])
    return registros[0] if registros else None

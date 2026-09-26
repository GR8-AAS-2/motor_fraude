""" para pruebas unitarias de la API REST del motor de fraude. """
import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.append(str(Path(__file__).resolve().parent.parent))

os.environ.setdefault("FRAUDE_API_KEY", "test-key")
os.environ.setdefault("SUPABASE_URL", "https://example.supabase.co")
os.environ.setdefault("SUPABASE_SERVICE_ROLE_KEY", "test-service-role-key")
os.environ.setdefault("AUDIT_SERVICE_URL", "https://audit.example.com")
os.environ.setdefault("AUDIT_SERVICE_API_KEY", "test-audit-key")

import pytest

from fraud_service import create_app
from fraud_service.hashing import calcular_hash_poliza

API_KEY_HEADERS = {"X-API-Key": "test-key"}

POLIZA_VALIDA = {
    "numero_poliza": "POL-1",
    "tipo_documento": "CC",
    "documento_identidad": "123456789",
    "ramo": "Vida",
    "tipo_cobertura": "Individual",
    "monto_asegurado": 500000,
    "fecha_inicio_vigencia": "2026-01-01",
    "fecha_fin_vigencia": "2026-12-31",
}


@pytest.fixture
def client():
    app = create_app()
    app.testing = True
    return app.test_client()


def _mock_table(mock_get_client):
    mock_table = MagicMock()
    mock_get_client.return_value.table.return_value = mock_table
    return mock_table


def test_health_no_auth_needed(client):
    resp = client.get("/api/health")
    assert resp.status_code == 200
    assert resp.get_json() == {"status": "ok"}


def test_registrar_hash_requires_api_key(client):
    resp = client.post("/api/polizas/hash", json=POLIZA_VALIDA)
    assert resp.status_code == 401


def test_registrar_hash_validates_payload(client):
    resp = client.post(
        "/api/polizas/hash",
        json={"numero_poliza": "POL-1"},  # faltan campos
        headers=API_KEY_HEADERS,
    )
    assert resp.status_code == 400


@patch("fraud_service.routes.get_supabase_client")
def test_registrar_hash_success(mock_get_client, client):
    mock_table = _mock_table(mock_get_client)
    mock_table.select.return_value.eq.return_value.execute.return_value.data = []
    mock_table.insert.return_value.execute.return_value.data = [
        {
            "id": "1",
            "numero_poliza": "POL-1",
            "hash": "abc123",
            "fecha_creacion": "2026-01-01T00:00:00Z",
        }
    ]

    resp = client.post("/api/polizas/hash", json=POLIZA_VALIDA, headers=API_KEY_HEADERS)

    assert resp.status_code == 201
    body = resp.get_json()
    assert body["numero_poliza"] == "POL-1"


@patch("fraud_service.routes.get_supabase_client")
def test_registrar_hash_rechaza_duplicado(mock_get_client, client):
    mock_table = _mock_table(mock_get_client)
    mock_table.select.return_value.eq.return_value.execute.return_value.data = [{"id": "1"}]

    resp = client.post("/api/polizas/hash", json=POLIZA_VALIDA, headers=API_KEY_HEADERS)

    assert resp.status_code == 409
    mock_table.insert.assert_not_called()


def test_validar_poliza_requires_api_key(client):
    resp = client.post("/api/polizas/validar", json=POLIZA_VALIDA)
    assert resp.status_code == 401


@patch("fraud_service.routes.get_supabase_client")
def test_validar_poliza_sin_registro(mock_get_client, client):
    mock_table = _mock_table(mock_get_client)
    mock_table.select.return_value.eq.return_value.execute.return_value.data = []

    resp = client.post("/api/polizas/validar", json=POLIZA_VALIDA, headers=API_KEY_HEADERS)

    assert resp.status_code == 404
    body = resp.get_json()
    assert body["hash_coincide"] is False
    assert body["verificacion"] == "sin_registro"


@patch("fraud_service.routes.get_supabase_client")
def test_validar_poliza_hash_directo_coincide(mock_get_client, client):
    hash_correcto = calcular_hash_poliza(POLIZA_VALIDA)
    mock_table = _mock_table(mock_get_client)
    mock_table.select.return_value.eq.return_value.execute.return_value.data = [
        {"hash": hash_correcto}
    ]

    resp = client.post("/api/polizas/validar", json=POLIZA_VALIDA, headers=API_KEY_HEADERS)

    assert resp.status_code == 200
    body = resp.get_json()
    assert body["hash_coincide"] is True
    assert body["verificacion"] == "directo"
    assert body["datos_correctos"]["numero_poliza"] == "POL-1"


@patch("fraud_service.routes.obtener_log_creacion_poliza")
@patch("fraud_service.routes.get_supabase_client")
def test_validar_poliza_no_coincide_pero_log_confirma(
    mock_get_client, mock_obtener_log, client
):
    # El hash guardado corresponde a los datos "reales" (los del log), no a
    # los recibidos en la petición (que están alterados).
    datos_reales = {**POLIZA_VALIDA, "monto_asegurado": 999999}
    hash_guardado = calcular_hash_poliza(datos_reales)

    mock_table = _mock_table(mock_get_client)
    mock_table.select.return_value.eq.return_value.execute.return_value.data = [
        {"hash": hash_guardado}
    ]
    mock_obtener_log.return_value = {"detalle": datos_reales}

    resp = client.post("/api/polizas/validar", json=POLIZA_VALIDA, headers=API_KEY_HEADERS)

    assert resp.status_code == 200
    body = resp.get_json()
    assert body["hash_coincide"] is False
    assert body["verificacion"] == "log_auditoria"
    assert body["datos_correctos"]["monto_asegurado"] == 999999


@patch("fraud_service.routes.obtener_log_creacion_poliza")
@patch("fraud_service.routes.get_supabase_client")
def test_validar_poliza_no_coincide_y_log_tampoco_confirma(
    mock_get_client, mock_obtener_log, client
):
    mock_table = _mock_table(mock_get_client)
    mock_table.select.return_value.eq.return_value.execute.return_value.data = [
        {"hash": "hash-totalmente-distinto"}
    ]
    mock_obtener_log.return_value = None  # no hay log de auditoría

    resp = client.post("/api/polizas/validar", json=POLIZA_VALIDA, headers=API_KEY_HEADERS)

    assert resp.status_code == 200
    body = resp.get_json()
    assert body["hash_coincide"] is False
    assert body["verificacion"] == "sin_confirmar"
    assert body["datos_correctos"] is None


def test_calcular_hash_es_determinista_con_tipos_distintos():
    # Mismo dato, distinta representación (float vs int, con hora en la
    # fecha) debe producir el mismo hash.
    datos_a = {**POLIZA_VALIDA, "monto_asegurado": 500000, "fecha_inicio_vigencia": "2026-01-01"}
    datos_b = {
        **POLIZA_VALIDA,
        "monto_asegurado": "500000.00",
        "fecha_inicio_vigencia": "2026-01-01T00:00:00",
    }
    assert calcular_hash_poliza(datos_a) == calcular_hash_poliza(datos_b)


def test_calcular_hash_cambia_si_cambia_un_dato():
    datos_a = dict(POLIZA_VALIDA)
    datos_b = {**POLIZA_VALIDA, "monto_asegurado": 1}
    assert calcular_hash_poliza(datos_a) != calcular_hash_poliza(datos_b)

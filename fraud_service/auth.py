"""Autenticación simple usando API key, propia de este servicio."""

import hmac
import os
from functools import wraps

from flask import jsonify, request


def require_api_key(view_func):
    @wraps(view_func)
    def wrapper(*args, **kwargs):
        expected = os.environ.get("FRAUDE_API_KEY")
        if not expected:
            return jsonify({"error": "Servicio mal configurado: falta FRAUDE_API_KEY"}), 500

        provided = request.headers.get("X-API-Key", "")
        if not hmac.compare_digest(provided, expected):
            return jsonify({"error": "No autorizado"}), 401

        return view_func(*args, **kwargs)

    return wrapper

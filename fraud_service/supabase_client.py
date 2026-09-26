"""Cliente Supabase compartido por este servicio (misma cuenta/proyecto 
poliza_seguridad, pero tabla propia)."""

import os
from functools import lru_cache

from supabase import Client, create_client

TABLE_NAME = "poliza_hashes"


class SupabaseConfigError(RuntimeError):
    """Se lanza cuando faltan variables de entorno requeridas."""


@lru_cache(maxsize=1)
def get_supabase_client() -> Client:
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")

    if not url or not key:
        raise SupabaseConfigError(
            "Faltan las variables de entorno SUPABASE_URL y/o SUPABASE_SERVICE_ROLE_KEY."
        )

    return create_client(url, key)

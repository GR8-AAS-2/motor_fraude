"""Punto de entrada WSGI para el runtime Python de Vercel ."""

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv

load_dotenv()

from fraud_service import create_app  # noqa: E402

app = create_app()

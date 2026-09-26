"""Servidor de desarrollo local (no se usa en Vercel).

Uso:
    python run.py
"""

from dotenv import load_dotenv

load_dotenv()

from fraud_service import create_app  # noqa: E402

app = create_app()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001, debug=True, use_reloader=False)

from flask import Flask, jsonify

from .routes import bp


def create_app() -> Flask:
    app = Flask(__name__)
    app.register_blueprint(bp)

    @app.errorhandler(404)
    def not_found(_error):
        return jsonify({"error": "Recurso no encontrado"}), 404

    @app.errorhandler(405)
    def method_not_allowed(_error):
        return jsonify({"error": "Método no permitido"}), 405

    @app.errorhandler(500)
    def internal_error(_error):
        return jsonify({"error": "Error interno del servidor"}), 500

    return app

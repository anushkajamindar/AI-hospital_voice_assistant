"""
Hospital AI Voice Assistant - Flask App Factory
"""

from flask import Flask
from .routes.call_handler import call_bp
from .routes.webhook import webhook_bp
from frontend_api import frontend_bp
from .utils.logger import setup_logging


def create_app():
    setup_logging()
    app = Flask(__name__)

    # Register blueprints
    app.register_blueprint(call_bp)
    app.register_blueprint(webhook_bp)
    app.register_blueprint(frontend_bp)  # Dashboard frontend + /api/appointments

    return app
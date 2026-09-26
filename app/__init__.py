from flask import Flask, jsonify
from flask_cors import CORS
from flask_migrate import Migrate
from dotenv import load_dotenv
from .config import Config
from .models import db
from .routes.api import api
from .routes.public import public
from .routes.webhooks import webhooks
from .security.headers import install_security_headers
from .security.error_handler import install_error_handlers

migrate = Migrate()

def create_app(config_object=None):
    load_dotenv()
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_object(config_object or Config)
    db.init_app(app)
    migrate.init_app(app, db)
    CORS(app, supports_credentials=True)
    app.register_blueprint(api, url_prefix='/api')
    app.register_blueprint(public)
    app.register_blueprint(webhooks, url_prefix='/webhooks')
    install_security_headers(app)
    install_error_handlers(app)
    with app.app_context():
        db.create_all()
    @app.get('/health')
    def health():
        return jsonify({'status': 'ok', 'service': 'thalasseri'})
    return app

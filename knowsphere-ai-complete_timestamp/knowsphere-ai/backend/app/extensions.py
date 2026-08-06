"""
Flask extension instances.

Instantiated here (unbound) and attached to the app in the application
factory (app/__init__.py) via .init_app(app) — the standard pattern to avoid
circular imports between extensions and blueprints.
"""
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_jwt_extended import JWTManager
from flask_cors import CORS

db = SQLAlchemy()
migrate = Migrate()
jwt = JWTManager()
cors = CORS()

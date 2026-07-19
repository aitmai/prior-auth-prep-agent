import os

from dotenv import load_dotenv
from flask import Flask
from flask_login import LoginManager
from flask_wtf import CSRFProtect

load_dotenv()

login_manager = LoginManager()
csrf = CSRFProtect()


def create_app():
    app = Flask(__name__)
    app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-only-change-me")
    # Off by default on purpose — this skips password entry entirely.
    # Never set ALLOW_DEMO_LOGIN=true on a deployment that touches real PHI.
    app.config["ALLOW_DEMO_LOGIN"] = os.environ.get("ALLOW_DEMO_LOGIN", "false").lower() == "true"

    login_manager.init_app(app)
    login_manager.login_view = "auth.login"
    csrf.init_app(app)

    from routes.cases import cases_bp
    from routes.auth import auth_bp
    app.register_blueprint(cases_bp)
    app.register_blueprint(auth_bp)

    @login_manager.user_loader
    def load_user(user_id):
        from db.connection import query
        from models import User
        rows = query("SELECT * FROM users WHERE id = %s", (user_id,))
        return User(rows[0]) if rows else None

    return app


app = create_app()

if __name__ == "__main__":
    app.run(debug=True, port=5000)

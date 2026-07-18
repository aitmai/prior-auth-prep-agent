import os

from dotenv import load_dotenv
from flask import Flask

load_dotenv()


def create_app():
    app = Flask(__name__)
    app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-only-change-me")

    from routes.cases import cases_bp
    app.register_blueprint(cases_bp)

    return app


app = create_app()

if __name__ == "__main__":
    app.run(debug=True, port=5000)

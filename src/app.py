import os
from pathlib import Path

from flask import Flask, redirect, url_for

from routes_calculator import register as register_calculator
from config import DATA_DIR

_SECRET_KEY_FILE = Path(DATA_DIR) / ".secret_key"


def _load_secret_key() -> str:
    """Load or generate a persistent secret key."""
    env_key = os.environ.get("SECRET_KEY")
    if env_key:
        return env_key
    # Try loading from file
    if _SECRET_KEY_FILE.exists():
        return _SECRET_KEY_FILE.read_text().strip()
    # Generate and persist
    key = os.urandom(24).hex()
    Path(DATA_DIR).mkdir(parents=True, exist_ok=True)
    _SECRET_KEY_FILE.write_text(key)
    return key


def create_app() -> Flask:
    app = Flask(__name__)
    app.secret_key = _load_secret_key()

    # Calculator routes only
    register_calculator(app)

    @app.route("/")
    def root():
        return redirect(url_for("employees"))

    return app


app = create_app()

if __name__ == "__main__":
    # 기본 포트 8888 (원본 프로젝트와 동일)
    app.run(host="0.0.0.0", port=8888, debug=True)

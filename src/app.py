import os
from pathlib import Path

from flask import Flask, redirect, url_for, send_from_directory, abort

from routes_calculator import register as register_calculator
from routes_api import register_api
from config import DATA_DIR

_SECRET_KEY_FILE = Path(DATA_DIR) / ".secret_key"
# Frontend dist candidates: Docker (src/static/frontend) or bare metal (../frontend/dist)
_FRONTEND_DIST_CANDIDATES = [
    Path(__file__).parent / "static" / "frontend",
    Path(__file__).parent.parent / "frontend" / "dist",
]


def _get_frontend_dist() -> Path | None:
    """Resolve frontend dist at runtime (handles late builds)."""
    return next((p for p in _FRONTEND_DIST_CANDIDATES if p.exists()), None)


def _load_secret_key() -> str:
    """Load or generate a persistent secret key."""
    env_key = os.environ.get("SECRET_KEY")
    if env_key:
        return env_key
    if _SECRET_KEY_FILE.exists():
        return _SECRET_KEY_FILE.read_text().strip()
    key = os.urandom(24).hex()
    Path(DATA_DIR).mkdir(parents=True, exist_ok=True)
    _SECRET_KEY_FILE.write_text(key)
    return key


def create_app() -> Flask:
    fd = _get_frontend_dist()
    app = Flask(__name__, static_folder=str(fd) if fd else None, static_url_path="/static/frontend")
    app.secret_key = _load_secret_key()

    MODE = os.environ.get("WORKPAY_MODE", "react")

    if MODE == "legacy":
        # Legacy Jinja2 routes (existing)
        register_calculator(app)
    else:
        # New JSON API routes for React SPA
        register_api(app)

    @app.route("/")
    def root():
        if MODE == "legacy":
            return redirect(url_for("employees"))
        # React SPA: serve index.html
        frontend = _get_frontend_dist()
        if frontend:
            return send_from_directory(str(frontend), "index.html")
        abort(404)

    # SPA fallback: serve React index.html for client-side routes
    if MODE == "react":
        @app.route("/<path:path>")
        def spa_fallback(path):
            if path.startswith("api/") or path.startswith("static/"):
                abort(404)
            frontend = _get_frontend_dist()
            if frontend:
                return send_from_directory(str(frontend), "index.html")
            abort(404)

    return app


app = create_app()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8888, debug=True)

from flask import Flask, redirect, url_for

from routes_calculator import register as register_calculator


def create_app() -> Flask:
    import os
    app = Flask(__name__)
    # flash()를 쓰므로 secret_key 필요
    # 환경 변수에서 읽거나, 없으면 랜덤 생성 (프로덕션에서는 반드시 환경 변수 사용)
    app.secret_key = os.environ.get('SECRET_KEY', os.urandom(24).hex())

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

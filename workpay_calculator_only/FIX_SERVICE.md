# 서비스 파일 수정 가이드

## 문제 원인
`status=203/EXEC` 에러는 실행 파일을 찾을 수 없거나 실행할 수 없다는 의미입니다.

현재 서비스 파일의 문제점:
1. `WorkingDirectory=/workpay_calculator_only` - 잘못된 경로
2. `FLASK_APP=/workpay_calculator_only/app.py` - 잘못된 경로
3. `ExecStart`에서 `flask` 명령어 직접 사용 - 경로 문제 가능

## 해결 방법

### 1. 서비스 파일 수정

다음 명령어로 서비스 파일을 수정하세요:

```bash
sudo nano /etc/systemd/system/workpay-calculator.service
```

다음 내용으로 수정:

```ini
[Unit]
Description=WorkPay Calculator Flask Application
After=network.target

[Service]
Type=simple
User=root
Group=root
WorkingDirectory=/workpay_calculator_only/workpay_calculator_only
Environment="PATH=/workpay_calculator_only/venv/bin:/usr/local/bin:/usr/bin:/bin"
Environment="FLASK_APP=/workpay_calculator_only/workpay_calculator_only/app.py"
ExecStart=/workpay_calculator_only/venv/bin/python -m flask run --host=0.0.0.0 --port=8888

# 자동 재시작 설정
Restart=always
RestartSec=10

# 로그 설정
StandardOutput=journal
StandardError=journal
SyslogIdentifier=workpay-calculator

[Install]
WantedBy=multi-user.target
```

**주요 변경사항:**
1. `WorkingDirectory`: `/workpay_calculator_only` → `/workpay_calculator_only/workpay_calculator_only`
2. `FLASK_APP`: `/workpay_calculator_only/app.py` → `/workpay_calculator_only/workpay_calculator_only/app.py`
3. `ExecStart`: `flask` 직접 사용 → `python -m flask` 사용 (더 안정적)

### 2. 경로 확인

실제 경로를 확인하세요:

```bash
# 프로젝트 디렉토리 확인
ls -la /workpay_calculator_only/

# app.py 위치 확인
ls -la /workpay_calculator_only/workpay_calculator_only/app.py

# 가상환경 Python 확인
ls -la /workpay_calculator_only/venv/bin/python

# Flask 설치 확인
/workpay_calculator_only/venv/bin/python -m flask --version
```

### 3. 서비스 재시작

```bash
# systemd 리로드
sudo systemctl daemon-reload

# 서비스 재시작
sudo systemctl restart workpay-calculator.service

# 상태 확인
sudo systemctl status workpay-calculator.service

# 로그 확인 (에러가 있는 경우)
sudo journalctl -u workpay-calculator -n 50 --no-pager
```

### 4. 대안: 직접 Python으로 실행

만약 여전히 문제가 있다면, `ExecStart`를 다음과 같이 변경:

```ini
ExecStart=/workpay_calculator_only/venv/bin/python /workpay_calculator_only/workpay_calculator_only/app.py
```

그리고 `app.py`의 마지막 부분이 다음과 같이 되어 있는지 확인:

```python
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8888, debug=False)
```

### 5. 권한 문제 해결

만약 권한 문제가 있다면:

```bash
# 가상환경 파일 권한 확인
ls -la /workpay_calculator_only/venv/bin/python
ls -la /workpay_calculator_only/venv/bin/flask

# 실행 권한 부여 (필요한 경우)
chmod +x /workpay_calculator_only/venv/bin/python
chmod +x /workpay_calculator_only/venv/bin/flask
```

## 디버깅 팁

### 로그 확인
```bash
# 실시간 로그 확인
sudo journalctl -u workpay-calculator -f

# 최근 100줄 로그
sudo journalctl -u workpay-calculator -n 100 --no-pager
```

### 수동 실행 테스트
```bash
# 가상환경 활성화
source /workpay_calculator_only/venv/bin/activate

# 프로젝트 디렉토리로 이동
cd /workpay_calculator_only/workpay_calculator_only

# Flask 앱 직접 실행 테스트
python app.py
# 또는
flask run --host=0.0.0.0 --port=8888
```

수동 실행이 성공하면 서비스 파일의 경로 문제일 가능성이 높습니다.

# WorkPay Calculator 시스템 서비스 설치 가이드 (Rocky Linux)

이 가이드는 Rocky Linux에서 WorkPay Calculator를 systemd 서비스로 등록하여 부팅 시 자동으로 시작되도록 설정하는 방법을 설명합니다.

## 방법 1: 자동 설치 스크립트 사용 (권장)

1. 스크립트에 실행 권한 부여:
```bash
chmod +x install_service.sh
```

2. 스크립트 실행:
```bash
./install_service.sh
```

스크립트가 다음을 자동으로 수행합니다:
- 가상환경 확인 및 생성 (선택)
- 서비스 파일 생성
- systemd에 서비스 등록
- 서비스 시작 및 자동 시작 설정

## 방법 2: 수동 설치

### 1. 가상환경 생성 (권장)

```bash
cd /path/to/workpay_calculator_only
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r workpay_calculator_only/requirements.txt
deactivate
```

### 2. 서비스 파일 생성

`/etc/systemd/system/workpay-calculator.service` 파일을 생성합니다:

```bash
sudo nano /etc/systemd/system/workpay-calculator.service
```

다음 내용을 입력합니다 (경로를 실제 경로로 수정):

```ini
[Unit]
Description=WorkPay Calculator Flask Application
After=network.target

[Service]
Type=simple
User=your_username
Group=your_group
WorkingDirectory=/path/to/workpay_calculator_only/workpay_calculator_only
Environment="PATH=/path/to/workpay_calculator_only/venv/bin:/usr/local/bin:/usr/bin:/bin"
Environment="FLASK_APP=/path/to/workpay_calculator_only/workpay_calculator_only/app.py"
ExecStart=/path/to/workpay_calculator_only/venv/bin/flask run --host=0.0.0.0 --port=8888

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

**중요: 다음 항목을 실제 값으로 변경하세요:**
- `User`: 실행할 사용자 이름
- `Group`: 실행할 그룹 이름
- `WorkingDirectory`: 프로젝트 디렉토리 경로
- `Environment PATH`: 가상환경의 bin 디렉토리 경로
- `Environment FLASK_APP`: app.py 파일의 전체 경로
- `ExecStart`: flask 실행 파일의 전체 경로

### 3. 가상환경을 사용하지 않는 경우

가상환경을 사용하지 않는다면 다음과 같이 수정:

```ini
ExecStart=/usr/bin/python3 -m flask run --host=0.0.0.0 --port=8888
```

또는 gunicorn을 사용하는 경우:

```ini
ExecStart=/path/to/venv/bin/gunicorn -w 4 -b 0.0.0.0:8888 app:app
```

### 4. 서비스 활성화 및 시작

```bash
# systemd 데몬 리로드
sudo systemctl daemon-reload

# 서비스 활성화 (부팅 시 자동 시작)
sudo systemctl enable workpay-calculator.service

# 서비스 시작
sudo systemctl start workpay-calculator.service

# 서비스 상태 확인
sudo systemctl status workpay-calculator.service
```

## 서비스 관리 명령어

### 서비스 상태 확인
```bash
sudo systemctl status workpay-calculator
```

### 서비스 시작
```bash
sudo systemctl start workpay-calculator
```

### 서비스 중지
```bash
sudo systemctl stop workpay-calculator
```

### 서비스 재시작
```bash
sudo systemctl restart workpay-calculator
```

### 서비스 로그 확인
```bash
# 실시간 로그 확인
sudo journalctl -u workpay-calculator -f

# 최근 100줄 로그 확인
sudo journalctl -u workpay-calculator -n 100

# 오늘 로그만 확인
sudo journalctl -u workpay-calculator --since today
```

### 자동 시작 해제
```bash
sudo systemctl disable workpay-calculator
```

## 방화벽 설정

Rocky Linux에서 포트 8888을 열어야 할 수 있습니다:

```bash
# firewalld 사용 시
sudo firewall-cmd --permanent --add-port=8888/tcp
sudo firewall-cmd --reload

# 또는 iptables 사용 시
sudo iptables -A INPUT -p tcp --dport 8888 -j ACCEPT
```

## 문제 해결

### 서비스가 시작되지 않는 경우

1. 서비스 상태 확인:
```bash
sudo systemctl status workpay-calculator
```

2. 로그 확인:
```bash
sudo journalctl -u workpay-calculator -n 50
```

3. 서비스 파일 문법 확인:
```bash
sudo systemctl cat workpay-calculator
```

4. 경로 확인:
```bash
# Python 경로 확인
which python3
which flask

# 가상환경 경로 확인
ls -la /path/to/workpay_calculator_only/venv/bin/
```

### 권한 문제

서비스 파일의 `User`와 `Group`이 올바른지 확인하세요. 일반적으로 서비스를 실행할 사용자로 설정합니다.

### 포트가 이미 사용 중인 경우

다른 포트를 사용하거나 기존 프로세스를 종료:

```bash
# 포트 8888을 사용하는 프로세스 확인
sudo lsof -i :8888
# 또는
sudo netstat -tlnp | grep 8888

# 프로세스 종료
sudo kill -9 <PID>
```

## Gunicorn 사용 (프로덕션 환경 권장)

프로덕션 환경에서는 Gunicorn을 사용하는 것을 권장합니다:

1. Gunicorn 설치:
```bash
source venv/bin/activate
pip install gunicorn
deactivate
```

2. 서비스 파일 수정:
```ini
ExecStart=/path/to/venv/bin/gunicorn -w 4 -b 0.0.0.0:8888 --access-logfile - --error-logfile - app:app
```

## 보안 고려사항

프로덕션 환경에서는 다음을 고려하세요:

1. **HTTPS 사용**: Nginx를 리버스 프록시로 사용하고 SSL 인증서 설정
2. **방화벽**: 필요한 포트만 열기
3. **사용자 권한**: 최소 권한 사용자로 서비스 실행
4. **로그 관리**: 로그 로테이션 설정

#!/bin/bash
# WorkPay Calculator 서비스 설치 스크립트
# Rocky Linux용 systemd 서비스 설정

set -e

# 색상 정의
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}WorkPay Calculator 서비스 설치${NC}"
echo ""

# 현재 사용자 확인
CURRENT_USER=$(whoami)
CURRENT_GROUP=$(id -gn)
echo -e "현재 사용자: ${YELLOW}${CURRENT_USER}${NC}"
echo -e "현재 그룹: ${YELLOW}${CURRENT_GROUP}${NC}"
echo ""

# 프로젝트 경로 확인
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_DIR="/workpay_calculator_only"
echo -e "프로젝트 디렉토리: ${YELLOW}${PROJECT_DIR}${NC}"

if [ ! -d "${PROJECT_DIR}" ]; then
    echo -e "${RED}오류: ${PROJECT_DIR} 디렉토리를 찾을 수 없습니다.${NC}"
    exit 1
fi

# 가상환경 확인
VENV_DIR="${SCRIPT_DIR}/venv"
if [ ! -d "${VENV_DIR}" ]; then
    echo -e "${YELLOW}가상환경이 없습니다. 생성하시겠습니까? (y/n)${NC}"
    read -r response
    if [[ "$response" =~ ^([yY][eE][sS]|[yY])$ ]]; then
        echo "가상환경 생성 중..."
        python3 -m venv "${VENV_DIR}"
        echo "가상환경 활성화 및 패키지 설치 중..."
        source "${VENV_DIR}/bin/activate"
        pip install --upgrade pip
        pip install -r "${PROJECT_DIR}/requirements.txt"
        deactivate
        echo -e "${GREEN}가상환경 생성 완료${NC}"
    else
        VENV_DIR=""
        echo -e "${YELLOW}가상환경 없이 진행합니다.${NC}"
    fi
fi

# Python 경로 확인
if [ -n "${VENV_DIR}" ] && [ -d "${VENV_DIR}" ]; then
    PYTHON_PATH="${VENV_DIR}/bin/python"
    FLASK_PATH="${VENV_DIR}/bin/flask"
else
    PYTHON_PATH=$(which python3)
    FLASK_PATH=$(which flask)
    if [ -z "${FLASK_PATH}" ]; then
        FLASK_PATH="${PYTHON_PATH} -m flask"
    fi
fi

echo -e "Python 경로: ${YELLOW}${PYTHON_PATH}${NC}"
echo -e "Flask 경로: ${YELLOW}${FLASK_PATH}${NC}"
echo ""

# 서비스 파일 생성
SERVICE_FILE="/tmp/workpay-calculator.service"
cat > "${SERVICE_FILE}" << EOF
[Unit]
Description=WorkPay Calculator Flask Application
After=network.target

[Service]
Type=simple
User=${CURRENT_USER}
Group=${CURRENT_GROUP}
WorkingDirectory=${PROJECT_DIR}
Environment="PATH=${VENV_DIR}/bin:/usr/local/bin:/usr/bin:/bin"
Environment="FLASK_APP=${PROJECT_DIR}/app.py"
ExecStart=${PYTHON_PATH} -m flask run --host=0.0.0.0 --port=8888

# 자동 재시작 설정
Restart=always
RestartSec=10

# 로그 설정
StandardOutput=journal
StandardError=journal
SyslogIdentifier=workpay-calculator

[Install]
WantedBy=multi-user.target
EOF

echo -e "${GREEN}서비스 파일 생성 완료${NC}"
echo ""
echo "서비스 파일 내용:"
echo "----------------------------------------"
cat "${SERVICE_FILE}"
echo "----------------------------------------"
echo ""

# 서비스 파일 설치 확인
echo -e "${YELLOW}서비스 파일을 /etc/systemd/system/에 복사하시겠습니까? (sudo 권한 필요) (y/n)${NC}"
read -r response
if [[ "$response" =~ ^([yY][eE][sS]|[yY])$ ]]; then
    sudo cp "${SERVICE_FILE}" /etc/systemd/system/workpay-calculator.service
    sudo chmod 644 /etc/systemd/system/workpay-calculator.service
    echo -e "${GREEN}서비스 파일 설치 완료${NC}"
    
    # systemd 리로드
    echo "systemd 데몬 리로드 중..."
    sudo systemctl daemon-reload
    echo -e "${GREEN}systemd 리로드 완료${NC}"
    
    # 서비스 활성화 확인
    echo ""
    echo -e "${YELLOW}서비스를 지금 시작하고 부팅 시 자동 시작하도록 설정하시겠습니까? (y/n)${NC}"
    read -r response2
    if [[ "$response2" =~ ^([yY][eE][sS]|[yY])$ ]]; then
        sudo systemctl enable workpay-calculator.service
        sudo systemctl start workpay-calculator.service
        echo -e "${GREEN}서비스 시작 및 자동 시작 설정 완료${NC}"
        echo ""
        echo "서비스 상태 확인:"
        sudo systemctl status workpay-calculator.service
    else
        echo ""
        echo "수동으로 서비스를 시작하려면:"
        echo -e "  ${YELLOW}sudo systemctl enable workpay-calculator.service${NC}"
        echo -e "  ${YELLOW}sudo systemctl start workpay-calculator.service${NC}"
    fi
else
    echo ""
    echo "서비스 파일 위치: ${SERVICE_FILE}"
    echo "수동으로 설치하려면:"
    echo -e "  ${YELLOW}sudo cp ${SERVICE_FILE} /etc/systemd/system/workpay-calculator.service${NC}"
    echo -e "  ${YELLOW}sudo systemctl daemon-reload${NC}"
    echo -e "  ${YELLOW}sudo systemctl enable workpay-calculator.service${NC}"
    echo -e "  ${YELLOW}sudo systemctl start workpay-calculator.service${NC}"
fi

echo ""
echo -e "${GREEN}설치 완료!${NC}"
echo ""
echo "유용한 명령어:"
echo "  서비스 상태 확인: sudo systemctl status workpay-calculator"
echo "  서비스 시작:      sudo systemctl start workpay-calculator"
echo "  서비스 중지:      sudo systemctl stop workpay-calculator"
echo "  서비스 재시작:    sudo systemctl restart workpay-calculator"
echo "  로그 확인:        sudo journalctl -u workpay-calculator -f"
echo "  자동 시작 해제:    sudo systemctl disable workpay-calculator"

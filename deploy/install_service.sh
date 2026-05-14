#!/bin/bash
# WorkPay 서비스 설치 스크립트 (Rocky Linux / 베어메탈)
# Docker 사용 시 이 스크립트 불필요. docker compose up 으로 대체.

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  WorkPay 서비스 설치${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""

# ---------- 경로 ----------
SERVICE_DIR="/srv/workpay"
DATA_DIR="/var/lib/workpay"
CONF_FILE="/etc/workpay.conf"
VENV_DIR="${SERVICE_DIR}/.venv"

# ---------- 사전 조건 ----------
echo -e "📦 사전 조건 확인 중..."

# Python 3.9+
if ! command -v python3 &>/dev/null; then
    echo -e "${RED}❌ python3가 설치되어 있지 않습니다.${NC}"
    echo "   sudo dnf install python3"
    exit 1
fi
PY_VER=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
echo -e "   Python: ${YELLOW}${PY_VER}${NC}"

# Node.js 20+
if ! command -v node &>/dev/null; then
    echo -e "${YELLOW}⚠️  node가 없습니다. 프론트엔드 빌드를 위해 설치합니다.${NC}"
    sudo dnf install -y nodejs || {
        echo -e "${RED}❌ nodejs 설치가 실패했습니다. 수동으로 설치해주세요.${NC}"
        exit 1
    }
fi
NODE_VER=$(node -v)
echo -e "   Node.js: ${YELLOW}${NODE_VER}${NC}"

# npm
if ! command -v npm &>/dev/null; then
    echo -e "${RED}❌ npm이 없습니다.${NC}"
    exit 1
fi
echo -e "   npm: ${YELLOW}$(npm -v)${NC}"
echo ""

# ---------- 설정 파일 ----------
echo -e "📝 설정 파일 확인 중..."
if [ ! -f "${CONF_FILE}" ]; then
    echo -e "${YELLOW}⚠️  ${CONF_FILE}이 없습니다. 기본값으로 생성합니다.${NC}"
    sudo tee "${CONF_FILE}" > /dev/null << CONF
# WorkPay Configuration
# Generate SECRET_KEY: openssl rand -hex 32
SECRET_KEY=$(openssl rand -hex 32)
ADMIN_PASSWORD=password
CONF
    sudo chmod 600 "${CONF_FILE}"
    echo -e "   ${GREEN}생성 완료 (${CONF_FILE})${NC}"
else
    echo -e "   ${GREEN}이미 존재${NC}"
fi
echo ""

# ---------- 프론트엔드 빌드 ----------
echo -e "🔨 프론트엔드 빌드 중..."
FRONTEND_DIR="${SERVICE_DIR}/frontend"
if [ ! -d "${FRONTEND_DIR}" ]; then
    echo -e "${RED}❌ ${FRONTEND_DIR} 디렉토리가 없습니다.${NC}"
    echo "   먼저 git clone 하세요:"
    echo "   sudo git clone <repo_url> ${SERVICE_DIR}"
    exit 1
fi

cd "${FRONTEND_DIR}"
echo "   npm ci ..."
npm ci
echo "   npm run build ..."
npm run build
echo -e "   ${GREEN}빌드 완료${NC}"
echo ""

# ---------- Python 가상환경 ----------
echo -e "🐍 Python 가상환경 설정 중..."
if [ ! -d "${VENV_DIR}" ]; then
    echo "   venv 생성 중..."
    python3 -m venv "${VENV_DIR}"
fi

echo "   패키지 설치 중..."
"${VENV_DIR}/bin/pip" install --upgrade pip
"${VENV_DIR}/bin/pip" install -r "${SERVICE_DIR}/src/requirements.txt"
echo -e "   ${GREEN}완료${NC}"
echo ""

# ---------- 데이터 디렉토리 ----------
echo -e "💾 데이터 디렉토리 확인 중..."
sudo mkdir -p "${DATA_DIR}"
sudo chown "$(whoami):$(id -gn)" "${DATA_DIR}" 2>/dev/null || true
echo -e "   ${GREEN}${DATA_DIR}${NC}"
echo ""

# ---------- systemd 서비스 ----------
echo -e "⚙️  systemd 서비스 설정 중..."
CURRENT_USER=$(whoami)
CURRENT_GROUP=$(id -gn)

sudo tee /etc/systemd/system/workpay-calculator.service > /dev/null << SVC
[Unit]
Description=WorkPay Calculator Flask Application
After=network.target

[Service]
Type=simple
User=${CURRENT_USER}
Group=${CURRENT_GROUP}
WorkingDirectory=${SERVICE_DIR}/src
EnvironmentFile=${CONF_FILE}
Environment="PATH=${VENV_DIR}/bin:/usr/local/bin:/usr/bin:/bin"
Environment="WORKPAY_DATA_DIR=${DATA_DIR}"
Environment="FLASK_APP=app.py"
ExecStart=${VENV_DIR}/bin/python -m flask run --host=0.0.0.0 --port=8888

Restart=always
RestartSec=10

StandardOutput=journal
StandardError=journal
SyslogIdentifier=workpay-calculator

NoNewPrivileges=true
PrivateTmp=true

[Install]
WantedBy=multi-user.target
SVC

sudo systemctl daemon-reload
echo -e "   ${GREEN}서비스 파일 설치 완료${NC}"
echo ""

# ---------- 서비스 시작 ----------
echo -e "${YELLOW}서비스를 시작하고 부팅 시 자동 시작하시겠습니까? (y/n)${NC}"
read -r START_NOW
if [[ "$START_NOW" =~ ^([yY][eE][sS]|[yY])$ ]]; then
    sudo systemctl enable workpay-calculator.service
    sudo systemctl start workpay-calculator.service
    echo ""
    echo -e "${GREEN}✅ 서비스 시작 완료${NC}"
    echo ""
    echo "   상태 확인: sudo systemctl status workpay-calculator"
    echo "   로그 확인: sudo journalctl -u workpay-calculator -f"
    echo "   브라우저:  http://$(hostname -I | awk '{print $1}'):8888"
fi

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  설치 완료!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo "📌 유용한 명령어:"
echo "  상태 확인:  sudo systemctl status workpay-calculator"
echo "  시작:       sudo systemctl start workpay-calculator"
echo "  중지:       sudo systemctl stop workpay-calculator"
echo "  재시작:     sudo systemctl restart workpay-calculator"
echo "  로그:       sudo journalctl -u workpay-calculator -f"
echo ""
echo "🔄 업데이트 방법:"
echo "  cd ${SERVICE_DIR}"
echo "  git pull"
echo "  cd frontend && npm ci && npm run build"
echo "  ${VENV_DIR}/bin/pip install -r ../src/requirements.txt"
echo "  sudo systemctl restart workpay-calculator"

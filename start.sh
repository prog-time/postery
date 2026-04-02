#!/bin/bash
set -e

cd "$(dirname "$0")"

HOST="0.0.0.0"
PORT="8000"
GREEN="\033[0;32m"
CYAN="\033[0;36m"
YELLOW="\033[1;33m"
RESET="\033[0m"

echo ""
echo -e "${CYAN}╔══════════════════════════════════════════╗${RESET}"
echo -e "${CYAN}║              Postery  —  Admin           ║${RESET}"
echo -e "${CYAN}╚══════════════════════════════════════════╝${RESET}"
echo ""

# ── Virtual environment ──────────────────────────────────────────────────────
if [ ! -f ".venv/bin/activate" ]; then
    echo -e "${YELLOW}[1/3] Creating virtual environment...${RESET}"
    rm -rf .venv
    if ! python3 -m venv .venv 2>/dev/null; then
        echo -e "${YELLOW}      python3-venv не найден. Устанавливаю...${RESET}"
        sudo apt install -y python3-venv python3-pip
        python3 -m venv .venv
    fi
else
    echo -e "${GREEN}[1/3] Virtual environment found.${RESET}"
fi

source .venv/bin/activate

# ── Dependencies ─────────────────────────────────────────────────────────────
echo -e "${YELLOW}[2/3] Installing dependencies...${RESET}"
pip install -q -r requirements.txt
echo -e "${GREEN}      Done.${RESET}"

# ── Env file ─────────────────────────────────────────────────────────────────
if [ ! -f ".env" ] && [ -f ".env.example" ]; then
    cp .env.example .env
    echo -e "${YELLOW}      .env created from .env.example — проверьте настройки.${RESET}"
fi

# ── Data directory ───────────────────────────────────────────────────────────
mkdir -p data

# ── Default admin ─────────────────────────────────────────────────────────────
python3 - <<'EOF'
from app.database import engine, Base, SessionLocal
from app.models.admin_user import AdminUser, Role
from app.auth import hash_password
Base.metadata.create_all(bind=engine)
with SessionLocal() as db:
    if not db.query(AdminUser).first():
        db.add(AdminUser(username="admin", password_hash=hash_password("admin"), role=Role.SUPERADMIN, is_active=True))
        db.commit()
        print("\033[1;33m      Создан пользователь по умолчанию: admin / admin\033[0m")
        print("\033[1;33m      Смените пароль: python create_superadmin.py\033[0m")
EOF

# ── Info ─────────────────────────────────────────────────────────────────────
echo ""
echo -e "${CYAN}[3/3] Starting server on http://${HOST}:${PORT}${RESET}"
echo ""
echo -e "  ${GREEN}Приложение:${RESET}  http://localhost:${PORT}"
echo -e "  ${GREEN}Админка:${RESET}     http://localhost:${PORT}/admin"
echo -e "  ${GREEN}API docs:${RESET}    http://localhost:${PORT}/docs"
echo ""
echo -e "  ${YELLOW}Как открыть админку:${RESET}"
echo -e "  1. Откройте браузер"
echo -e "  2. Перейдите по адресу → http://localhost:${PORT}/admin"
echo -e "  3. Войдите с учётными данными администратора"
echo ""
echo -e "  Для остановки нажмите ${YELLOW}Ctrl+C${RESET}"
echo ""
echo -e "${CYAN}──────────────────────────────────────────────${RESET}"
echo ""

# ── Run ───────────────────────────────────────────────────────────────────────
uvicorn main:app --host "$HOST" --port "$PORT" --reload

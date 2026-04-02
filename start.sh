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
echo -e "${CYAN}║     posting.iliya-code.ru  —  Admin      ║${RESET}"
echo -e "${CYAN}╚══════════════════════════════════════════╝${RESET}"
echo ""

# ── Virtual environment ──────────────────────────────────────────────────────
if [ ! -d ".venv" ]; then
    echo -e "${YELLOW}[1/3] Creating virtual environment...${RESET}"
    python3 -m venv .venv
else
    echo -e "${GREEN}[1/3] Virtual environment found.${RESET}"
fi

source .venv/bin/activate

# ── Dependencies ─────────────────────────────────────────────────────────────
echo -e "${YELLOW}[2/3] Installing dependencies...${RESET}"
pip install -q -r requirements.txt
echo -e "${GREEN}      Done.${RESET}"

# ── Data directory ───────────────────────────────────────────────────────────
mkdir -p data

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

#!/usr/bin/env bash
# TaleWeaver Run Script (Bash)
# Pulls the latest Git changes, syncs dependencies when lock files changed, checks the setup
# and ports configured in .env, then starts backend (Poetry) and frontend (Vite).

set -e

# Change directory to the repository root directory
cd "$(dirname "$0")"

NO_PULL=false
for arg in "$@"; do
    if [ "$arg" == "--no-pull" ]; then
        NO_PULL=true
    fi
done

# System Poetry first, then the venv fallback created by setup.sh
find_poetry() {
    if command -v poetry &> /dev/null; then
        command -v poetry
    elif [ -x venv/Scripts/poetry ] || [ -x venv/Scripts/poetry.exe ]; then
        echo "./venv/Scripts/poetry"
    elif [ -x venv/bin/poetry ]; then
        echo "./venv/bin/poetry"
    fi
}

# 'poetry env info' reports the system Python when no env exists, so probe the deps instead
poetry_env_ready() {
    [ -n "$POETRY" ] && "$POETRY" run python -c "import fastapi, uvicorn, alembic" &> /dev/null
}

frontend_installed() {
    [ -f frontend/node_modules/.bin/vite ]
}

# Reads KEY from .env (last occurrence, quotes and trailing comments stripped)
env_value() {
    local value=""
    if [ -f .env ]; then
        value=$(grep -E "^\s*$1\s*=" .env | tail -n 1 | cut -d '=' -f 2- | cut -d '#' -f 1 | tr -d "\"' \r\t")
    fi
    echo "${value:-$2}"
}

port_in_use() {
    (echo > "/dev/tcp/127.0.0.1/$1") &> /dev/null || (echo > "/dev/tcp/::1/$1") &> /dev/null
}

echo "=============================="
echo "      TaleWeaver Runner       "
echo "=============================="

# 1. Fetch current state from Git and remember what changed
CHANGED_FILES=""
if [ "$NO_PULL" = true ]; then
    echo "[*] Skipping Git pull."
elif [ -d ".git" ]; then
    echo "[*] Fetching latest changes from Git..."
    BEFORE=$(git rev-parse HEAD)
    if git pull; then
        CHANGED_FILES=$(git diff --name-only "$BEFORE" HEAD)
    else
        echo "[!] Warning: Git pull failed. Continuing anyway..."
    fi
else
    echo "[!] Not a Git repository, skipping Git pull."
fi

# 2. Check setup status
POETRY=$(find_poetry)
MISSING=()
[ -f .env ] || MISSING+=(".env")
if [ -z "$POETRY" ]; then
    MISSING+=("Poetry")
elif ! poetry_env_ready; then
    MISSING+=("Poetry environment")
fi
frontend_installed || MISSING+=("frontend/node_modules")

if [ ${#MISSING[@]} -gt 0 ]; then
    echo "[!] Project setup is missing or incomplete (missing: ${MISSING[*]})."
    read -rp "Would you like to run the setup script now? (y/n): " RUN_SETUP
    if [[ ! "$RUN_SETUP" =~ ^[Yy]$ ]]; then
        echo "[*] Exiting. Run ./setup.sh to set up the project."
        exit 0
    fi
    echo "[*] Running setup.sh..."
    bash ./setup.sh --skip-start
    POETRY=$(find_poetry)
    if [ ! -f .env ] || ! poetry_env_ready || ! frontend_installed; then
        echo "[!] Setup failed or is still incomplete. Exiting."
        exit 1
    fi
    CHANGED_FILES=""
fi

# 3. Sync dependencies when the pull brought relevant changes
if echo "$CHANGED_FILES" | grep -qxE "poetry\.lock|pyproject\.toml"; then
    echo "[*] Python dependencies changed, running 'poetry install'..."
    "$POETRY" install
fi
if echo "$CHANGED_FILES" | grep -qxE "frontend/package(-lock)?\.json"; then
    echo "[*] Frontend dependencies changed, running 'npm install'..."
    (cd frontend && npm install --include=dev)
fi

# 4. Check the ports configured in .env (backend and Vite both read them from there)
BACKEND_PORT=$(env_value BACKEND_PORT 8000)
FRONTEND_PORT=$(env_value FRONTEND_PORT 5173)
if [ "$BACKEND_PORT" == "$FRONTEND_PORT" ]; then
    echo "[!] BACKEND_PORT and FRONTEND_PORT in .env must differ (both are $BACKEND_PORT)."
    exit 1
fi
BUSY=()
for port in "$BACKEND_PORT" "$FRONTEND_PORT"; do
    if port_in_use "$port"; then
        BUSY+=("$port")
    fi
done
if [ ${#BUSY[@]} -gt 0 ]; then
    echo "[!] Port(s) already in use: ${BUSY[*]}."
    echo "    Another TaleWeaver instance (e.g. a second checkout) or another program is running."
    echo "    Stop it, or set different BACKEND_PORT / FRONTEND_PORT values in .env."
    exit 1
fi

# 5. Start the application locally
echo "[*] Starting backend (port $BACKEND_PORT) and frontend (port $FRONTEND_PORT)..."
"$POETRY" run taleweaver &
BACKEND_PID=$!

(cd frontend && npm run dev) &
FRONTEND_PID=$!

# Trap Ctrl+C to stop both background processes
trap 'echo -e "\nStopping backend and frontend..."; kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; exit 0' INT TERM

echo "[+] Processes started. PIDs: Backend=$BACKEND_PID, Frontend=$FRONTEND_PID"
echo "[+] Open http://localhost:$FRONTEND_PORT"
echo "Press Ctrl+C to stop both processes."

wait

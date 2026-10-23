#!/usr/bin/env bash
# TaleWeaver Setup Script (Bash)
# This script sets up the Python environment, database, and frontend dependencies.

set -e

# Parse arguments
SKIP_START=false
for arg in "$@"; do
    if [ "$arg" == "--skip-start" ]; then
        SKIP_START=true
    fi
done

echo "--- TaleWeaver Setup ---"

# 1. Environment Variables (.env)
ENV_CREATED=false
if [ ! -f .env ]; then
    echo "[*] Creating .env from .env.example..."
    cp .env.example .env
    ENV_CREATED=true
fi

if ! grep -q "PROJECT_NAME=" .env; then
    sed -i '1i PROJECT_NAME="TaleWeaver"' .env
else
    if [[ "$OSTYPE" == "darwin"* ]]; then
        sed -i '' 's/PROJECT_NAME=.*/PROJECT_NAME="TaleWeaver"/' .env
    else
        sed -i 's/PROJECT_NAME=.*/PROJECT_NAME="TaleWeaver"/' .env
    fi
fi

# 2. Dependency Management (Poetry)
echo "[*] Setting up Python dependencies with Poetry..."
if command -v poetry &> /dev/null; then
    echo "[+] Using system Poetry..."
    poetry install
    RUN_CMD="poetry run"
    PYTHON_CMD="poetry run python"
else
    echo "[*] Poetry not found in PATH. Checking virtual environment (venv)..."
    if [ ! -d "venv" ]; then
        echo "[*] Creating virtual environment (venv)..."
        python3 -m venv venv
    fi
    if [[ "$OSTYPE" == "msys" || "$OSTYPE" == "cygwin" ]]; then
        ./venv/Scripts/pip install --upgrade pip "poetry>=2.0.0"
        ./venv/Scripts/poetry install
        RUN_CMD="./venv/Scripts/poetry run"
        PYTHON_CMD="./venv/Scripts/poetry run python"
    else
        ./venv/bin/pip install --upgrade pip "poetry>=2.0.0"
        ./venv/bin/poetry install
        RUN_CMD="./venv/bin/poetry run"
        PYTHON_CMD="./venv/bin/poetry run python"
    fi
fi


# 3. Data Directory
mkdir -p data

# Helper: set or append a key=value pair in .env
# Usage: set_env_key KEY VALUE
set_env_key() {
    local key="$1"
    local value="$2"
    if grep -q "^${key}=" .env; then
        # Key line exists – replace it (macOS needs empty string after -i)
        if [[ "$OSTYPE" == "darwin"* ]]; then
            sed -i '' "s|^${key}=.*|${key}=${value}|" .env
        else
            sed -i "s|^${key}=.*|${key}=${value}|" .env
        fi
    else
        # Key line missing entirely – append it
        echo "${key}=${value}" >> .env
    fi
}

# 4. Ports (asked once for a new .env; run.sh checks them before every start)
if [ "$ENV_CREATED" = true ]; then
    echo "[*] Configure ports (press Enter for the default). Use different ports per checkout."
    read -rp "Backend port [8000]: " BACKEND_PORT_INPUT || true
    read -rp "Frontend port [5173]: " FRONTEND_PORT_INPUT || true
    if [[ "$BACKEND_PORT_INPUT" =~ ^[0-9]+$ ]]; then set_env_key "BACKEND_PORT" "$BACKEND_PORT_INPUT"; fi
    if [[ "$FRONTEND_PORT_INPUT" =~ ^[0-9]+$ ]]; then set_env_key "FRONTEND_PORT" "$FRONTEND_PORT_INPUT"; fi
fi

# 5. Security Keys
# ENCRYPTION_KEY
if ! grep -qE "^ENCRYPTION_KEY=[a-zA-Z0-9+/=_-]{20,}" .env; then
    echo "[*] Generating ENCRYPTION_KEY..."
    KEY=$($PYTHON_CMD -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())")
    set_env_key "ENCRYPTION_KEY" "$KEY"
    echo "[+] ENCRYPTION_KEY written to .env"
fi

# SECRET_KEY
if ! grep -qE "^SECRET_KEY=[a-fA-F0-9]{64}" .env; then
    echo "[*] Generating SECRET_KEY..."
    SKEY=$($PYTHON_CMD -c "import secrets; print(secrets.token_hex(32))")
    set_env_key "SECRET_KEY" "$SKEY"
    echo "[+] SECRET_KEY written to .env"
fi

# 6. Database Setup (Migrations)
echo "[*] Running database migrations..."
$PYTHON_CMD -m alembic upgrade head

# 7. Frontend Setup
echo "[*] Installing frontend dependencies..."
if ! command -v npm &> /dev/null; then
    echo "[!] Error: 'npm' is not installed or not in PATH. Please install Node.js and npm first."
    exit 1
fi
if command -v node &> /dev/null; then
    echo "[+] Found Node.js version: $(node --version)"
fi
cd frontend
npm install --include=dev
cd ..
if [ ! -f "frontend/node_modules/.bin/vite" ]; then
    echo "[!] Error: Vite executable not found in frontend/node_modules/.bin/vite after npm install."
    exit 1
fi

# 8. Git Hooks Setup
if [ -d ".git" ]; then
    echo "[*] Configuring Git pre-commit hooks..."
    git config core.hooksPath .githooks
    echo "[+] Git hooks linked to .githooks"
fi

echo -e "\n--- Setup Complete! ---"
echo "Start the application with: ./run.sh"
echo "(Backend only: $RUN_CMD taleweaver | Frontend only: cd frontend && npm run dev)"

# 9. Start (Optional) - run.sh owns the start logic incl. port checks
if [ "$SKIP_START" = false ]; then
    echo
    read -p "Would you like to start the application now? (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        exec bash ./run.sh --no-pull
    fi
fi

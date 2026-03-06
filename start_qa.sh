#!/bin/bash
# ─────────────────────────────────────────────────────────────
#  start_qa.sh — start de QA-instantie van Regian OS
#
#  • Poort : 8502
#  • Config: .env (basis) + .env.qa (overrides — zie .env.qa)
#  • Visueel: oranje QA-banner in het dashboard
#
#  Gebruik: ./start_qa.sh [--skip-tests]
# ─────────────────────────────────────────────────────────────
set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Activeer virtualenv
source .venv/bin/activate

# ── Omgevingsvariabelen ───────────────────────────────────────
export REGIAN_ENV=qa
export REGIAN_ENV_FILE=.env.qa

# Streamlit-poort overschrijven (los van config.toml)
export STREAMLIT_SERVER_PORT=8502
export STREAMLIT_BROWSER_SERVER_PORT=8502

# ── Maak QA-werkmap aan als die nog niet bestaat ─────────────
QA_ROOT=$(python3 -c "
import os; from dotenv import dotenv_values
base = dotenv_values('.env')
qa   = dotenv_values('.env.qa')
print(qa.get('REGIAN_ROOT_DIR', base.get('REGIAN_ROOT_DIR', '')))
")
if [ -n "$QA_ROOT" ] && [ ! -d "$QA_ROOT" ]; then
    echo "📁 QA-werkmap aanmaken: $QA_ROOT"
    mkdir -p "$QA_ROOT"
fi

echo ""
echo "🧪 Regian OS QA-omgeving wordt gestart op poort 8502..."
echo "   Basis-config : .env"
echo "   QA-overrides : .env.qa"
echo "   Werkmap      : $QA_ROOT"
echo ""

python3 -m streamlit run regian/interface/dashboard.py \
    --server.port=8502 \
    --browser.serverPort=8502

#!/bin/bash
# ─────────────────────────────────────────────────────────────
#  start_prod.sh — start de productie-instantie van Regian OS
#
#  • Poort : 8501 (zelfde als config.toml)
#  • Config: .env (geen overschrijvingen)
#  • Visueel: standaard dashboard zonder QA-banner
#
#  Gebruik: ./start_prod.sh
# ─────────────────────────────────────────────────────────────
set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Activeer virtualenv
source .venv/bin/activate

# ── Omgevingsvariabelen ───────────────────────────────────────
export REGIAN_ENV=prod
# REGIAN_ENV_FILE niet ingesteld → settings.py laadt alleen .env

echo ""
echo "🚀 Regian OS Productie-omgeving wordt gestart op poort 8501..."
echo "   Config: .env"
echo ""

python3 -m streamlit run regian/interface/dashboard.py

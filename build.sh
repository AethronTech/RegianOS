#!/bin/bash
set -e

echo "=== RegianOS Build Script ==="

# 1. Controleer Python
if ! command -v python3 &> /dev/null; then
    echo "❌ Python3 niet gevonden. Installeer Python 3.10+ eerst."
    exit 1
fi
echo "✅ Python: $(python3 --version)"

# 2. Maak virtualenv aan als die nog niet bestaat
if [ ! -d ".venv" ]; then
    echo "📦 Virtuele omgeving aanmaken..."
    python3 -m venv .venv
fi

# 3. Activeer virtualenv
source .venv/bin/activate
echo "✅ Virtuele omgeving actief"

# 4. Installeer dependencies
echo "📥 Dependencies installeren..."
pip install --upgrade pip -q
pip install -r requirements.txt -q
echo "✅ Dependencies geïnstalleerd"

# 5. Controleer .env
if [ ! -f ".env" ]; then
    echo "⚠️  Geen .env gevonden. Kopieer .env.example of maak er een aan."
else
    echo "✅ .env aanwezig"
fi

# 6. Controleer Ollama (optioneel)
if command -v ollama &> /dev/null; then
    echo "✅ Ollama gevonden: $(ollama --version 2>/dev/null || echo 'versie onbekend')"
else
    echo "⚠️  Ollama niet gevonden. Installeer via https://ollama.com als je lokale modellen wil gebruiken."
fi

echo ""
echo "=== Build succesvol ==="
echo ""
python3 main.py "$@"

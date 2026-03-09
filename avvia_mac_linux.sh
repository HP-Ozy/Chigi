#!/bin/bash

if ! command -v python3 &> /dev/null; then
    echo "[ERRORE] Python3 non trovato. Installa Python da https://python.org"
    exit 1
fi


echo "Installazione dipendenze..."
pip3 install -r requirements.txt -q 2>/dev/null || pip install -r requirements.txt -q

echo ""
echo "Avvio dashboard su http://localhost:5050"
echo "Premi CTRL+C per fermare."
echo ""

python3 app.py

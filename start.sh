#!/bin/bash
set -e

echo "Creazione ambiente virtuale con Python 3.11..."
python3.11 -m venv venv

echo "Attivazione ambiente..."
source venv/bin/activate

echo "Installazione requisiti..."
pip install -r requirements.txt

echo "Creazione script di attesa..."
cat << 'EOF' > open_browser.py
import socket, time, webbrowser
for _ in range(60):
    if socket.socket().connect_ex(('127.0.0.1', 8000)) == 0:
        webbrowser.open('http://127.0.0.1:8000')
        break
    time.sleep(0.5)
EOF

echo "Avvio del browser in background (in attesa del server)..."
python open_browser.py &

echo "Avvio del server (premi Ctrl+C per fermarlo)..."
uvicorn main:app --reload --host 127.0.0.1 --port 8000

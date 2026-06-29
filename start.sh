#!/bin/bash
set -e

echo "Aggiunta repository deadsnakes PPA..."
sudo apt-get install -y software-properties-common
sudo add-apt-repository -y ppa:deadsnakes/ppa
sudo apt-get update -y

echo "Installazione Python 3.11..."
sudo apt-get install -y python3.11 python3.11-venv python3.11-dev

echo "Verifica:"
python3.11 --version

echo "Creazione venv con Python 3.11..."
/usr/bin/python3.11 -m venv venv

source venv/bin/activate
python --version  # Deve mostrare 3.11.x

pip install --upgrade pip
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
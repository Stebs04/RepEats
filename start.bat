@echo off
echo Creazione ambiente virtuale con Python 3.11...
py -3.11 -m venv venv

echo Attivazione ambiente...
call venv\Scripts\activate

echo Installazione requisiti...
pip install -r requirements.txt

echo Creazione script di attesa...
echo import socket, time, webbrowser > open_browser.py
echo for _ in range(60): >> open_browser.py
echo     if socket.socket().connect_ex(('127.0.0.1', 8000)) == 0: >> open_browser.py
echo         webbrowser.open('http://127.0.0.1:8000') >> open_browser.py
echo         break >> open_browser.py
echo     time.sleep(0.5) >> open_browser.py

echo Avvio del browser in background (in attesa del server)...
start /b python open_browser.py

echo Avvio del server (premi Ctrl+C per fermarlo)...
uvicorn main:app --reload --host 127.0.0.1 --port 8000

pause
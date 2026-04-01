@echo off
echo Creazione ambiente virtuale con Python 3.11...
py -3.11 -m venv venv

echo Attivazione ambiente...
call venv\Scripts\activate

echo Installazione requisiti...
pip install -r requirements.txt

echo Completato!
pause
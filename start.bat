@echo off
echo Creazione ambiente virtuale...
python -m venv venv

echo Attivazione ambiente...
call venv\Scripts\activate

echo Installazione requisiti...
pip install -r requirements.txt

echo Completato!
pause

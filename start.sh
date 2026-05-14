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

echo "Completato!"
read -p "Premi [Invio] per continuare..."
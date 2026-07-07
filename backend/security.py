"""
Author: Timothy Giolito (20054431)

Ho racchiuso qui dentro tutta l'infrastruttura di sicurezza legata ai JWT.
Avere un modulo dedicato mi permette di tenere i router in ordine e di avere la certezza 
che l'identità di chi fa una richiesta arrivi esclusivamente dal payload del token firmato, 
senza mai fidarci ciecamente dei parametri inviati liberamente dai client.
"""
import os
from datetime import datetime, timedelta, timezone

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer

from src.database.user_service import get_user_data

# Author: Timothy Giolito (20054431)
# Variabili ambientali lette dal sistema operativo. Ho inserito dei valori fittizi di ripiego
# giusto per riuscire a far girare il backend in locale senza impazzire col file .env, 
# ma ovviamente in ambiente di produzione la chiave deve essere ben configurata.
SECRET_KEY = os.getenv("JWT_SECRET_KEY", "chiave-di-sviluppo-non-sicura")
ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30"))

# Author: Timothy Giolito (20054431)
# Dichiariamo lo schema di autenticazione in modo che FastAPI sappia cercare 
# il token Bearer direttamente nell'header HTTP Authorization di ogni chiamata protetta.
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


def create_access_token(data: dict) -> str:
    """
    Author: Timothy Giolito (20054431)
    
    Genera un token firmato iniettando i dati che vogliamo mantenere tracciati
    e appendendo un timestamp di scadenza, dopodiché mi restituisce tutto serializzato.
    """
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def get_current_user(token: str = Depends(oauth2_scheme)) -> int:
    """
    Author: Timothy Giolito (20054431)
    
    Questa funzione fa da guardia ai cancelli. Agisce come dipendenza di FastAPI per validare
    al volo il token in ingresso, decodificarlo, estrarre l'ID dell'utente e accertarsi
    che quel profilo esista ancora nel nostro database prima di farlo passare.
    Se c'è puzza di bruciato per scadenze o manomissioni, sbatte fuori la richiesta con un 401.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Credenziali non valide o sessione scaduta",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        subject = payload.get("sub")
        if subject is None:
            raise credentials_exception
        user_id = int(subject)
    except (jwt.PyJWTError, ValueError, TypeError):
        raise credentials_exception

    # Author: Timothy Giolito (20054431)
    # Controllo di integrità: dobbiamo essere certi che chi ha prodotto il token
    # esista ancora fisicamente sul database prima di procedere.
    if get_user_data(user_id) is None:
        raise credentials_exception

    return user_id

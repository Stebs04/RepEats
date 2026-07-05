"""
Logica di sicurezza centralizzata per l'autenticazione basata su JWT.

Isola in un unico modulo la creazione dei token di accesso e la dipendenza
FastAPI che li valida, così che i router restino puliti e l'identità dell'utente
sia ricavata ESCLUSIVAMENTE dal token firmato (mai da parametri passati dal client).
"""
import os
from datetime import datetime, timedelta, timezone

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer

from src.database.user_service import get_user_data

# Configurazione letta dall'ambiente (.env). I default servono solo a evitare
# crash in sviluppo: in produzione JWT_SECRET_KEY DEVE essere impostata.
SECRET_KEY = os.getenv("JWT_SECRET_KEY", "chiave-di-sviluppo-non-sicura")
ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30"))

# Schema Bearer: estrae automaticamente il token dall'header
# `Authorization: Bearer <token>`. tokenUrl punta all'endpoint di login.
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


def create_access_token(data: dict) -> str:
    """
    Genera un JWT firmato includendo i claim forniti e una scadenza (`exp`).

    Args:
        data: Claim da includere nel payload (es. `{"sub": "<user_id>"}`).

    Returns:
        Il token JWT codificato come stringa.
    """
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def get_current_user(token: str = Depends(oauth2_scheme)) -> int:
    """
    Dipendenza FastAPI: valida il token, ne estrae l'ID utente e ne verifica
    l'esistenza nel database.

    Solleva 401 Unauthorized se il token è mancante, invalido, scaduto oppure
    riferito a un utente inesistente.

    Returns:
        L'ID dell'utente autenticato (int).
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

    # Verifica che l'utente esista ancora (usa i servizi DB esistenti).
    if get_user_data(user_id) is None:
        raise credentials_exception

    return user_id

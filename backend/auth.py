"""
Author: Timothy Giolito (20054431)

Punto d'ingresso per tutta la parte di autenticazione e sicurezza dell'applicazione.
Questo router FastAPI si occupa di validare chi cerca di entrare nel sistema, sia che 
si tratti di un nuovo utente in fase di registrazione sia di un login esistente.
"""
import re
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.exc import IntegrityError
from src.database.user_service import authenticate_user, create_user
from backend.security import create_access_token

router = APIRouter()

class LoginRequest(BaseModel):
    """
    Author: Timothy Giolito (20054431)
    
    Validiamo a monte il payload in ingresso per essere sicuri che ci passino 
    entrambe le credenziali necessarie per fare l'accesso.
    """
    username: str
    password: str

class RegisterRequest(BaseModel):
    """
    Author: Timothy Giolito (20054431)
    
    Struttura attesa quando un nuovo utente tenta di creare un account.
    """
    username: str
    email: str
    password: str

@router.post("/login")
def login(request: LoginRequest):
    """
    Author: Timothy Giolito (20054431)
    
    Riceve le credenziali in chiaro, interroga il database per vedere se matchano 
    con gli hash salvati e, se va tutto liscio, emette un token JWT valido.
    In caso di credenziali sballate interrompiamo subito la richiesta con un 401.
    """
    user = authenticate_user(request.username, request.password)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Username o Password errati"
        )

    # Author: Timothy Giolito (20054431)
    # Creiamo un token JWT firmato usando l'id dell'utente come soggetto principale.
    # Preferisco mantenere le cose sicure, quindi non infilo dati sensibili in chiaro nel payload.
    access_token = create_access_token(data={"sub": str(user.id)})
    return {"access_token": access_token, "token_type": "bearer"}

@router.post("/register")
def register(request: RegisterRequest):
    """
    Author: Timothy Giolito (20054431)
    
    Prende in carico la registrazione di un nuovo profilo.
    Facciamo prima un controllo robusto sulla complessità della password e poi 
    proviamo a scrivere sul db. Se qualcuno prova a rubare uno username o una mail
    già presi, intercettiamo l'errore del database e lo giriamo al frontend in modo pulito.
    """
    if len(request.password) < 8 or \
       not re.search(r"[A-Z]", request.password) or \
       not re.search(r"[a-z]", request.password) or \
       not re.search(r"[0-9]", request.password) or \
       not re.search(r"[!@#$%^&*(),.?\":{}|<>]", request.password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="La password deve contenere almeno 8 caratteri, una lettera maiuscola, una minuscola, un numero e un carattere speciale."
        )

    try:
        new_user = create_user(request.username, request.email, request.password)
        return {
            "message": "Registrazione completata!",
            "user_id": new_user.id,
            "username": new_user.username
        }
    except IntegrityError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="L'email o l'username inseriti sono già in uso. Prova ad accedere o utilizzane di diversi."
        )
    except Exception as e:
        # Author: Timothy Giolito (20054431)
        # Se capita un'eccezione non prevista la stampo sulla console del server per 
        # capire al volo cosa è andato storto, e mando un generico errore 400 al client.
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=400, detail=f"Errore imprevisto durante la registrazione: {str(e)}")
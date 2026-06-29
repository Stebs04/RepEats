"""
Modulo router per l'autenticazione.
Espone gli endpoint di login e registrazione per l'integrazione frontend.
"""
import re
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.exc import IntegrityError
from src.database.user_service import authenticate_user, create_user

router = APIRouter()

class LoginRequest(BaseModel):
    """Schema di validazione per le credenziali di accesso."""
    username: str
    password: str

class RegisterRequest(BaseModel):
    """Schema di validazione per i dati di onboarding utente."""
    username: str
    email: str
    password: str

@router.post("/login")
def login(request: LoginRequest):
    """
    Autentica l'utente confrontando le credenziali.
    Solleva 401 Unauthorized in caso di match fallito.
    """
    user = authenticate_user(request.username, request.password)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Username o Password errati"
        )
    
    return {
        "message": "Login effettuato con successo",
        "user_id": user.id,
        "username": user.username
    }

@router.post("/register")
def register(request: RegisterRequest):
    """
    Crea un nuovo account utente.
    Cattura eccezioni a livello db (es. vincoli unicità violati) castandole a 400 Bad Request.
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
        # Dump dello stack trace su stdout per debugging interno rapido
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=400, detail=f"Errore imprevisto durante la registrazione: {str(e)}")
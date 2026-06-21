"""
Modulo router per l'autenticazione.
Espone gli endpoint di login e registrazione per l'integrazione frontend.
"""
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
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
    try:
        new_user = create_user(request.username, request.email, request.password)
        return {
            "message": "Registrazione completata!",
            "user_id": new_user.id,
            "username": new_user.username
        }
    except Exception as e:
        # Dump dello stack trace su stdout per debugging interno rapido
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=400, detail=f"Errore nella registrazione: {str(e)}")
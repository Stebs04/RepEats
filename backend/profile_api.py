from fastapi import APIRouter, HTTPException, Query, Depends
from src.database.user_service import update_user_profile, get_user_data
from pydantic import BaseModel
from backend.security import get_current_user

router = APIRouter()

class ProfileUpdate(BaseModel):
    """
    Schema di validazione in ingresso per l'upsert dei dati anagrafici e degli obiettivi.
    
    Author: Stefano Bellan (20054330)
    """
    age: int
    weight: float
    height: float
    gender: str
    activity_level: float
    target_weight: float
    target_weeks: int
    goal_type: str
    workout_duration: int
    workout_preference: str
    allergies: str | None = None
    dietary_preferences: str | None = None

@router.post("/update")
def update_profile(data: ProfileUpdate, user_id: int = Depends(get_current_user)):
    """
    Endpoint per il provisioning parziale o totale dei metadati del profilo.
    I valori forniti sovrascrivono lo stato persistito per l'utente loggato.
    
    Author: Stefano Bellan (20054330)
    """
    try:
        update_user_profile(
            user_id=user_id,
            weight=data.weight,
            height=data.height,
            age=data.age,
            gender=data.gender,
            activity_level=data.activity_level,
            target_weight=data.target_weight,
            target_weeks=data.target_weeks,
            goal_type=data.goal_type,
            workout_duration=data.workout_duration,
            workout_preference=data.workout_preference,
            allergies=data.allergies,
            dietary_preferences=data.dietary_preferences
        )
        return {"message": "Profilo aggiornato con successo"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/get")
def get_profile(user_id: int = Depends(get_current_user)):
    """
    Esposizione in sola lettura dei metadati anagrafici consolidati.
    
    Author: Stefano Bellan (20054330)
    """
    try:
        user_data = get_user_data(user_id)
        if not user_data:
            # Ritorno formattato in fallback per entità anagrafica non inizializzata a db
            return {"data": {}}
        return {"data": user_data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

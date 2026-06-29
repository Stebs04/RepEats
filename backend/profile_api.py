from fastapi import APIRouter, HTTPException, Query
from src.database.user_service import update_user_profile, get_user_data
from pydantic import BaseModel

router = APIRouter()

class ProfileUpdate(BaseModel):
    user_id: int
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

@router.post("/update")
def update_profile(data: ProfileUpdate):
    try:
        update_user_profile(
            user_id=data.user_id,
            weight=data.weight,
            height=data.height,
            age=data.age,
            gender=data.gender,
            activity_level=data.activity_level,
            target_weight=data.target_weight,
            target_weeks=data.target_weeks,
            goal_type=data.goal_type,
            workout_duration=data.workout_duration,
            workout_preference=data.workout_preference
        )
        return {"message": "Profilo aggiornato con successo"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/get")
def get_profile(user_id: int = Query(...)):
    try:
        user_data = get_user_data(user_id)
        if not user_data:
            # Ritorna campi vuoti di default se non esiste ancora un profilo completo
            return {"data": {}}
        return {"data": user_data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

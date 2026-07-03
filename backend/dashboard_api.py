from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime, timezone, date as date_type
from src.database.user_service import get_user_data, get_macros_by_date, calculate_daily_macros, delete_meal_log, get_user_workout_plans, delete_workout_plan, update_workout_plan_by_id

router = APIRouter()

class ExercisePayload(BaseModel):
    """Singolo esercizio inviato dal frontend durante la modifica manuale di una scheda."""
    name: str
    muscle_group: Optional[str] = ""
    sets: int = 3
    reps: str = "10"
    rest_time: Optional[str] = "90s"

class WorkoutUpdateRequest(BaseModel):
    """Payload per l'aggiornamento manuale di una scheda di allenamento."""
    name: str
    exercises: List[ExercisePayload]

@router.get("/stats")
def get_dashboard_stats(user_id: int = Query(...), date: Optional[str] = Query(None, description="Data nel formato YYYY-MM-DD; se assente usa oggi")):
    try:
        # Recuperiamo i dati del profilo e l'obiettivo (es. "dimagrimento")
        user_data = get_user_data(user_id)
        if not user_data:
            raise HTTPException(status_code=404, detail="Utente non trovato")

        # Determiniamo la data richiesta (default: oggi in UTC)
        if date:
            try:
                data_selezionata = date_type.fromisoformat(date)
            except ValueError:
                raise HTTPException(status_code=422, detail="Formato data non valido, usare YYYY-MM-DD")
        else:
            data_selezionata = datetime.now(timezone.utc).date()

        # Recuperiamo quello che l'utente ha effettivamente mangiato nella data selezionata
        macros_odierni = get_macros_by_date(user_id, data_selezionata)

        # Calcoliamo matematicamente i suoi limiti in base al metabolismo
        target_macros = calculate_daily_macros(user_id)

        # Uniamo tutto in un unico "pacchetto" JSON pronto per la pagina HTML

        # Recupero i pasti della data selezionata per categoria
        from sqlalchemy import func
        from src.database.database import get_session
        from src.database.models import MealLog

        session = get_session()
        meals_today_records = session.query(MealLog).filter(
            MealLog.user_id == user_id,
            func.date(MealLog.timestamp) == data_selezionata
        ).all()
        session.close()

        meals_by_cat = {"Colazione": [], "Pranzo": [], "Cena": [], "Spuntino": []}
        for m in meals_today_records:
            cat = m.category if m.category in meals_by_cat else "Spuntino"
            meals_by_cat[cat].append({
                "id": m.id,
                "name": m.name,
                "calories": m.calories,
                "proteins": m.proteins,
                "carbs": m.carbohydrates,
                "fats": m.fats
            })

        return {
            "date": data_selezionata.isoformat(),
            "meals": meals_by_cat,
            "user": user_data,
            "today": macros_odierni,
            "targets": target_macros
        }
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/meal/{meal_id}")
def delete_meal(meal_id: int, user_id: int = Query(...)):
    """
    Elimina un pasto specifico dal database.
    Richiede user_id come query param per sicurezza (ownership check nel DB service).
    """
    try:
        success = delete_meal_log(user_id=user_id, meal_id=meal_id)
        if not success:
            raise HTTPException(status_code=404, detail="Pasto non trovato o non autorizzato")
        return {"message": "Pasto eliminato con successo"}
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/workouts")
def get_workouts(user_id: int = Query(...)):
    """
    Recupera tutte le schede di allenamento dell'utente.
    """
    try:
        plans = get_user_workout_plans(user_id)
        return {"workouts": plans}
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/workout/{plan_id}")
def update_workout(plan_id: int, request: WorkoutUpdateRequest, user_id: int = Query(...)):
    """
    Aggiorna manualmente una scheda di allenamento (nome ed esercizi).
    Usato dal form di modifica locale del frontend, senza passare per l'agente AI.
    """
    try:
        if not request.name.strip():
            raise HTTPException(status_code=422, detail="Il nome della scheda non può essere vuoto")
        if not request.exercises:
            raise HTTPException(status_code=422, detail="La scheda deve contenere almeno un esercizio")

        success = update_workout_plan_by_id(
            user_id=user_id,
            plan_id=plan_id,
            plan_name=request.name.strip(),
            exercises=[e.model_dump() for e in request.exercises]
        )
        if not success:
            raise HTTPException(status_code=404, detail="Scheda non trovata o non autorizzato")
        return {"message": "Scheda aggiornata con successo"}
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/workout/{plan_id}")
def delete_workout(plan_id: int, user_id: int = Query(...)):
    """
    Elimina una scheda di allenamento specifica dal database.
    """
    try:
        success = delete_workout_plan(user_id=user_id, plan_id=plan_id)
        if not success:
            raise HTTPException(status_code=404, detail="Scheda non trovata o non autorizzato")
        return {"message": "Scheda eliminata con successo"}
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))
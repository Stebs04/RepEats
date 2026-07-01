from fastapi import APIRouter, HTTPException, Query
from src.database.user_service import get_user_data, get_todays_macros, calculate_daily_macros, delete_meal_log, get_user_workout_plans, delete_workout_plan, update_workout_plan_by_id

router = APIRouter()

@router.get("/stats")
def get_dashboard_stats(user_id: int = Query(...), date: str = Query(None)):
    try:
        from datetime import datetime, timezone
        from sqlalchemy import func
        from src.database.database import get_session
        from src.database.models import MealLog

        if date:
            try:
                target_date = datetime.strptime(date, "%Y-%m-%d").date()
            except ValueError:
                target_date = datetime.now(timezone.utc).date()
        else:
            target_date = datetime.now(timezone.utc).date()

        # Recuperiamo i dati del profilo e l'obiettivo (es. "dimagrimento")
        user_data = get_user_data(user_id)
        if not user_data:
            raise HTTPException(status_code=404, detail="Utente non trovato")
            
        # Recuperiamo quello che l'utente ha effettivamente mangiato per la data target
        macros_odierni = get_todays_macros(user_id, target_date)
        
        # Calcoliamo matematicamente i suoi limiti in base al metabolismo
        target_macros = calculate_daily_macros(user_id)
        
        # Uniamo tutto in un unico "pacchetto" JSON pronto per la pagina HTML
        
        # Recupero i pasti della data target per categoria
        session = get_session()
        meals_today_records = session.query(MealLog).filter(
            MealLog.user_id == user_id,
            func.date(MealLog.timestamp) == target_date
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

from pydantic import BaseModel
from typing import List, Dict, Any

class WorkoutPlanUpdate(BaseModel):
    name: str
    exercises: List[Dict[str, Any]]

@router.put("/workout/{plan_id}")
def update_workout(plan_id: int, request: WorkoutPlanUpdate, user_id: int = Query(...)):
    """
    Modifica una scheda di allenamento esistente.
    """
    try:
        success = update_workout_plan_by_id(user_id=user_id, plan_id=plan_id, plan_name=request.name, exercises=request.exercises)
        if not success:
            raise HTTPException(status_code=404, detail="Scheda non trovata o non autorizzato")
        return {"message": "Scheda aggiornata con successo"}
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))
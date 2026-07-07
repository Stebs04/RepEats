from fastapi import APIRouter, HTTPException, Query, Depends
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime, timezone, date as date_type
from src.database.user_service import get_user_data, get_macros_by_date, calculate_daily_macros, delete_meal_log, get_user_workout_plans, delete_workout_plan, update_workout_plan_by_id
from backend.security import get_current_user

router = APIRouter()

class ExercisePayload(BaseModel):
    """
    Struttura dati per la validazione di un singolo record di esercizio in ingresso.
    
    Author: Stefano Bellan (20054330)
    """
    name: str
    muscle_group: Optional[str] = ""
    sets: int = 3
    reps: str = "10"
    rest_time: Optional[str] = "90s"

class WorkoutUpdateRequest(BaseModel):
    """
    Modello per la serializzazione delle mutazioni applicate alle schede di allenamento.
    
    Author: Stefano Bellan (20054330)
    """
    name: str
    exercises: List[ExercisePayload]

@router.get("/stats")
def get_dashboard_stats(date: Optional[str] = Query(None, description="Data nel formato YYYY-MM-DD; se assente usa oggi"), user_id: int = Depends(get_current_user)):
    try:
        # Fetching dei metadati anagrafici e obiettivi nutrizionali associati al token utente
        user_data = get_user_data(user_id)
        if not user_data:
            raise HTTPException(status_code=404, detail="Utente non trovato")

        # Normalizzazione temporale: fallback implicito sul layer UTC corrente se omessa
        if date:
            try:
                data_selezionata = date_type.fromisoformat(date)
            except ValueError:
                raise HTTPException(status_code=422, detail="Formato data non valido, usare YYYY-MM-DD")
        else:
            data_selezionata = datetime.now(timezone.utc).date()

        # Aggregazione parametrica del bilancio calorico parziale per la porzione di timeline in esame
        macros_odierni = get_macros_by_date(user_id, data_selezionata)

        # Computazione in runtime della soglia calorica totale derivata dal TDEE anagrafico
        target_macros = calculate_daily_macros(user_id)

        # Assemblaggio del payload consolidato destinato al layer di presentazione

        # Interrogazione del database per il partizionamento categorico degli intake giornalieri
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
def delete_meal(meal_id: int, user_id: int = Depends(get_current_user)):
    """
    Gestisce la rimozione definitiva di una entry nutrizionale.
    
    Il parametro di utenza viene risolto a livello middleware per validare
    l'appartenenza della risorsa prima della mutazione fisica sul db.
    
    Author: Stefano Bellan (20054330)
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
def get_workouts(user_id: int = Depends(get_current_user)):
    """
    Astrazione per il retrieving massivo dei piani di allenamento associati all'utente corrente.
    
    Author: Stefano Bellan (20054330)
    """
    try:
        plans = get_user_workout_plans(user_id)
        return {"workouts": plans}
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/workout/{plan_id}")
def update_workout(plan_id: int, request: WorkoutUpdateRequest, user_id: int = Depends(get_current_user)):
    """
    Endpoint per la sovrascrittura programmatica delle metriche del piano d'allenamento.
    
    Progettato per bypassare il workflow conversazionale dell'agente e
    permettere manipolazioni CRUD dirette da interfaccia client.
    
    Author: Stefano Bellan (20054330)
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
def delete_workout(plan_id: int, user_id: int = Depends(get_current_user)):
    """
    Terminazione del ciclo di vita di un piano di allenamento specifico.
    
    Author: Stefano Bellan (20054330)
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
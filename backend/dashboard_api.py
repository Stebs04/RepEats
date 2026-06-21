from fastapi import APIRouter, HTTPException, Query
from src.database.user_service import get_user_data, get_todays_macros, calculate_daily_macros, delete_meal_log

router = APIRouter()

@router.get("/stats")
def get_dashboard_stats(user_id: int = Query(...)):
    try:
        # Recuperiamo i dati del profilo e l'obiettivo (es. "dimagrimento")
        user_data = get_user_data(user_id)
        if not user_data:
            raise HTTPException(status_code=404, detail="Utente non trovato")
            
        # Recuperiamo quello che l'utente ha effettivamente mangiato oggi
        macros_odierni = get_todays_macros(user_id)
        
        # Calcoliamo matematicamente i suoi limiti in base al metabolismo
        target_macros = calculate_daily_macros(user_id)
        
        # Uniamo tutto in un unico "pacchetto" JSON pronto per la pagina HTML
        
        # Recupero i pasti di oggi per categoria
        from datetime import datetime, timezone
        from sqlalchemy import func
        from src.database.database import get_session
        from src.database.models import MealLog

        session = get_session()
        today_date = datetime.now(timezone.utc).date()
        meals_today_records = session.query(MealLog).filter(
            MealLog.user_id == user_id,
            func.date(MealLog.timestamp) == today_date
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
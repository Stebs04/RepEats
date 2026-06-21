"""
Router per la gestione della chat AI.
Gestisce l'invio dei messaggi, il recupero del contesto utente e l'interazione con l'agente.
"""
from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from pydantic import BaseModel
from typing import Optional
import tempfile
import os
from agno.models.message import Image as AgnoImage
from src.agents.nutritionst import NutritionistAgent, MealAnalysis
from src.database.user_service import (
    get_user_data, 
    get_todays_macros, 
    save_message, 
    get_chat_history, 
    create_new_conversation,
    calculate_daily_macros,
    save_meal_log,
    get_user_conversations,
    rename_conversation,
    delete_conversation
)
from src.agents.fitness_agent import get_fitness_agent

router = APIRouter()

class ChatMessageRequest(BaseModel):
    """Payload per l'invio di un messaggio nella chat."""
    user_id: int
    conversation_id: Optional[int] = None
    message: str


@router.post("/send")
def send_chat_message(request: ChatMessageRequest):
    """
    Elabora un nuovo messaggio dell'utente.
    Inizializza una nuova conversazione se assente e inietta il contesto nutrizionale all'agente.
    """
    try:
        user_data = get_user_data(request.user_id)
        macros_odierni = get_todays_macros(request.user_id)
        daily_targets = calculate_daily_macros(request.user_id)

        conv_id = request.conversation_id
        
        if not conv_id:
            titolo = request.message[:30] + "..." if len(request.message) > 30 else request.message
            nuova_conv = create_new_conversation(request.user_id, title=titolo)
            conv_id = nuova_conv.id

        save_message(conv_id, "user", request.message)

        history = get_chat_history(conv_id)
        team_agent = get_fitness_agent(user_data, macros_odierni, daily_targets, history)

        response = team_agent.run(request.message)
        ai_text = response.content

        save_message(conv_id, "assistant", ai_text)

        return {
            "reply": ai_text,
            "conversation_id": conv_id
        }
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Errore nell'elaborazione del messaggio: {str(e)}")

@router.post("/vision")
async def analyze_food_image(
    user_id: int = Form(...),
    grammatura: int = Form(...),
    categoria: str = Form("Spuntino"),
    file: UploadFile = File(...)
):
    contents = await file.read()
    with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as tmp:
        tmp.write(contents)
        tmp_path = tmp.name

    try:
        agent = NutritionistAgent()
        prompt_agente = (
            f"Analizza accuratamente l'immagine del pasto o il codice a barre (usa gli strumenti a tua disposizione). "
            f"IMPORTANTE: L'utente ha indicato che la porzione consumata è di ESATTAMENTE {grammatura} grammi. "
            f"Se usi lo strumento del codice a barre (che restituisce valori per 100g), DEVI FARE LA PROPORZIONE MATEMATICA per ricalcolare i valori su {grammatura}g. "
            "Restituisci ESCLUSIVAMENTE un oggetto JSON valido per lo schema MealAnalysis. Non aggiungere testo prima o dopo. "
            "DEVI restituire i dati seguendo rigorosamente lo schema MealAnalysis: "
            "name: estrai il nome del prodotto o un nome descrittivo. "
            f"analysis_result: una breve descrizione. Includi una frase del tipo 'Valori stimati per {grammatura}g'. "
            f"calories, proteins, carbohydrates, fats: solo numeri (i valori finali calcolati per {grammatura}g). "
            "NON aggiungere chiacchiere extra, rispondi solo con i dati strutturati."
        )
        
        response = agent.run(
            prompt_agente, 
            images=[AgnoImage(filepath=tmp_path)],
            response_model=MealAnalysis
        )
        
        raw_content = response.content
        if isinstance(raw_content, str):
            clean_json = raw_content.replace("```json", "").replace("```", "").strip()
            analysis = MealAnalysis.model_validate_json(clean_json)
        else:
            analysis = raw_content
            
        save_meal_log(
            user_id=user_id,
            analysis_result=analysis.model_dump_json(),
            category=categoria,
            name=analysis.name,
            calories=analysis.calories,
            proteins=analysis.proteins,
            carbs=analysis.carbohydrates,
            fats=analysis.fats
        )
        
        return {
            "message": "Pasto analizzato e salvato con successo!",
            "data": analysis.model_dump()
        }
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Errore Vision: {str(e)}")
    finally:
        os.remove(tmp_path)


@router.get("/sessions")
def get_sessions(user_id: int):
    try:
        convs = get_user_conversations(user_id)
        return {"sessions": [{"id": c.id, "title": c.title, "created_at": c.created_at} for c in convs]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/session/{conversation_id}")
def get_session_history(conversation_id: int):
    try:
        history = get_chat_history(conversation_id)
        return {"history": [{"role": m.role, "content": m.content} for m in history]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

class RenameRequest(BaseModel):
    title: str

@router.put("/session/{conversation_id}")
def rename_session(conversation_id: int, request: RenameRequest):
    try:
        rename_conversation(conversation_id, request.title)
        return {"message": "Rinominato con successo"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/session/{conversation_id}")
def delete_session(conversation_id: int):
    try:
        delete_conversation(conversation_id)
        return {"message": "Cancellato con successo"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

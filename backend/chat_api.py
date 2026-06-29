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
from agno.agent import Agent
from agno.models.groq import Groq as GroqModel
from src.agents.nutritionst import NutritionistAgent, VisionNutritionistAgent, MealAnalysis
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
from src.orchestrator import get_orchestrator

router = APIRouter()

class ChatMessageRequest(BaseModel):
    """Payload per l'invio di un messaggio nella chat."""
    user_id: int
    conversation_id: Optional[int] = None
    message: str
    chat_type: Optional[str] = "nutritionist"


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
            nuova_conv = create_new_conversation(request.user_id, title=titolo, chat_type=request.chat_type)
            conv_id = nuova_conv.id

        save_message(conv_id, "user", request.message)

        history = get_chat_history(conv_id)
        team_agent = get_orchestrator(user_data, macros_odierni, daily_targets, history, request.chat_type)

        response = team_agent.run(request.message)
        
        # Estrazione robusta del testo dalla risposta del team agent.
        # Con show_members_responses=True, response.content potrebbe essere:
        # - una stringa (il caso normale)
        # - None se l'output è strutturato in modo diverso
        # - un oggetto non-stringa
        if isinstance(response.content, str) and response.content.strip():
            ai_text = response.content
        elif hasattr(response, 'messages') and response.messages:
            # Prende l'ultimo messaggio assistant disponibile
            assistant_msgs = [m for m in response.messages if getattr(m, 'role', '') == 'assistant']
            if assistant_msgs:
                ai_text = getattr(assistant_msgs[-1], 'content', str(response.content))
            else:
                ai_text = str(response.content)
        else:
            ai_text = str(response.content) if response.content else "Mi dispiace, non ho ricevuto una risposta."

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
        user_data = get_user_data(user_id)
        obiettivo = user_data.get("goal_type", "mantenimento") if user_data else "mantenimento"

        # ================================================================
        # FASE 1: Agente Vision con Tool Calling (testo libero)
        # Groq non supporta vision + tool + structured output insieme.
        # Prima lasciamo che l'agente veda l'immagine e chiami il tool
        # per il barcode, restituendo dati grezzi come testo.
        # ================================================================
        agent_fase1 = VisionNutritionistAgent()
        prompt_fase1 = (
            f"Analizza questa immagine. "
            f"SE vedi un CODICE A BARRE: leggi il numero e usa OBBLIGATORIAMENTE lo strumento get_product_info_by_barcode per trovare il prodotto. "
            f"SE vedi del CIBO: identifica il piatto e stima i valori nutrizionali per {grammatura}g. "
            f"Rispondi con un testo che contenga chiaramente: "
            f"1) Il nome del prodotto/piatto "
            f"2) Le calorie, proteine, carboidrati e grassi per {grammatura}g "
            f"(se hai i valori per 100g dal barcode, fai la proporzione: valore * {grammatura} / 100) "
            f"3) Una breve descrizione. "
            f"Sii preciso con i numeri. Non restituire JSON, solo testo descrittivo."
        )

        response_fase1 = agent_fase1.run(
            prompt_fase1,
            images=[AgnoImage(filepath=tmp_path)],
        )

        # Estrai il testo dalla risposta della fase 1
        if isinstance(response_fase1.content, str):
            testo_analisi = response_fase1.content
        else:
            testo_analisi = str(response_fase1.content)

        # ================================================================
        # FASE 2: Agente Parser - converte il testo in MealAnalysis JSON
        # Nessuna immagine, nessun tool: solo conversione testo → struttura
        # ================================================================
        agente_parser = Agent(
            model=GroqModel(id="meta-llama/llama-4-scout-17b-16e-instruct"),
            description="Converti dati nutrizionali in JSON strutturato.",
            instructions=[
                "Sei un parser di dati nutrizionali. Ricevi un testo con informazioni su un alimento e devi estrarne i dati in formato JSON.",
                "REGOLE CRITICHE:",
                "1. Restituisci SOLO un oggetto JSON valido, senza testo prima o dopo.",
                "2. Il JSON deve avere ESATTAMENTE questi campi: name, analysis_result, calories, proteins, carbohydrates, fats, advice.",
                "3. calories, proteins, carbohydrates, fats devono essere numeri float (non stringhe).",
                "4. Se il testo dice che il prodotto non è stato trovato o i valori sono 0, usa 0.0 come valore.",
                "5. analysis_result deve essere una frase descrittiva.",
                f"6. I valori devono essere riferiti a {grammatura}g di prodotto.",
                f"7. Genera in 'advice' un consiglio velocissimo (max 1 riga) su cosa mangiare dopo, considerando che l'obiettivo dell'utente è: {obiettivo}",
                "Template JSON da restituire:",
                '{{"name": "nome prodotto", "analysis_result": "descrizione", "calories": 0.0, "proteins": 0.0, "carbohydrates": 0.0, "fats": 0.0, "advice": "Il tuo consiglio qui."}}',
            ],
            markdown=False,
        )

        prompt_fase2 = (
            f"Converti questi dati in JSON strutturato (valori per {grammatura}g) e genera il consiglio in base all'obiettivo ({obiettivo}):\n\n"
            f"{testo_analisi}\n\n"
            f"Restituisci SOLO il JSON, nessun altro testo."
        )

        response_fase2 = agente_parser.run(prompt_fase2)

        raw_content = response_fase2.content
        if isinstance(raw_content, str):
            clean_json = raw_content.replace("```json", "").replace("```", "").strip()
            # Rimuovi eventuali caratteri non-JSON all'inizio/fine
            if clean_json.find('{') != -1:
                clean_json = clean_json[clean_json.find('{'):clean_json.rfind('}')+1]
            analysis = MealAnalysis.model_validate_json(clean_json)
        elif isinstance(raw_content, MealAnalysis):
            analysis = raw_content
        else:
            analysis = MealAnalysis(
                name="Prodotto non identificato",
                analysis_result=testo_analisi[:200] if testo_analisi else "Analisi non disponibile",
                calories=0.0, proteins=0.0, carbohydrates=0.0, fats=0.0
            )
            
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
def get_sessions(user_id: int, chat_type: Optional[str] = None):
    try:
        convs = get_user_conversations(user_id, chat_type)
        return {"sessions": [{"id": c.id, "title": c.title, "created_at": c.created_at} for c in convs]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/session/{conversation_id}")
def get_session_history(conversation_id: int):
    try:
        history = get_chat_history(conversation_id)
        return {"history": history}
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

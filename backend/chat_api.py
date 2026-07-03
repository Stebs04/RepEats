"""
Router per la gestione della chat AI.
Gestisce l'invio dei messaggi, il recupero del contesto utente e l'interazione con l'agente.
"""
from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from pydantic import BaseModel
from typing import Optional
import tempfile
import os
import re
from agno.models.message import Image as AgnoImage
from agno.agent import Agent
from agno.models.groq import Groq as GroqModel
from src.agents.nutritionst import NutritionistAgent, VisionNutritionistAgent, MealAnalysis
from src.tools.openfoodfacts_tool import get_product_info_by_barcode, BarcodeSearchInput
from src.tools.barcode_scanner import scan_barcode
from src.database.user_service import (
    get_user_data, 
    get_macros_by_date,
    save_message, 
    get_chat_history, 
    create_new_conversation,
    calculate_daily_macros,
    save_meal_log,
    get_user_conversations,
    rename_conversation,
    delete_conversation,
    get_user_workout_plans
)
from src.orchestrator import get_orchestrator

router = APIRouter()

class ChatMessageRequest(BaseModel):
    """Payload per l'invio di un messaggio nella chat."""
    user_id: int
    conversation_id: Optional[int] = None
    message: str
    chat_type: Optional[str] = "nutritionist"


def _workout_snapshot(user_id: int) -> list:
    """
    Crea una "fotografia" delle schede di allenamento dell'utente (nomi ed esercizi).
    Serve a verificare in modo deterministico se una run dell'agente Coach
    ha davvero scritto qualcosa nel database, senza fidarsi del testo della risposta.
    """
    return [
        (
            p["id"],
            p["name"],
            tuple((e["name"], e["muscle_group"], e["sets"], e["reps"], e["rest_time"]) for e in p["exercises"])
        )
        for p in get_user_workout_plans(user_id)
    ]


def _extract_ai_text(response) -> str:
    """
    Estrazione robusta del testo dalla risposta del team agent.
    Con show_members_responses=True, response.content potrebbe essere:
    - una stringa (il caso normale)
    - None se l'output è strutturato in modo diverso
    - un oggetto non-stringa
    """
    if isinstance(response.content, str) and response.content.strip():
        return response.content
    if hasattr(response, 'messages') and response.messages:
        # Prende l'ultimo messaggio assistant disponibile
        assistant_msgs = [m for m in response.messages if getattr(m, 'role', '') == 'assistant']
        if assistant_msgs:
            return getattr(assistant_msgs[-1], 'content', str(response.content))
        return str(response.content)
    return str(response.content) if response.content else "Mi dispiace, non ho ricevuto una risposta."


@router.post("/send")
def send_chat_message(request: ChatMessageRequest):
    """
    Elabora un nuovo messaggio dell'utente.
    Inizializza una nuova conversazione se assente e inietta il contesto nutrizionale all'agente.
    """
    try:
        user_data = get_user_data(request.user_id)
        macros_odierni = get_macros_by_date(request.user_id)
        daily_targets = calculate_daily_macros(request.user_id)

        conv_id = request.conversation_id
        
        if not conv_id:
            titolo = request.message[:30] + "..." if len(request.message) > 30 else request.message
            nuova_conv = create_new_conversation(request.user_id, title=titolo, chat_type=request.chat_type)
            conv_id = nuova_conv.id

        save_message(conv_id, "user", request.message)

        history = get_chat_history(conv_id)
        team_agent = get_orchestrator(user_data, macros_odierni, daily_targets, history, request.chat_type)

        # Fotografia delle schede PRIMA della run: permette di verificare
        # deterministicamente se l'agente ha davvero scritto sul database.
        is_coach = request.chat_type == "coach"
        snapshot_prima = _workout_snapshot(request.user_id) if is_coach else None

        response = team_agent.run(request.message)
        ai_text = _extract_ai_text(response)

        # ============================================================
        # RETE DI SICUREZZA (solo Coach): se l'agente DICHIARA di aver
        # salvato/modificato una scheda ma il database risulta invariato,
        # significa che non ha chiamato il tool. Gli inviamo un messaggio
        # di sistema (invisibile all'utente) che lo obbliga a chiamare
        # il tool con la scheda appena proposta. La risposta originale
        # resta quella mostrata all'utente.
        # ============================================================
        workouts_updated = False
        if is_coach:
            workouts_updated = _workout_snapshot(request.user_id) != snapshot_prima
            low = ai_text.lower()
            claims_save = "sched" in low and re.search(r"salvat|aggiornat|modificat|memorizzat", low)
            if claims_save and not workouts_updated:
                recovery_prompt = (
                    "MESSAGGIO AUTOMATICO DI SISTEMA (l'utente NON vede questo messaggio, non rispondergli): "
                    "nella tua ultima risposta hai dichiarato di aver salvato o aggiornato una scheda di allenamento, "
                    "ma nel database NON risulta alcuna modifica: non hai chiamato lo strumento. "
                    "Questa era la tua ultima risposta:\n\n"
                    f"{ai_text}\n\n"
                    "Ricava da questa risposta il nome della scheda e i suoi esercizi, e chiama ADESSO lo strumento "
                    "`create_workout_plan_tool` (oppure `modify_workout_plan_tool` se si trattava della modifica di "
                    "una scheda esistente) per salvarla davvero. Rispondi solo con una breve conferma."
                )
                team_agent.run(recovery_prompt)
                workouts_updated = _workout_snapshot(request.user_id) != snapshot_prima

        save_message(conv_id, "assistant", ai_text)

        return {
            "reply": ai_text,
            "conversation_id": conv_id,
            "workouts_updated": workouts_updated
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
    barcode_manuale: str = Form(""),
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
        # FASE 0: Rilevamento barcode.
        # Priorità al codice inserito a mano dall'utente (fallback robusto
        # quando la foto è troppo sfocata/rumorosa per l'OCR): se presente e
        # plausibile (8-14 cifre) lo usiamo direttamente, saltando lo scan.
        # Altrimenti detection deterministica sui pixel (OpenCV), nessun LLM:
        # se l'immagine è cibo senza codice a barre scan_barcode restituisce
        # None e si passa alla stima visiva. Zero allucinazioni.
        # ================================================================
        barcode_pulito = "".join(filter(str.isdigit, barcode_manuale or ""))
        if 8 <= len(barcode_pulito) <= 14:
            barcode = barcode_pulito
        else:
            barcode = scan_barcode(tmp_path)

        fonte = "stima"
        testo_analisi = None

        if barcode:
            # Percorso barcode: tool chiamato direttamente dal codice,
            # proporzione calcolata in Python (nessuna stima LLM).
            prod = get_product_info_by_barcode(BarcodeSearchInput(barcode=barcode))
            if prod.energy_kcal_100g is not None:
                fattore = grammatura / 100.0
                fonte = "openfoodfacts"
                testo_analisi = (
                    f"Prodotto: {prod.product_name}. Dati OpenFoodFacts per {grammatura}g: "
                    f"{round((prod.energy_kcal_100g or 0) * fattore, 1)} kcal, "
                    f"{round((prod.proteins_100g or 0) * fattore, 1)}g proteine, "
                    f"{round((prod.carbohydrates_100g or 0) * fattore, 1)}g carboidrati, "
                    f"{round((prod.fat_100g or 0) * fattore, 1)}g grassi."
                )
            # Prodotto non trovato: si prosegue con la stima visiva qui sotto.

        if testo_analisi is None:
            # ================================================================
            # FASE 1: Stima visiva pura. L'agente NON ha il tool OpenFoodFacts
            # registrato, quindi non può usarlo nemmeno per errore.
            # ================================================================
            agent_fase1 = VisionNutritionistAgent(with_barcode_tool=False)
            prompt_fase1 = (
                f"Riconosci l'alimento in questa immagine. "
                f"Stima i valori nutrizionali per 100g, poi scala per {grammatura}g (valore_100g * {grammatura} / 100). "
                f"Rispondi con un testo che contenga chiaramente: "
                f"1) Il nome del piatto "
                f"2) Le calorie, proteine, carboidrati e grassi per {grammatura}g "
                f"3) Una breve descrizione. "
                f"Sii preciso con i numeri. Non restituire JSON, solo testo descrittivo."
            )
            response_fase1 = agent_fase1.run(
                prompt_fase1,
                images=[AgnoImage(filepath=tmp_path)],
            )
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
        
        data_out = analysis.model_dump()
        data_out["fonte"] = fonte  # "openfoodfacts" o "stima"
        return {
            "message": "Pasto analizzato e salvato con successo!",
            "data": data_out
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

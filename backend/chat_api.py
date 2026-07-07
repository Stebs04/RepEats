"""
Router API per le interazioni testuali con l'intelligenza artificiale.

Gestisce in modo centralizzato lo streaming dei messaggi, il recupero 
dello storico conversazionale e l'arricchimento del contesto utente 
prima di delegare l'esecuzione all'agente.

Author: Stefano Bellan (20054330)
"""
from fastapi import APIRouter, HTTPException, UploadFile, File, Form, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional
import tempfile
import os
import re
import json
from agno.run.team import RunContentEvent
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
    get_macros_breakdown_by_category,
    save_meal_log,
    get_user_conversations,
    rename_conversation,
    delete_conversation,
    get_user_workout_plans
)
from src.orchestrator import get_orchestrator
from backend.security import get_current_user

router = APIRouter()

class ChatMessageRequest(BaseModel):
    """
    Rappresentazione strongly-typed della singola richiesta inviata dal client.
    
    Author: Stefano Bellan (20054330)
    """
    conversation_id: Optional[int] = None
    message: str
    chat_type: Optional[str] = "nutritionist"


def _workout_snapshot(user_id: int) -> list:
    """
    Genera un'immagine immutabile e comparabile dello stato corrente delle schede di allenamento.

    Questo meccanismo funge da rete di sicurezza contro le "allucinazioni di azione" tipiche degli LLM.
    Dal momento che un modello potrebbe affermare in output di aver eseguito un'operazione 
    di salvataggio senza aver realmente triggerato il tool, questa fotografia pre-run ci permette di
    verificare deterministicamente se il database ha subito mutazioni dopo la risposta.
    La scelta della tupla semplifica le operazioni di diff riducendole a un banale confronto di uguaglianza.

    Author: Stefano Bellan (20054330)
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
    Sanitizza e recupera il payload testuale dall'oggetto di ritorno dell'agente.
    
    Gestisce in modo difensivo le strutture eterogenee restituite in modalità multi-agente,
    assicurandosi di isolare sempre l'ultimo segmento testuale valido o fornendo 
    un fallback sicuro in caso di parsing fallito.
    
    Author: Stefano Bellan (20054330)
    """
    if isinstance(response.content, str) and response.content.strip():
        return response.content
    if hasattr(response, 'messages') and response.messages:
        # Estrapoliamo programmaticamente l'ultima porzione di testo utile elaborata dall'assistant
        assistant_msgs = [m for m in response.messages if getattr(m, 'role', '') == 'assistant']
        if assistant_msgs:
            return getattr(assistant_msgs[-1], 'content', str(response.content))
        return str(response.content)
    return str(response.content) if response.content else "Mi dispiace, non ho ricevuto una risposta."


def _sse(payload: dict) -> str:
    """
    Impacchetta un dizionario Python in una stringa conforme allo standard Server-Sent Events.
    
    Author: Stefano Bellan (20054330)
    """
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


@router.post("/send")
def send_chat_message(request: ChatMessageRequest, current_user: int = Depends(get_current_user)):
    """
    Innesca l'elaborazione del messaggio instradando la risposta tramite protocollo SSE.
    
    Provvede all'allocazione di un nuovo spazio conversazionale qualora necessario
    e imposta il protocollo trasmissivo per gestire il caricamento token per token,
    includendo gli eventi di setup e terminazione per pilotare coerentemente l'interfaccia.
    
    Author: Stefano Bellan (20054330)
    """
    # Blocchiamo la preparazione in fase sincrona per garantire che, in caso di data failure,
    # il server risponda con uno status HTTP corretto prima di compromettere il buffer di streaming.
    # Affidiamo il recupero dell'identità esclusivamente al middleware di decodifica JWT.
    user_id = current_user
    try:
        user_data = get_user_data(user_id)
        macros_odierni = get_macros_by_date(user_id)
        daily_targets = calculate_daily_macros(user_id)
        breakdown_odierno = get_macros_breakdown_by_category(user_id)

        conv_id = request.conversation_id
        if not conv_id:
            titolo = request.message[:30] + "..." if len(request.message) > 30 else request.message
            nuova_conv = create_new_conversation(user_id, title=titolo, chat_type=request.chat_type)
            conv_id = nuova_conv.id

        save_message(conv_id, "user", request.message)

        history = get_chat_history(conv_id)
        team_agent = get_orchestrator(user_data, macros_odierni, daily_targets, breakdown_odierno, history, request.chat_type)
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Errore nell'elaborazione del messaggio: {str(e)}")

    # Fotografiamo programmaticamente il cluster fitness prima dell'esecuzione
    # per avere un pivot di confronto post-run. Selezioniamo questa via solo
    # per l'agente Coach, essendo l'unico autorizzato ad alterare le schede.
    is_coach = request.chat_type == "coach"
    snapshot_prima = _workout_snapshot(user_id) if is_coach else None

    def event_stream():
        try:
            yield _sse({"type": "start", "conversation_id": conv_id})

            # Intercettiamo progressivamente i token scaricati dall'engine LLM
            # incapsulandoli in frame SSE per abbattere il time-to-first-byte percepito.
            chunks = []
            for event in team_agent.run(request.message, stream=True):
                if isinstance(event, RunContentEvent) and isinstance(event.content, str) and event.content:
                    chunks.append(event.content)
                    yield _sse({"type": "content", "delta": event.content})

            ai_text = "".join(chunks).strip() or "Mi dispiace, non ho ricevuto una risposta."

            # Valutazione di congruenza strutturale (Applicabile solo al Coach)
            # 
            # Implementa un sistema euristico per mitigare i disallineamenti tra
            # testo generato e invocazione reale delle function calling API.
            # Comparando il delta semantico del messaggio con il delta dello stato 
            # fisico del database, individuiamo eventuali allucinazioni operative.
            # Se viene rilevata l'anomalia, forziamo il recupero iniettando in coda
            # un system prompt nascosto che impone la riparazione istantanea del
            # mancato salvataggio, il tutto in via trasparente per il client.
            workouts_updated = False
            if is_coach:
                workouts_updated = _workout_snapshot(user_id) != snapshot_prima
                low = ai_text.lower()
                # Ricerca euristica: intercettiamo espressioni indicative di intenti 
                # di scrittura. Una regex volutamente permissiva ammortizza il rischio
                # di perdere salvataggi legittimi mascherati da un fraseggio atipico.
                claims_save = "sched" in low and re.search(r"salvat|aggiornat|modificat|memorizzat", low)
                if claims_save and not workouts_updated:
                    # Esecuzione del fallback: passiamo il prompt correttivo 
                    # all'engine forzando il parser interno a riconoscere il task saltato.
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
                    team_agent.run(recovery_prompt, stream=False)
                    workouts_updated = _workout_snapshot(user_id) != snapshot_prima

            save_message(conv_id, "assistant", ai_text)

            yield _sse({"type": "end", "workouts_updated": workouts_updated})

        except Exception as e:
            import traceback
            traceback.print_exc()
            yield _sse({"type": "error", "detail": str(e)})

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )

@router.post("/vision")
async def analyze_food_image(
    grammatura: int = Form(...),
    categoria: str = Form("Spuntino"),
    barcode_manuale: str = Form(""),
    file: UploadFile = File(...),
    current_user: int = Depends(get_current_user)
):
    # Astrazione del contesto utente delegata interamente alla validazione del token
    user_id = current_user
    contents = await file.read()
    with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as tmp:
        tmp.write(contents)
        tmp_path = tmp.name

    try:
        user_data = get_user_data(user_id)
        obiettivo = user_data.get("goal_type", "mantenimento") if user_data else "mantenimento"

        # Esecuzione del blocco di decodifica visiva
        # Privilegiamo l'input esplicito se fornito (bypass sicuro in casi di 
        # scarsa qualità ottica), passando poi alla libreria di detection sui pixel
        # per limitare le inferenze pesanti. Se il binario restituisce vuoto,
        # fallback calcolato e deterministico verso l'engine semantico.
        barcode_pulito = "".join(filter(str.isdigit, barcode_manuale or ""))
        if 8 <= len(barcode_pulito) <= 14:
            barcode = barcode_pulito
        else:
            barcode = scan_barcode(tmp_path)

        fonte = "stima"
        testo_analisi = None

        if barcode:
            # Il flusso prosegue a monte in Python nativo garantendo tempi costanti
            # e proteggendoci dalle approssimazioni tipiche del modello.
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
            # In caso di esito nullo, degradazione dolce verso la pipeline visuale

        if testo_analisi is None:
            # Attivazione engine visivo
            # Disaccoppiamo le capability omettendo il function calling, garantendo
            # che il sub-agente lavori esclusivamente sull'interpretazione visiva
            # senza incorrere in iterazioni API indesiderate.
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

        # Serializzazione della risposta
        # Deleghiamo a un worker separato il mapping dal discorso naturale
        # alla struttura JSON stretta validata contro il nostro schema Pydantic.
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
            # Pulizia regressiva per scartare prefissi o markdown spurio
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
def get_sessions(chat_type: Optional[str] = None, current_user: int = Depends(get_current_user)):
    try:
        convs = get_user_conversations(current_user, chat_type)
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

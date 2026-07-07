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
from agno.run.team import RunContentEvent, RunErrorEvent
from agno.models.message import Image as AgnoImage
from agno.agent import Agent
from agno.models.groq import Groq as GroqModel
from src.agents.nutritionst import NutritionistAgent, VisionNutritionistAgent, MealAnalysis
from src.tools.openfoodfacts_tool import get_product_info_by_barcode
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
from src.orchestrator import get_orchestrator, build_user_context
from src.agents.fitness_agent import get_pt_agent
from src.database.knowledge_base import build_knowledge
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


# Lista di affermazioni che valgono come conferma esplicita di salvataggio (Fase 2).
_SAVE_AFFERM = ("si", "sì", "ok", "okay", "va bene", "perfetto", "salva", "salvala",
                "certo", "confermo", "d'accordo", "daccordo", "procedi", "vai",
                "memorizza", "yes", "sisi")


def _is_save_confirmation(user_message: str, prev_assistant: str) -> bool:
    """
    Rileva se l'utente ha confermato il salvataggio di una scheda proposta nel turno precedente.

    🔴 Il frontend antepone SEMPRE il prefisso di routing 'Al Coach: ' a ogni messaggio: va
    rimosso PRIMA del confronto, altrimenti l'affermazione non matcha mai (es. 'Al Coach: salvala'
    diventa 'al coach salvala') e il salvataggio deterministico non parte, lasciando il modello
    debole a rigenerare la scheda in loop.

    Author: Stefano Bellan (20054330)
    """
    msg = re.sub(r'^\s*al(?:la)?\s+coach\s*:?\s*', '', user_message.strip(), flags=re.IGNORECASE)
    um = re.sub(r'[^\w\s]', '', msg.lower()).strip()
    is_afferm = any(um == a or um.startswith(a + " ") for a in _SAVE_AFFERM)
    is_proposal = any(k in prev_assistant.lower() for k in ["salv", "profil", "memorizz", "scheda", "vuoi"])
    return is_afferm and is_proposal


# Parole che segnalano la MODIFICA di una scheda esistente (non una creazione).
_MODIFY_KW = ("modific", "sovrascriv", "aggiorn", "cambia", "sostituis", "rendila", "rendi")


def _looks_like_modification(history: list) -> bool:
    """
    Rileva se la richiesta confermata riguarda la MODIFICA di una scheda esistente.

    Serve a disambiguare in Fase 2 quale tool forzare: il modello debole, davanti a una
    'scheda singola', tende a scegliere `create_workout_plan_tool` (che ha il guard sul
    numero minimo di esercizi e può rifiutare la modifica di un giorno piccolo) invece di
    `modify_workout_plan_tool`. Guardiamo l'ultima richiesta utente PRIMA della conferma.

    Author: Timothy Giolito (20054431)
    """
    user_msgs = [m["content"] for m in history if m["role"] == "user"]
    # L'ultimo messaggio utente è la conferma ('sì/salva'): quello che conta è il precedente.
    candidati = user_msgs[:-1] if len(user_msgs) > 1 else user_msgs
    for msg in reversed(candidati):
        low = re.sub(r'^\s*al(?:la)?\s+coach\s*:?\s*', '', msg.lower(), flags=re.IGNORECASE)
        return any(k in low for k in _MODIFY_KW)
    return False


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
        # Fase 1 (proposta): il Coach NON deve poter scrivere sul DB. L'human-in-the-loop
        # è imposto STRUTTURALMENTE disabilitando i suoi tool di scrittura, invece di
        # fidarci del solo prompt (che il modello debole ignorava: chiamava il tool in
        # Fase 1 saltando la conferma e sputando il blocco json nella chat). Il salvataggio
        # reale avviene solo in Fase 2, con un agente tools-enabled ricostruito su richiesta.
        is_coach = request.chat_type == "coach"
        team_agent = get_orchestrator(user_data, macros_odierni, daily_targets, breakdown_odierno, history, request.chat_type, enable_tools=not is_coach)
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Errore nell'elaborazione del messaggio: {str(e)}")

    # Fotografiamo programmaticamente il cluster fitness prima dell'esecuzione
    # per avere un pivot di confronto post-run. Selezioniamo questa via solo
    # per l'agente Coach, essendo l'unico autorizzato ad alterare le schede.
    snapshot_prima = _workout_snapshot(user_id) if is_coach else None

    # Rilevazione Fase 2 (conferma di salvataggio) PRIMA della run: l'utente ha detto
    # "sì/ok/salva" a una proposta di salvataggio del turno precedente. Serve a bypassare
    # la ri-generazione verbosa della scheda da parte del modello debole (che ignora il
    # divieto testuale) e a forzare il solo salvataggio con conferma secca.
    # ponytail: euristica su lista di affermazioni; se serve più copertura, ampliare _afferm.
    fase2_conferma = False
    if is_coach:
        # Author: Stefano Bellan (20054330)
        _prev_assist = next((m["content"] for m in reversed(history) if m["role"] == "assistant"), "")
        fase2_conferma = _is_save_confirmation(request.message, _prev_assist)

    # Prompt di salvataggio forzato: recupera dalla cronologia le schede proposte in Fase 1
    # e chiama davvero il tool corretto, rispondendo solo con la conferma esatta.
    # Distinguiamo MODIFICA da CREAZIONE: nel caso di modifica imponiamo un SINGOLO tool
    # (`modify_workout_plan_tool`), altrimenti il modello debole ripiega su create_* e il
    # guard sul minimo esercizi può bloccare la modifica di un giorno piccolo.
    # Author: Stefano Bellan (20054330)
    is_modifica = is_coach and _looks_like_modification(history)
    if is_modifica:
        recovery_prompt = (
            "MESSAGGIO AUTOMATICO DI SISTEMA (l'utente NON vede questo messaggio, non rispondergli): "
            "l'utente ha CONFERMATO la MODIFICA di una scheda ESISTENTE che gli hai proposto nel turno precedente, "
            "ma nel database NON risulta ancora aggiornata. Chiama ADESSO ESCLUSIVAMENTE lo strumento `modify_workout_plan_tool`, "
            "passando come `plan_name` il NOME ESATTO della scheda esistente da modificare e come `exercises` la lista COMPLETA "
            "e aggiornata degli esercizi proposti (recuperandoli dalla cronologia). NON usare create_workout_plan_tool né "
            "create_weekly_workout_plan_tool. NON riscrivere la scheda in testo: chiama solo il tool. "
            "Rispondi ESCLUSIVAMENTE con la frase esatta: '✅ Scheda salvata nel profilo.' senza aggiungere altro."
        )
    else:
        recovery_prompt = (
            "MESSAGGIO AUTOMATICO DI SISTEMA (l'utente NON vede questo messaggio, non rispondergli): "
            "l'utente ha CONFERMATO il salvataggio della/e scheda/e che gli hai proposto nel turno precedente, "
            "ma nel database NON risulta alcuna modifica: non hai chiamato lo strumento. "
            "Recupera i dati di TUTTE le schede/giorni proposti nel turno precedente (nella cronologia) e chiama ADESSO lo strumento: "
            "`create_weekly_workout_plan_tool` per un piano su più giorni, `create_workout_plan_tool` per una scheda singola. "
            "NON riscrivere la scheda in testo: chiama solo il tool. "
            "Rispondi ESCLUSIVAMENTE con la frase esatta: '✅ Scheda salvata nel profilo.' senza aggiungere altro."
        )

    def _save_via_tools() -> bool:
        """
        Esegue il salvataggio forzato eseguendo DIRETTAMENTE l'agente Coach (che possiede
        i tool), NON l'orchestratore Team. In route-mode il leader tentava di chiamare il
        tool del membro senza averlo in request.tools (400 tool_use_failed) e, privo dello
        schema, ne inventava i parametri (`workout_plan`/`day` invece di `plans`/`name`).
        Girando il membro diretto il tool è in request.tools e il modello riceve lo schema
        corretto. La run di Fase 1 gira coi tool disattivati (human-in-the-loop): il commit
        reale sul DB passa ESCLUSIVAMENTE da qui, solo su conferma esplicita.

        Il modello debole a volte, invece di chiamare il tool, emette solo la frase di
        conferma (action hallucination): verifichiamo lo snapshot e RITENTIAMO fino a 3
        volte finché il DB cambia davvero. Ritorna True se la scrittura è avvenuta.
        ponytail: retry a tetto fisso (3); se anche così fallisce spesso, il collo di
        bottiglia è il modello, non il numero di tentativi.
        """
        ctx = build_user_context(user_data, macros_odierni, daily_targets, breakdown_odierno, history, request.chat_type)
        coach = get_pt_agent(ctx, build_knowledge(domain="fitness"), user_data, enable_tools=True)
        for tentativo in range(1, 4):
            coach.run(recovery_prompt, stream=False)
            if _workout_snapshot(user_id) != snapshot_prima:
                return True
            print(f"[chat_api] salvataggio Fase 2: tentativo {tentativo}/3 senza scrittura, ritento")
        return False

    def event_stream():
        try:
            yield _sse({"type": "start", "conversation_id": conv_id})

            # FASE 2 DETERMINISTICA: l'utente ha confermato. Non lasciamo ri-scrivere l'intera
            # scheda al modello (che altrimenti ridumpa tutto il piano): eseguiamo il solo
            # salvataggio in background ed emettiamo esclusivamente la conferma secca.
            if is_coach and fase2_conferma:
                _save_via_tools()
                updated = _workout_snapshot(user_id) != snapshot_prima
                # Author: Stefano Bellan (20054330)
                ai_text = "✅ Scheda salvata nel profilo." if updated else "Non sono riuscito a salvare la scheda. Riprova a chiedermela."
                yield _sse({"type": "content", "delta": ai_text})
                save_message(conv_id, "assistant", ai_text)
                yield _sse({"type": "end", "workouts_updated": updated})
                return

            # Intercettiamo progressivamente i token scaricati dall'engine LLM
            # incapsulandoli in frame SSE per abbattere il time-to-first-byte percepito.
            chunks = []
            run_error = None
            for event in team_agent.run(request.message, stream=True):
                if isinstance(event, RunContentEvent) and isinstance(event.content, str) and event.content:
                    chunks.append(event.content)
                    yield _sse({"type": "content", "delta": event.content})
                elif isinstance(event, RunErrorEvent):
                    # Il modello/provider ha fallito (es. rate limit Groq 429): l'evento di
                    # errore NON è un RunContentEvent, quindi senza questo ramo lo streaming
                    # resta vuoto e l'utente vede solo un generico "non ho ricevuto risposta".
                    run_error = str(getattr(event, "content", "") or "Errore sconosciuto")

            ai_text = "".join(chunks).strip()

            # Nessun testo generato ma errore del provider: mostra un messaggio utile e chiudi.
            if not ai_text and run_error:
                _low = run_error.lower()
                if "rate_limit" in _low or "429" in _low or "tokens per day" in _low:
                    friendly = "⚠️ Ho esaurito il numero di richieste disponibili per ora. Riprova tra qualche minuto."
                else:
                    friendly = "⚠️ Si è verificato un errore momentaneo del servizio. Riprova tra poco."
                yield _sse({"type": "content", "delta": friendly})
                save_message(conv_id, "assistant", friendly)
                yield _sse({"type": "end", "workouts_updated": False})
                return

            ai_text = ai_text or "Mi dispiace, non ho ricevuto una risposta."

            # In Fase 1 il Coach gira SENZA tool di scrittura: la run di streaming non può
            # mutare il DB, quindi lo stato delle schede resta invariato. Il salvataggio
            # avviene solo in Fase 2 (conferma esplicita, ramo sopra). Rimosso il vecchio
            # fallback "anti-allucinazione" che forzava il salvataggio quando il testo
            # sembrava dichiararlo: ora rischierebbe solo di scrivere una scheda NON
            # confermata dall'utente, violando l'human-in-the-loop.
            workouts_updated = False

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
            prod = get_product_info_by_barcode(barcode=barcode)
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


if __name__ == "__main__":
    # Self-check detection Fase 2: il prefisso di routing NON deve rompere il match.
    _prop = "Ecco la scheda. Vuoi che la salvi nel tuo profilo?"
    assert _is_save_confirmation("Al Coach: salvala", _prop)
    assert _is_save_confirmation("Al Coach: sì", _prop)
    assert _is_save_confirmation("sì, salvala", _prop)
    assert _is_save_confirmation("Al Coach: ok", _prop)
    assert not _is_save_confirmation("Al Coach: cambia il primo esercizio", _prop)
    assert not _is_save_confirmation("Al Coach: salvala", "Ciao, come posso aiutarti?")
    print("OK _is_save_confirmation")

    # Self-check rilevamento modifica: guarda la richiesta PRIMA della conferma.
    _hist_mod = [
        {"role": "user", "content": "Al Coach: Modifichiamo la scheda Venerdì aumentando la difficoltà"},
        {"role": "assistant", "content": "Ecco la scheda modificata. Vuoi che la salvi?"},
        {"role": "user", "content": "Al Coach: Sì sovrascrivila"},
    ]
    _hist_new = [
        {"role": "user", "content": "Al Coach: Creami una scheda per il petto"},
        {"role": "assistant", "content": "Ecco la scheda. Vuoi che la salvi?"},
        {"role": "user", "content": "Al Coach: Sì salva"},
    ]
    assert _looks_like_modification(_hist_mod)
    assert not _looks_like_modification(_hist_new)
    print("OK _looks_like_modification")

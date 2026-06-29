"""
Modulo Orchestratore centrale di RepEats.
Gestisce il routing intelligente delle richieste utente verso l'agente corretto
(Personal Trainer o Nutrizionista) tramite l'architettura multi-agente di Agno.

Questo modulo è stato estratto da fitness_agent.py per separare le responsabilità:
- L'orchestratore si occupa di contesto condiviso, knowledge base e routing.
- Ogni agente (fitness, nutritionist) resta indipendente e focalizzato sul proprio dominio.

Autore: Stefano Bellan (20054330)
"""

import os
from datetime import datetime

from agno.models.groq import Groq
from agno.team import Team
from agno.team.mode import TeamMode

# Importazione dei componenti nativi di Agno per la gestione dell'architettura RAG
from agno.knowledge.knowledge import Knowledge
from agno.vectordb.lancedb import LanceDb
from agno.knowledge.embedder.sentence_transformer import SentenceTransformerEmbedder

# Importazione degli agenti specializzati
from src.agents.fitness_agent import get_pt_agent
from src.agents.nutritionst import ConversationalNutritionistAgent


def setup_knowledge_base() -> Knowledge:
    """
    Configura e inizializza la Knowledge Base per il sistema RAG.
    La funzione si appoggia a LanceDB per l'archiviazione vettoriale locale 
    e a un modello all-MiniLM leggero per calcolare embedding semantici.
    """
    base_dir = os.path.dirname(os.path.abspath(__file__))
    kb_dir = os.path.join(base_dir, "knowledge_base")
    db_dir = os.path.join(base_dir, "database", "lancedb_vectors")

    #Controllo che la cartella per il database esista, prevenendo errori a runtime
    os.makedirs(db_dir, exist_ok=True)

    #Inizializzazione dell'oggetto KnowledgeBase nativo di agno
    knowledge_base = Knowledge(
        vector_db=LanceDb(
            table_name="protocolli_allenamento",
            uri=db_dir,
            embedder=SentenceTransformerEmbedder(id="sentence-transformers/all-MiniLM-L6-v2")
        )
    )

    lancedb_table_path = os.path.join(db_dir, "protocolli_allenamento.lance")
    if not os.path.exists(lancedb_table_path):
        print("⚙️ Primo avvio rilevato: Vettorializzazione dei documenti in corso...")
        knowledge_base.insert(path=kb_dir)
    
    return knowledge_base


def build_user_context(user_data: dict, macros: dict, daily_targets: dict, chat_history: list, chat_type: str = "coach") -> str:
    """
    Costruisce il contesto condiviso (Memoria Condivisa) che sarà accessibile
    sia all'Orchestratore che agli Agenti specializzati.
    
    Args:
        user_data: Dati biometrici dell'utente (età, peso, obiettivo).
        macros: Macro assunti oggi (calorie, proteine, carboidrati, grassi).
        daily_targets: Obiettivi giornalieri calcolati.
        chat_history: Cronologia messaggi della conversazione corrente.
        chat_type: Tipo di chat attiva ("coach" o "nutritionist").
    
    Returns:
        Stringa formattata con il contesto utente completo.
    """
    target_cal = daily_targets.get('target_calories', 0)
    now = datetime.now()
    ora_attuale = now.strftime("%d/%m/%Y %H:%M")
    current_hour = now.hour

    # Calcolo della percentuale di calorie assunte rispetto al target
    cal_consumed = macros.get('calories', 0)
    cal_progress_pct = round((cal_consumed / target_cal * 100), 1) if target_cal > 0 else 0

    # Fascia oraria e range di intake atteso (percentuale del fabbisogno giornaliero)
    if current_hour < 12:
        fascia_oraria = "Mattina (06:00-12:00)"
        expected_range = "25-35%"
    elif current_hour < 15:
        fascia_oraria = "Primo pomeriggio (12:00-15:00)"
        expected_range = "50-65%"
    elif current_hour < 18:
        fascia_oraria = "Tardo pomeriggio (15:00-18:00)"
        expected_range = "60-75%"
    else:
        fascia_oraria = "Sera (18:00-22:00)"
        expected_range = "80-100%"

    # Ricostruzione della memoria della chat per fornire contesto condiviso all'Orchestratore e agli Agenti
    storia_testo = "Nessun messaggio precedente."
    if chat_history:
        storia_testo = "\n".join([f"{msg['role'].upper()}: {msg['content']}" for msg in chat_history])

    user_context = f"""
--- CONTESTO UTENTE (MEMORIA CONDIVISA) ---
DATI BIOMETRICI:
- Età: {user_data.get('age')} anni
- Peso: {user_data.get('weight')} kg
- Obiettivo: {user_data.get('goal_type')}
- Tempo a disposizione per allenamento: {user_data.get('workout_duration', 60)} minuti
- Tipo di allenamento preferito: {user_data.get('workout_preference', 'Ipertrofia')}

NUTRIZIONE ODIERNA:
- Calorie assunte: {macros['calories']} / {target_cal} kcal ({cal_progress_pct}% del fabbisogno)
- Proteine: {macros['proteins']}g
- Carboidrati: {macros['carbohydrates']}g
- Grassi: {macros['fats']}g

ANALISI TEMPORALE INTAKE CALORICO:
- Fascia oraria corrente: {fascia_oraria}
- Range di intake atteso per questa fascia: {expected_range} del fabbisogno giornaliero
- Intake attuale: {cal_progress_pct}%
- NOTA: È NORMALE non aver raggiunto il 100% del fabbisogno se non è ancora sera. Valuta l'intake rispetto al range atteso, NON rispetto al totale giornaliero.

DATA E ORA CORRENTE: {ora_attuale}

PAGINA CORRENTE DELL'UTENTE: {chat_type.upper()}

CRONOLOGIA CONVERSAZIONE:
{storia_testo}
--- FINE CONTESTO ---
"""
    return user_context


def get_orchestrator(user_data: dict, macros: dict, daily_targets: dict, chat_history: list, chat_type: str = "coach"):
    """
    Crea e restituisce l'Orchestratore centrale di RepEats.
    
    L'orchestratore è un Team Agno in modalità 'route' che:
    1. Riceve la richiesta dell'utente.
    2. In base al contesto (pagina corrente), instrada al membro corretto.
    3. Restituisce la risposta dell'agente specializzato senza modificarla.
    
    La selezione dei membri è STRUTTURALE: solo l'agente corretto è inserito nel team,
    rendendo impossibile un routing errato da parte dell'LLM.
    
    Args:
        user_data: Dati biometrici dell'utente.
        macros: Macro assunti oggi.
        daily_targets: Obiettivi giornalieri calcolati.
        chat_history: Cronologia messaggi della conversazione corrente.
        chat_type: Tipo di chat attiva ("coach" o "nutritionist").
    
    Returns:
        Team: L'orchestratore configurato pronto per ricevere messaggi.
    """
    # Setup della knowledge base per il fitness agent
    kb = setup_knowledge_base()

    # Costruzione del contesto condiviso
    user_context = build_user_context(user_data, macros, daily_targets, chat_history, chat_type)

    # Creazione degli agenti specializzati con il contesto iniettato
    pt_agent = get_pt_agent(user_context=user_context, knowledge_base=kb, user_data=user_data)
    nutrizionista_chat = ConversationalNutritionistAgent(user_context=user_context)

    # Selezione dei membri in base alla pagina corrente dell'utente.
    # Questa è una scelta STRUTTURALE: evitiamo di affidarci alle istruzioni dell'orchestratore
    # per il routing, perché il LLM potrebbe ignorarle. Invece, rendiamo IMPOSSIBILE
    # instradare all'agente sbagliato, inserendo nel team solo l'agente corretto.
    if chat_type == "coach":
        active_members = [pt_agent]
        routing_description = "Team con solo il Personal Trainer attivo (pagina Coach)."
    elif chat_type == "nutritionist":
        active_members = [nutrizionista_chat]
        routing_description = "Team con solo il Nutrizionista attivo (pagina Nutrition)."
    else:
        # Fallback: entrambi gli agenti disponibili
        active_members = [pt_agent, nutrizionista_chat]
        routing_description = "Orchestratore Multi-Agente con Memoria Condivisa tra Fitness e Nutrizione."

    # Istruzioni dell'Orchestratore centrale
    instructions = [
        user_context,
        
        "# RUOLO",
        "Sei l'Orchestratore intelligente di RepEats. Il tuo compito è instradare la richiesta dell'utente al membro del team disponibile.",
        
        "# REGOLE",
        "- Instrada SEMPRE al membro del team disponibile.",
        "- NON modificare, riassumere o commentare le risposte dei tuoi membri. Restituisci la risposta del membro esattamente come la ricevi.",
        "- NON rispondere tu direttamente alle domande.",
    ]

    # Orchestratore centrale con mode=route
    return Team(
        name="repeats_team",
        mode=TeamMode.route,
        model=Groq(id="meta-llama/llama-4-scout-17b-16e-instruct"),
        members=active_members,
        instructions=instructions,
        markdown=True,
        description=routing_description,
        show_members_responses=True,
    )

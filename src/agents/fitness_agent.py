import os
from agno.agent import Agent
from agno.models.groq import Groq

def get_fitness_knowledge():
    """
    Funzione RAG: Legge le linee guida dal file di testo locale.
    """
    file_path = "knowledge_base/linee_guida_allenamento.txt"
    try:
        if os.path.exists(file_path):
            with open(file_path, "r", encoding="utf-8") as f:
                return f.read()
        return "Nessuna linea guida specifica trovata nella base di conoscenza."
    except Exception as e:
        return f"Errore nel caricamento della knowledge base: {e}"

def get_fitness_agent(user_data: dict, macros: dict, daily_targets: dict):
    """
    Configurazione dell'agente con contesto Multi-Agente e RAG.
    """
    # Recupero le linee guida dal file (RAG)
    knowledge = get_fitness_knowledge()
    
    # Calcolo del target calorico per il prompt
    target_cal = daily_targets.get('target_calories', 0)
    
    # Costruzione del contesto biometrico e NUTRIZIONALE (Multi-Agent)
    user_context = f"""
    DATI BIOMETRICI UTENTE:
    - Età: {user_data.get('age')} anni | Peso: {user_data.get('weight')} kg
    - Obiettivo: {user_data.get('goal_type')}
    
    SITUAZIONE NUTRIZIONALE DI OGGI:
    - Calorie assunte: {macros['calories']} kcal (Target giornaliero: {target_cal} kcal)
    - Proteine assunte: {macros['proteins']}g
    """

    instructions = [
        user_context,
        "--- KNOWLEDGE BASE (PROTOCOLLI DA SEGUIRE) ---",
        knowledge,
        "--- MISSIONE ---",
        "Sei il Senior Personal Trainer di RepEats. Fornisci schede e consigli basati sui dati sopra.",
        
        "--- REGOLE D'ORO ---",
        "1. SICUREZZA CALORICA: Se l'utente ha mangiato pochissimo (sotto le 1000 kcal o meno del 40% del target), "
        "NON suggerire pesi pesanti. Proponi stretching o riposo spiegando il rischio di cali di energia.",
        
        "2. VINCOLO RAG: Usa ESCLUSIVAMENTE i protocolli (serie/ripetizioni) descritti nella KNOWLEDGE BASE sopra.",
        
        "3. TONE: Sii motivante ma metti sempre la salute al primo posto. Usa il 'tu'.",
        "4. FORMATTAZIONE: Usa il Markdown con grassetti e liste puntate."
    ]

    return Agent(
        model=Groq(id="llama-3.3-70b-versatile"),
        instructions=instructions,
        markdown=True,
        description="Agente Fitness esperto con integrazione RAG e Nutrizionale."
    )
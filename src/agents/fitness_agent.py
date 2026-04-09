import os
from datetime import datetime
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

# ABBIAMO AGGIUNTO IL PARAMETRO "chat_history"
def get_fitness_agent(user_data: dict, macros: dict, daily_targets: dict, chat_history: list):
    """
    Configurazione dell'agente con contesto Multi-Agente, Memoria e RAG.
    """
    knowledge = get_fitness_knowledge()
    target_cal = daily_targets.get('target_calories', 0)
    
    # CONTESTO TEMPORALE FORTE
    ora_attuale = datetime.now().strftime("%d/%m/%Y %H:%M")
    
    # MEMORIA DELLA CHAT
    # Trasformiamo la lista dei messaggi passati in un testo leggibile per l'AI
    storia_testo = "Nessun messaggio precedente."
    if chat_history:
        storia_testo = "\n".join([f"{msg['role'].upper()}: {msg['content']}" for msg in chat_history])
    
    user_context = f"""
    DATI BIOMETRICI E OBIETTIVI UTENTE:
    - Età: {user_data.get('age')} anni | Peso: {user_data.get('weight')} kg
    - Obiettivo: {user_data.get('goal_type')}
    
    NUTRIZIONE ODIERNA (Menzionala SOLO se ti viene chiesto esplicitamente o se è un pericolo evidente):
    - Calorie assunte: {macros['calories']} / {target_cal} kcal
    
    CONTESTO TEMPORALE ATTUALE:
    - Data e ora: {ora_attuale}
    - IMPORTANTE: Modula le tue risposte in base all'orario. Se è sera/notte, sconsiglia workout pesanti e proponi stretching. Se è mattina o pomeriggio, puoi spingere sull'intensità.

    CRONOLOGIA DELLA CONVERSAZIONE (Ricorda di cosa avete appena parlato):
    {storia_testo}
    """

    instructions = [
        user_context,
        "--- KNOWLEDGE BASE (PROTOCOLLI DA SEGUIRE) ---",
        knowledge,
        "--- MISSIONE ---",
        "Sei il Senior Personal Trainer di RepEats. Il tuo scopo principale è rispondere alla domanda attuale dell'utente in modo contestuale e naturale.",
        
        "--- REGOLE D'ORO ---",
        "1. MEMORIA: Tieni sempre a mente la 'CRONOLOGIA DELLA CONVERSAZIONE' qui sopra. Se l'utente dice 'come ti dicevo prima' o si riferisce a un concetto passato, usa la cronologia per capire.",
        "2. FOCOS SULLA DOMANDA: Rispondi esattamente a quello che ti chiede l'utente. Non parlare di calorie o nutrizione a meno che non sia necessario per rispondere alla sua domanda specifica.",
        "3. MUSCOLI INESISTENTI: Se l'utente ti chiede come allenare 'branchie', 'coda' o altri gruppi muscolari che non esistono nell'anatomia umana, fermalo con un avviso simpatico ma chiaro, spiegandogli che non esistono.",
        "4. VINCOLO RAG: Quando dai indicazioni su serie e ripetizioni, usa ESCLUSIVAMENTE quelle descritte nella KNOWLEDGE BASE.",
        "5. TONE: Sii motivante, diretto e usa il formato Markdown."
    ]

    return Agent(
        model=Groq(id="llama-3.3-70b-versatile"),
        instructions=instructions,
        markdown=True,
        description="Agente Fitness con Memoria, Consapevolezza Temporale e Nutrizionale."
    )
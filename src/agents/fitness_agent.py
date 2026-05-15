import os
from datetime import datetime
from agno.agent import Agent
from agno.models.groq import Groq

# Importazione dei componenti nativi di Agno per la gestione dell'architettura RAG
from agno.knowledge.knowledge import Knowledge
from agno.vectordb.lancedb import LanceDb
from agno.knowledge.embedder.sentence_transformer import SentenceTransformerEmbedder

# Importiamo l'agente nutrizionista. Fai attenzione alla corretta importazione della classe.
from src.agents.nutritionst import NutritionistAgent

def setup_knowledge_base() -> Knowledge:
    """
    Configura e inizializza la Knowledge Base per il sistema RAG.
    La funzione si appoggia a LanceDB per l'archiviazione vettoriale locale
    e a un modello all-MiniLM leggero per calcolare gli embedding semantici.
    """
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    kb_dir = os.path.join(base_dir, "knowledge_base")
    db_dir = os.path.join(base_dir, "database", "lancedb_vectors")
    
    # controllo che la cartella per il database esista, prevenendo errori a runtime
    os.makedirs(db_dir, exist_ok=True)

    # Inizializzazione dell'oggetto KnowledgeBase nativo di Agno
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

# Created by Stefano Bellan 20054330 - Implementazione orchestrazione multi agente
def ask_nutritionist(query: str) -> str:
    """
    Interroga l'agente Nutrizionista per ottenere consigli alimentari specifici.
    Utilizza questo strumento quando l'utente fa domande su cosa mangiare, 
    prima o dopo l'allenamento, o per dubbi nutrizionali.
    
    Args:
        query (str): La domanda specifica sull'alimentazione formulata dall'utente.
        
    Returns:
        str: Il parere esperto del nutrizionista.
    """
    # Istanziamo correttamente la classe importata
    nutrizionista = NutritionistAgent()

    # Sovrascrittura delle istruzioni per evitare la risposta con un json strutturato
    nutrizionista.instructions = [
        "Sei il Nutrizionista esperto di RepEats.",
        "Il Personal Trainer ti sta chiedendo un parere per un utente.",
        "Rispondi alla domanda in modo chiaro, professionale e discorsivo.",
        "Fornisci indicazioni utili e pratiche basate sui macros e obiettivi.",
        "ASSOLUTAMENTE NON usare il formato JSON, rispondi solo con testo normale."
    ]

    risposta = nutrizionista.run(query)
    return str(risposta.content)

# ABBIAMO AGGIUNTO IL PARAMETRO "chat_history"
# Modified by Stefano Bellan 20054330 - Aggiunta registrazione tool ask_nutritionist e connessione alla TextKnowledgeBase
def get_fitness_agent(user_data: dict, macros: dict, daily_targets: dict, chat_history: list):
    """
    Configurazione dell'agente con contesto Multi-Agente, Memoria e integrazione nativa VERO RAG.
    """
    kb = setup_knowledge_base()
    
    target_cal = daily_targets.get('target_calories', 0)
    
    # CONTESTO TEMPORALE FORTE
    ora_attuale = datetime.now().strftime("%d/%m/%Y %H:%M")

    # MEMORIA DELLA CHAT
    # Trasformazione della lista dei messaggi passati in un testo leggibile per l'AI
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
        "--- MISSIONE ---",
        "Sei il Senior Personal Trainer di RepEats. Il tuo scopo principale è rispondere alla domanda attuale dell'utente in modo contestuale e naturale.",
        
        "--- REGOLE D'ORO ---",
        "1. MEMORIA: Tieni sempre a mente la 'CRONOLOGIA DELLA CONVERSAZIONE' qui sopra. Se l'utente dice 'come ti dicevo prima' o si riferisce a un concetto passato, usa la cronologia per capire.",
        "2. FOCUS SULLA DOMANDA: Rispondi esattamente a quello che ti chiede l'utente. Non parlare di calorie o nutrizione a meno che non sia necessario per rispondere alla sua domanda specifica.",
        "3. MUSCOLI INESISTENTI: Se l'utente ti chiede come allenare 'branchie', 'coda' o altri gruppi muscolari che non esistono nell'anatomia umana, fermalo con un avviso simpatico ma chiaro, spiegandogli che non esistono.",
        "4. VINCOLO RAG: Quando ti viene chiesto dei protocolli di allenamento o delle linee guida, DEVI utilizzare attivamente gli strumenti di ricerca nella Knowledge Base. Basa i tuoi consigli ESCLUSIVAMENTE sui frammenti di testo restituiti dal database vettoriale.",
        "5. TONE: Sii motivante, diretto e usa il formato Markdown.",
        "6. ORCHESTRAZIONE MULTI-AGENTE: Se l'utente ti chiede consigli specifici su cosa mangiare, non inventare la risposta ma chiama il tool 'ask_nutritionist' e riporta all'utente il suo parere da esperto."
    ]

    return Agent(
        model=Groq(id="llama-3.3-70b-versatile"),
        instructions=instructions,
        knowledge=kb,               # Oggetto base di conoscenza configurato in precedenza
        search_knowledge=True,      # Forzo Agno a dotare l'LLM degli strumenti di query vettoriale
        tools=[ask_nutritionist],
        markdown=True,
        description="Agente Fitness con Memoria, Consapevolezza Temporale e Integrazione RAG su database vettoriale."
    )
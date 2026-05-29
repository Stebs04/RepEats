import os
from datetime import datetime
from agno.agent import Agent
from agno.models.groq import Groq

from agno.team import Team

# Importazione dei componenti nativi di Agno per la gestione dell'architettura RAG
from agno.knowledge.knowledge import Knowledge
from agno.vectordb.lancedb import LanceDb
from agno.knowledge.embedder.sentence_transformer import SentenceTransformerEmbedder

# Importiamo l'agente nutrizionista.
from src.agents.nutritionst import NutritionistAgent

def setup_knowledge_base() -> Knowledge:
    """
    Configura e inizializza la Knowledge Base per il sistema RAG.
    La funzione si appoggia a LanceDB pper l'archiviazione vettoriale locale 
    e a un modello all-MiniLM leggero per calcolare embedding semantici
    """
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
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

# Created by Timothy Giolito
# Modified by Stefano Bellan 20054330 - Implementazione orchestrazione multi agente
def get_fitness_agent(user_data: dict, macros: dict, daily_targets: dict, chat_history: list):
    """
    Configurazione dell'agente con contesto Multi-Agente, Memoria e integrazione nativa VERO RAG.
    """
    kb = setup_knowledge_base()

    target_cal = daily_targets.get('target_calories', 0)

    #Costruzione del contesto temporale
    ora_attuale = datetime.now().strftime("%d/%m/%Y %H:%M")

    #Ricostruzione della memoria della chat per fornire contesto all'LLM
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

    # Isolamento delle logiche di dominio istanziando i due agenti specializzati.
    # Assegnazione dell'istanza RAG esclusivamente al modulo fitness. In questo modo evitiamo 
    # che la vector search venga inquinata da query non pertinenti come quelle alimentari.
    pt_agent = Agent(
        name="PersonalTrainer",
        role="Specialista in protocolli di allenamento e ipertrofia",
        model=Groq(id="llama-3.3-70b-versatile"),
        knowledge=kb,
        search_knowledge=True,
        instructions=[
            "Sei il Personal Trainer di RepEats.",
            "Usa SEMPRE la knowledge base per fornire linee guida e protocolli di allenamento.",
            "Non inventare esercizi fuori dai protocolli, affidati ai documenti vettorializzati."
        ]
    )

    # Adattamento dell'agente nutrizionista già esistente per lavorare in un contesto conversazionale di team
    nutrizionista = NutritionistAgent()
    nutrizionista.name = "Nutrizionista"
    nutrizionista.role = "Specialista in nutrizione e macro"
    nutrizionista.instructions.extend([
        "Stai operando in una chat come consulente.",
        "Rispondi in modo discorsivo e professionale.",
        "ASSOLUTAMENTE NON usare il formato JSON, restituisci solo testo normale in Markdown."
    ])
    
    # Rimozione della regola restrittiva sui tag XML per permettere al motore di Agno di elaborare la richiesta nativa
    instructions = [
        user_context,
        "--- MISSIONE ---",
        "Sei l'Orchestratore principale di RepEats. Interagisci con l'utente, capisci il suo intento e coordini il team delegando i task.",
        
        "--- REGOLE D'ORO ---",
        "1. MEMORIA: Tieni sempre a mente la 'CRONOLOGIA DELLA CONVERSAZIONE' qui sopra.",
        "2. DELEGA MULTI-AGENTE: Se l'utente chiede un protocollo o consigli di allenamento, DELEGA la richiesta al 'PersonalTrainer'. Se chiede pareri su cibo, dieta o integratori, DELEGA al 'Nutrizionista'.",
        "3. MUSCOLI INESISTENTI: Se l'utente ti chiede come allenare 'branchie', 'coda' o altri gruppi muscolari che non esistono nell'anatomia umana, fermalo con un avviso simpatico ma chiaro, spiegandogli che non esistono.",
        "4. SINTESI: Raccogli le risposte dei tuoi sub-agenti e offri una risposta finale unica, coesa e naturale all'utente.",
        "5. TONE: Sii motivante, diretto e usa il formato Markdown."
    ]

     # Implementazione nativa del pattern Orchestrator sfruttando il parametro members del framework.
    # L'engine LLM gestirà autonomamente il routing verso i sub-agenti registrati.
    return Team(
        model=Groq(id="llama-3.3-70b-versatile"),
        members=[pt_agent, nutrizionista],
        instructions=instructions,
        markdown=True,
        description="Agente Orchestratore con Memoria, Consapevolezza Temporale e Delega Multi-Agente."
    )
        
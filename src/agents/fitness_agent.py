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
    
    # Ristrutturiamo il prompt del Personal Trainer per renderlo un estrattore rigido.
    # e blocchiamo la creatività del modello costringendolo a usare i dati caricati.
    pt_agent = Agent(
        name="PersonalTrainer",
        role="Specialista in protocolli di allenamento e ipertrofia",
        model=Groq(id="meta-llama/llama-4-scout-17b-16e-instruct"),
        knowledge=kb,
        search_knowledge=True,
        instructions=[
            "Sei il Personal Trainer di RepEats.",
            "REGOLA CRITICA E ASSOLUTA: Per rispondere a qualsiasi domanda su protocolli, serie, ripetizioni o tempi di recupero, DEVI obbligatoriamente cercare nella tua knowledge base prima di formulare la risposta.",
            "NON usare la tua conoscenza pregressa per i protocolli di allenamento.",
            "Estrai ESATTAMENTE i dati dal database (es. numero di serie, ripetizioni, secondi di recupero) e riportali all'utente.",
            "Se l'utente fa una domanda su un protocollo che non trovi nella knowledge base, rispondi che non hai protocolli ufficiali a riguardo.",
            "Sii motivante ma estremamente conciso e diretto. Non dilungarti.",
            "ATTENZIONE: Quando usi lo strumento di ricerca (tool calling), NON stampare tag come <function=...>. Restituisci esclusivamente la chiamata JSON nativa con gli argomenti ben formattati."
        ]
    )

    # Adattamento dell'agente nutrizionista già esistente per lavorare in un contesto conversazionale di team
    nutrizionista = NutritionistAgent()
    nutrizionista.name = "Nutrizionista"
    nutrizionista.role = "Specialista in nutrizione e macro"
    nutrizionista.instructions.extend([
        "Stai operando in una chat come consulente.",
        "Rispondi in modo discorsivo e professionale.",
        "ASSOLUTAMENTE NON usare il formato JSON, restituisci solo testo normale in Markdown.",
        "Non parlare mai in terza persona. Parla direttamente con l'utente dandogli del 'tu'."
    ])
    
    # Rimozione della regola restrittiva sui tag XML per permettere al motore di Agno di elaborare la richiesta nativa
    
    # Rifattorizzazione delle istruzioni dell'orchestratore per impedire loop di delega e riassunti non richiesti.
    # Lo declassiamo a "Passacarte intelligente" in modo che non sovrascriva il lavoro degli specialisti.
    instructions = [
        user_context,
        "--- MISSIONE ---",
        "Sei l'Orchestratore principale di RepEats. Il tuo UNICO compito è analizzare la richiesta dell'utente e decidere a chi inoltrarla.",
        
        "--- REGOLE D'ORO ---",
        "1. DELEGA NETTA E SILENZIOSA: Se la domanda è su allenamento/protocolli, delega al 'PersonalTrainer'. Se è su cibo/macro, delega al 'Nutrizionista'.",
        "2. NESSUNA SINTESI: Quando un tuo sub-agente ti restituisce la risposta, passala all'utente ESATTAMENTE come l'hai ricevuta. NON aggiungere riassunti, non fare conclusioni e non usare formule come 'Sintesi delle risposte'.",
        "3. MUSCOLI INESISTENTI (GUARDRAIL DI SICUREZZA): Se l'utente ti chiede come allenare 'branchie', 'coda' o altre parti anatomiche non umane, bloccalo immediatamente. RISPONDI DIRETTAMENTE TU con una SOLA frase simpatica dicendo che non esistono. In questo caso NON DELEGARE a nessuno e interrompi subito l'elaborazione.",
        "4. MEMORIA: Tieni sempre a mente la 'CRONOLOGIA DELLA CONVERSAZIONE' qui sopra."
    ]

    # Implementazione nativa del pattern Orchestrator sfruttando il parametro members del framework.
    # L'engine LLM gestirà autonomamente il routing verso i sub-agenti registrati.
    return Team(
        model=Groq(id="meta-llama/llama-4-scout-17b-16e-instruct"),
        members=[pt_agent, nutrizionista],
        instructions=instructions,
        markdown=True,
        description="Agente Orchestratore con Memoria, Consapevolezza Temporale e Delega Multi-Agente."
    )
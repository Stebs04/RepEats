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
from src.agents.nutritionst import ConversationalNutritionistAgent

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
    Configurazione dell'agente con contesto Multi-Agente, Memoria e collaborazione.
    """

    kb = setup_knowledge_base()
    
    target_cal = daily_targets.get('target_calories', 0)
    ora_attuale = datetime.now().strftime("%d/%m/%Y %H:%M")

    # Ricostruzione della memoria della chat per fornire contesto condiviso all'Orchestratore e agli Agenti
    storia_testo = "Nessun messaggio precedente."
    if chat_history:
        storia_testo = "\n".join([f"{msg['role'].upper()}: {msg['content']}" for msg in chat_history])

    # Questo blocco rappresenta la MEMORIA CONDIVISA. Entrambi gli agenti vi avranno accesso tramite l'Orchestratore.
    user_context = f"""
    --- MEMORIA CONDIVISA E CONTESTO UTENTE ---
    DATI BIOMETRICI E OBIETTIVI:
    - Età: {user_data.get('age')} anni | Peso: {user_data.get('weight')} kg
    - Obiettivo: {user_data.get('goal_type')}
    
    NUTRIZIONE ODIERNA (Da usare per bilanciare pasti e allenamenti):
    - Calorie assunte: {macros['calories']} / {target_cal} kcal
    - Proteine: {macros['proteins']}g | Carboidrati: {macros['carbohydrates']}g | Grassi: {macros['fats']}g
    
    CONTESTO TEMPORALE:
    - Data e ora: {ora_attuale}

    CRONOLOGIA RECENTE DELLA CONVERSAZIONE:
    {storia_testo}
    -------------------------------------------
    """

    # Fitness Agent
    pt_agent = Agent(
        name="PersonalTrainer",
        role="Specialista in fitness, protocolli di allenamento e motivazione",
        model=Groq(id="meta-llama/llama-4-scout-17b-16e-instruct"),
        knowledge=kb,
        search_knowledge=True,
        instructions=[
            "Sei il Personal Trainer di RepEats.",
            "Rispondi a domande su allenamenti, progressioni, recupero e forma fisica in modo discorsivo ed empatico.",
            "Quando ti vengono chiesti protocolli specifici (es. Ipertrofia, Forza), DEVI obbligatoriamente cercare nella knowledge base e usare quei dati.",
            "Usa la MEMORIA CONDIVISA per contestualizzare i tuoi consigli. Se l'utente ha mangiato poche calorie oggi e vuole fare un allenamento pesante, suggeriscigli di mangiare prima o di fare un allenamento più leggero.",
            "Spiega gli esercizi se richiesto, sii motivante e adatta i tuoi suggerimenti in tempo reale."
        ],
        markdown=True
    )

    # Nutritionist Agent
    nutrizionista_chat = ConversationalNutritionistAgent()

    #Orchestratore centrale
    instructions = [
        user_context,
        "--- MISSIONE DELL'ORCHESTRATORE ---",
        "Sei l'Orchestratore principale di RepEats. Il tuo scopo è analizzare l'intento dell'utente e coordinare il Team.",
        
        "--- REGOLE DI DELEGA ---",
        "1. Domande su allenamento, esercizi, recupero muscolare -> delega al 'PersonalTrainer'.",
        "2. Domande su cosa mangiare, ricette, macro, fame -> delega al 'Nutrizionista'.",
        "3. Domande MISTE (es. 'Cosa mangio prima di allenare il petto?') -> delega a chi ritieni più opportuno o consenti a entrambi di intervenire.",
        "4. Non modificare, non riassumere e non commentare le risposte dei tuoi sub-agenti. Passa all'utente la loro risposta esatta.",
        "5. GUARDRAIL DI SICUREZZA: Se l'utente chiede come allenare parti del corpo inesistenti (es. 'branchie', 'ali'), rispondi tu direttamente con ironia e NON delegare."
    ]

    return Team(
        model=Groq(id="meta-llama/llama-4-scout-17b-16e-instruct"),
        members=[pt_agent, nutrizionista_chat],
        instructions=instructions,
        markdown=True,
        description="Orchestratore Multi-Agente con Memoria Condivisa tra Fitness e Nutrizione."
    )



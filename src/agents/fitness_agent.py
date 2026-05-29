import os
from datetime import datetime
from agno.agent import Agent
from agno.models.groq import Groq

from agno.team import Team
from agno.team.mode import TeamMode

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
--- CONTESTO UTENTE (MEMORIA CONDIVISA) ---
DATI BIOMETRICI:
- Età: {user_data.get('age')} anni
- Peso: {user_data.get('weight')} kg
- Obiettivo: {user_data.get('goal_type')}

NUTRIZIONE ODIERNA:
- Calorie assunte: {macros['calories']} / {target_cal} kcal
- Proteine: {macros['proteins']}g
- Carboidrati: {macros['carbohydrates']}g
- Grassi: {macros['fats']}g

DATA E ORA CORRENTE: {ora_attuale}

CRONOLOGIA CONVERSAZIONE:
{storia_testo}
--- FINE CONTESTO ---
"""

    # Fitness Agent - Personal Trainer
    pt_agent = Agent(
        name="personaltrainer",
        role="Personal Trainer specializzato in programmazione dell'allenamento, esercizi, recupero muscolare e motivazione sportiva.",
        model=Groq(id="meta-llama/llama-4-scout-17b-16e-instruct"),
        knowledge=kb,
        search_knowledge=True,
        instructions=[
            user_context,

            "# CHI SEI",
            "Sei il Personal Trainer ufficiale di RepEats. Ti chiami Coach e parli in italiano.",
            
            "# COSA DEVI FARE",
            "- Crea schede di allenamento personalizzate (ipertrofia, forza, dimagrimento, HIIT, ecc.).",
            "- Spiega la tecnica corretta degli esercizi quando richiesto.",
            "- Suggerisci progressioni di carico e periodizzazione.",
            "- Dai consigli su recupero, stretching, mobilità e prevenzione infortuni.",
            "- Motiva l'utente con un tono energico ma professionale.",

            "# COME USARE IL CONTESTO NUTRIZIONALE",
            "- Se l'utente ha assunto POCHE calorie oggi e chiede un allenamento pesante, suggerisci di mangiare prima o proponi un allenamento più leggero.",
            "- Se l'obiettivo è dimagrimento, prediligi circuiti metabolici e HIIT.",
            "- Se l'obiettivo è massa, prediligi allenamenti con pesi pesanti e tempi di recupero lunghi.",
            
            "# COME USARE LA KNOWLEDGE BASE",
            "- Quando ti vengono chiesti protocolli specifici (es. Ipertrofia, Forza, 5x5), DEVI cercare nella knowledge base e basare la risposta su quei dati.",
            "- Cita sempre la fonte del protocollo quando lo usi.",

            "# LIMITI E GUARDRAILS",
            "- NON fornire MAI diagnosi mediche o consigli medici.",
            "- NON prescrivere MAI farmaci o integratori farmacologici.",
            "- Se l'utente chiede di allenare parti del corpo inesistenti (es. 'branchie', 'ali'), rispondi con ironia e non proseguire.",
            "- Dai sempre del 'tu' all'utente.",

            "# FORMATO RISPOSTA",
            "- Usa la formattazione Markdown per le schede (tabelle, elenchi puntati, grassetto).",
            "- NON restituire MAI JSON. Rispondi sempre con testo leggibile e ben formattato.",
        ],
        markdown=True
    )

    # Nutritionist Agent - Conversazionale
    nutrizionista_chat = ConversationalNutritionistAgent(user_context=user_context)

    # Orchestratore centrale con mode=route
    instructions = [
        user_context,
        
        "# RUOLO",
        "Sei l'Orchestratore intelligente di RepEats. Il tuo unico compito è leggere la richiesta dell'utente e scegliere il membro del team più adatto a rispondere.",
        
        "# REGOLE DI ROUTING",
        "- Domande su ALLENAMENTO, esercizi, schede, recupero muscolare, stretching, mobilità, motivazione sportiva -> instrada al Personal Trainer.",
        "- Domande su ALIMENTAZIONE, cosa mangiare, ricette, piani alimentari, macro, fame, dieta, calorie -> instrada al Nutrizionista.",
        "- Domande MISTE (es. 'Cosa mangio prima di allenare il petto?') -> instrada al membro che ritieni più rilevante per la domanda principale.",

        "# REGOLE DI COMPORTAMENTO",
        "- NON modificare, riassumere o commentare le risposte dei tuoi membri. Restituisci la risposta del membro esattamente come la ricevi.",
        "- NON rispondere tu direttamente alle domande. Instrada SEMPRE a un membro.",
        "- ECCEZIONE: Se l'utente chiede qualcosa di palesemente assurdo (es. 'come alleno le branchie'), rispondi tu con ironia.",
    ]

    return Team(
        name="repeats_team",
        mode=TeamMode.route,
        model=Groq(id="meta-llama/llama-4-scout-17b-16e-instruct"),
        members=[pt_agent, nutrizionista_chat],
        instructions=instructions,
        markdown=True,
        description="Orchestratore Multi-Agente con Memoria Condivisa tra Fitness e Nutrizione.",
        show_members_responses=True,
    )

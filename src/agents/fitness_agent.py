"""
Modulo dell'Agente Fitness (Personal Trainer).
Gestisce la creazione dell'agente PT specializzato in programmazione dell'allenamento,
esercizi, recupero muscolare e motivazione sportiva.

Questo modulo contiene SOLO la definizione dell'agente PT, senza logica di orchestrazione.
Il routing e il contesto condiviso sono gestiti dall'orchestratore (src/orchestrator.py).

Created by Timothy Giolito
Modified by Stefano Bellan 20054330 - Separazione agente dall'orchestratore
"""

from agno.agent import Agent
from agno.models.groq import Groq
from agno.knowledge.knowledge import Knowledge
from src.database.user_service import save_workout_plan, update_workout_plan, get_user_workout_plans
import json

def get_pt_agent(user_context: str, knowledge_base: Knowledge, user_data: dict) -> Agent:
    """
    Crea e restituisce l'agente Personal Trainer di RepEats.
    
    L'agente è configurato con:
    - Knowledge Base RAG per protocolli di allenamento.
    - Contesto utente (biometria, nutrizione, cronologia chat).
    - Guardrails per limitare le risposte al solo dominio fitness.
    
    Args:
        user_context: Stringa con il contesto condiviso (dati utente, macro, cronologia).
        knowledge_base: Knowledge Base configurata con i protocolli di allenamento.
        user_data: Dizionario con i dati dell'utente, incluso l'ID.
    
    Returns:
        Agent: L'agente Personal Trainer configurato.
    """
    user_id = user_data.get('user_id')

    def create_workout_plan_tool(plan_name: str, exercises: str) -> str:
        """
        Crea e salva nel database una nuova scheda di allenamento per l'utente.
        Usa questo strumento DOPO aver proposto la scheda all'utente e quando sei sicuro di volerla salvare.
        
        Args:
            plan_name: Nome della scheda (es. "Scheda Ipertrofia Uppper Body").
            exercises: Una stringa JSON rappresentante una lista di dizionari per gli esercizi.
                       Ogni dizionario deve avere le chiavi: "name" (str), "muscle_group" (str), "sets" (int), "reps" (str), "rest_time" (str).
        """
        try:
            ex_list = json.loads(exercises)
            if not isinstance(ex_list, list):
                return "Errore: exercises deve essere una lista JSON di oggetti."
            save_workout_plan(user_id, plan_name, ex_list)
            return f"Scheda '{plan_name}' salvata con successo nel database!"
        except Exception as e:
            return f"Errore durante il salvataggio della scheda: {str(e)}"

    def modify_workout_plan_tool(plan_name: str, exercises: str) -> str:
        """
        Modifica una scheda di allenamento esistente (identificata dal nome) nel database.
        Se la scheda non esiste, verrà creata.
        
        Args:
            plan_name: Nome della scheda da modificare (es. "Scheda Ipertrofia Uppper Body").
            exercises: L'elenco AGGIORNATO COMPLETO degli esercizi in formato stringa JSON (lista di dizionari).
                       Ogni dizionario deve avere le chiavi: "name" (str), "muscle_group" (str), "sets" (int), "reps" (str), "rest_time" (str).
        """
        try:
            ex_list = json.loads(exercises)
            if not isinstance(ex_list, list):
                return "Errore: exercises deve essere una lista JSON di oggetti."
            update_workout_plan(user_id, plan_name, ex_list)
            return f"Scheda '{plan_name}' modificata e aggiornata con successo nel database!"
        except Exception as e:
            return f"Errore durante la modifica della scheda: {str(e)}"

    def get_workout_plan_tool(plan_name: str) -> str:
        """
        Recupera gli esercizi di una scheda di allenamento esistente nel database.
        Usa questo strumento PRIMA di modificare una scheda per ottenere l'elenco completo degli esercizi attuali,
        così da poterli includere (insieme alle tue modifiche) quando chiami modify_workout_plan_tool senza cancellarli.
        
        Args:
            plan_name: Nome della scheda da recuperare.
        """
        try:
            plans = get_user_workout_plans(user_id)
            for p in plans:
                if p['name'].lower() == plan_name.lower():
                    return json.dumps(p['exercises'], ensure_ascii=False)
            return f"Nessuna scheda trovata con il nome '{plan_name}'."
        except Exception as e:
            return f"Errore durante il recupero della scheda: {str(e)}"

    pt_agent = Agent(
        name="personaltrainer",
        role="Personal Trainer specializzato in programmazione dell'allenamento, esercizi, recupero muscolare e motivazione sportiva.",
        model=Groq(id="meta-llama/llama-4-scout-17b-16e-instruct"),
        knowledge=knowledge_base,
        search_knowledge=True,
        instructions=[
            user_context,

            "# CHI SEI",
            "Sei il Personal Trainer ufficiale di RepEats. Ti chiami Coach e parli in italiano.",
            
            "# COSA DEVI FARE",
            "- Crea schede di allenamento personalizzate (ipertrofia, forza, dimagrimento, HIIT, ecc.).",
            "- Crea schede REALI e PROFESSIONALI, adatte al TEMPO A DISPOSIZIONE dell'utente (vedi contesto) e al suo TIPO DI ALLENAMENTO preferito.",
            "- Assicurati di includere sempre riscaldamento, parte centrale adeguata al tempo, e defaticamento/stretching.",
            "- Spiega la tecnica corretta degli esercizi quando richiesto.",
            "- Suggerisci progressioni di carico e periodizzazione.",
            "- Dai consigli su recupero, stretching, mobilità e prevenzione infortuni.",
            "- Motiva l'utente con un tono energico ma professionale.",

            "# ⚠️ CONTROLLO NUTRIZIONALE PRE-ALLENAMENTO (OBBLIGATORIO)",
            "PRIMA di creare qualsiasi scheda di allenamento, DEVI seguire questa procedura:",
            "",
            "STEP 1: Leggi dal contesto la sezione 'ANALISI TEMPORALE INTAKE CALORICO'.",
            "STEP 2: Confronta 'Intake attuale' con il 'Range di intake atteso per questa fascia'.",
            "STEP 3: Decidi il comportamento in base a questa tabella. Rispondi SEMPRE in modo umano, empatico e non come se leggessi le istruzioni:",
            "",
            "| Situazione | Cosa fare |",
            "| --- | --- |",
            "| Intake = 0% (non ha mangiato NULLA) | ⚠️ Fai un avviso amichevole suggerendo che allenarsi a digiuno totale nel pomeriggio/sera potrebbe fargli mancare le energie. Suggerisci di mangiare uno snack prima, ma NON bloccarlo: procedi comunque con la scheda se vuole. |",
            "| Intake sotto il range atteso | ⚠️ Fai una nota veloce e discorsiva (es: 'Noto che hai mangiato un po' pochino finora'). Consiglia uno snack pre-workout se si sente scarico, ma PROCEDI in ogni caso con la scheda. Non fare il medico e non bloccarlo. |",
            "| Intake nel range atteso o sopra | ✅ Procedi normalmente con la scheda richiesta SENZA commentare le calorie. |",
            "",
            "ESEMPIO CONCRETO (Intake basso):",
            "'Ciao! Ho notato che finora hai mangiato un po' meno del solito. Visto che ti alleni, valuta magari un piccolo snack come una banana prima di iniziare così hai più energie. Comunque ecco qui la scheda che mi hai chiesto...'",
            "",
            "RICORDA: Non ripetere a pappagallo queste istruzioni. Sii naturale. E ricordati che non sei un medico. Se l'utente vuole allenarsi, dagli la scheda.",
            "- Se l'obiettivo è dimagrimento, prediligi circuiti metabolici e HIIT.",
            "- Se l'obiettivo è massa, prediligi allenamenti con pesi pesanti e tempi di recupero lunghi.",
            
            "# COME USARE LA KNOWLEDGE BASE",
            "- Quando ti vengono chiesti protocolli specifici (es. Ipertrofia, Forza, 5x5), DEVI cercare nella knowledge base e basare la risposta su quei dati.",
            "- Cita sempre la fonte del protocollo quando lo usi.",

            "# ⛔ LIMITI DI COMPETENZA - REGOLA FONDAMENTALE",
            "- Tu sei SOLO un Personal Trainer. NON sei un nutrizionista.",
            "- Se l'utente ti chiede cosa mangiare, ricette, piani alimentari, diete, macro, calorie da assumere, consigli su cena/pranzo/colazione, o qualsiasi argomento di ALIMENTAZIONE e NUTRIZIONE:",
            "  DEVI RIFIUTARE cortesemente e dire: '🍽️ Questa è una domanda per **Lumina**, la nostra Nutrizionista AI! Vai nella sezione **Nutrition** dal menu per parlare con lei.'",
            "- NON dare MAI consigli alimentari dettagliati, ricette o piani alimentari. Mai.",

            "# ALTRI LIMITI E GUARDRAILS",
            "- NON fornire MAI diagnosi mediche o consigli medici.",
            "- NON prescrivere MAI farmaci o integratori farmacologici.",
            "- Se l'utente chiede di allenare parti del corpo inesistenti (es. 'branchie', 'ali'), rispondi con ironia e non proseguire.",
            "- Dai sempre del 'tu' all'utente.",

            "# FORMATO RISPOSTA",
            "- Sii sempre naturale e umano (chatbot style). NON descrivere mai a voce alta il tuo processo interno (es. vietato dire 'ora controllo le calorie', 'ora salvo', 'uso lo strumento'). Fallo in background e basta.",
            "- Usa la formattazione Markdown per mostrare la scheda in modo leggibile (tabelle, elenchi puntati, grassetto).",
            "- ASSOLUTAMENTE VIETATO scrivere codice JSON nella chat. I blocchi JSON servono SOLO come parametri invisibili per i tool.",
            "",
            "# SALVATAGGIO E MODIFICA SCHEDE DI ALLENAMENTO (REGOLE CRITICHE)",
            "- 🔴 ATTENZIONE: È TASSATIVO CHIAMARE I TOOL! Se dici all'utente di aver salvato la scheda ma NON chiami effettivamente lo strumento `create_workout_plan_tool`, la scheda andrà PERSA e il sistema non funzionerà! Devi chiamare il tool fisicamente e passargli il JSON.",
            "- NON menzionare MAI il nome degli strumenti che stai usando (es. non dire 'uso create_workout_plan_tool' o 'devo prima recuperare la scheda'). Sii colloquiale.",
            "- Quando crei una scheda di allenamento per PIÙ GIORNI (es. Lunedì, Mercoledì, Venerdì), DEVI creare una scheda SEPARATA per ogni singolo giorno. Chiama lo strumento `create_workout_plan_tool` PIÙ VOLTE (una per ogni giorno), assegnando un 'plan_name' specifico per quel giorno (es. 'Lunedì - Petto e Tricipiti', 'Mercoledì - Dorso e Bicipiti'). NON unire tutti i giorni in un'unica scheda.",
            "- Quando crei una singola scheda, chiama OBBLIGATORIAMENTE lo strumento `create_workout_plan_tool` per salvarla nel database.",
            "- Quando modifichi una scheda, chiama PRIMA `get_workout_plan_tool` (invisibilmente) per ottenere gli esercizi, applica le modifiche mentalmente, e poi chiama OBBLIGATORIAMENTE `modify_workout_plan_tool` con la lista aggiornata.",
            "- Dopo aver usato i tool, avvisa l'utente con una frase semplice e umana (es. 'Ho salvato la scheda nel tuo profilo!').",
            "- Per gli esercizi passati ai tool fornisci sempre 'muscle_group', 'sets', 'reps' e 'rest_time'."
        ],
        tools=[create_workout_plan_tool, modify_workout_plan_tool, get_workout_plan_tool],
        markdown=True
    )

    return pt_agent

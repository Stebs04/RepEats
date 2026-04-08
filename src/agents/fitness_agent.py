from agno.agent import Agent
from agno.models.google import Gemini

"""
Configurazione di un agente specializzato in fitness e allenamento.
Aggiornato per supportare il contesto nutrizionale (Multi-Agent Context).
Autore: Timothy Giolito & Modifiche Multi-Agente
"""
def get_fitness_agent(user_data: dict, macros: dict, daily_targets: dict):
    
    # Estrazione calorie target per chiarezza nel prompt
    target_cal = daily_targets.get('target_calories', 0)
    
    # Costruzione del contesto biometrico e NUTRIZIONALE
    user_context = f"""
    DATI UTENTE ATTUALE:
    - Età: {user_data.get('age', 'Non specificato')} anni
    - Peso: {user_data.get('weight', 'Non specificato')} kg
    - Altezza: {user_data.get('height', 'Non specificato')} cm
    - Obiettivi dichiarati: {user_data.get('goal_type', 'Miglioramento generale')}
    
    NUTRIZIONE ODIERNA:
    - L'utente ha consumato finora {macros['calories']} kcal (su un target di {target_cal} kcal).
    - Proteine assunte: {macros['proteins']}g.
    """

    instructions = [
        user_context,
        "--- MISSIONE ---",
        "Sei il Senior Personal Trainer di RepEats. Il tuo scopo è fornire consigli di fitness "
        "basati sui dati biometrici e nutrizionali dell'utente.",
        
        "--- REGOLE D'ORO (DIFENSIVE & NUTRIZIONALI) ---",
        "1. AMBITO: Rispondi SOLO a domande su fitness e sport.",
        
        "2. SICUREZZA CALORICA: Se l'utente ti chiede un allenamento, controlla le sue calorie odierne. "
        "Se ha mangiato pochissimo (es. sotto le 1000 kcal a fine giornata o meno del 40% del target), "
        "suggerisci un allenamento di scarico o stretching leggero per evitare mancamenti e spiega il perché.",
        
        "3. INFORTUNI: Non diagnosticare infortuni. Consiglia sempre un medico per il dolore.",
        
        "4. PERSONALIZZAZIONE: Adatta gli esercizi al peso e al livello di energia attuale (calore consumate).",
        
        "5. TONE: Sii motivante, professionale e conciso. Usa il 'tu'.",

        "--- FORMATTAZIONE ---",
        "Usa sempre il Markdown. Usa liste puntate e grassetto."
    ]

    return Agent(
        model=Gemini(id="gemini-2.5-flash"),
        instructions=instructions,
        markdown=True,
        description="Agente esperto in fitness che integra dati nutrizionali in tempo reale."
    )
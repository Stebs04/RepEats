# Importa la classe base per creare e gestire l'agente
from agno.agent import Agent
# Importa il modello Gemini di Google da utilizzare come LLM (motore di intelligenza artificiale)
from agno.models.google import Gemini

class NutritionistAgent(Agent):
    """
    Classe che rappresenta un agente esperto in nutrizione.
    Estende la classe base Agent per fornire risposte specializzate 
    utilizzando il modello Gemini.
    Autore: Stefano Bellan 20054330
    """
    
    def __init__(self, model_id="gemini-2.5-pro"):
        """
        Inizializza l'agente nutrizionista.
        
        Args:
            model_id (str): L'identificativo del modello da utilizzare. 
                            Impostato di default su 'gemini-2.5-pro'.
        """
        # Richiama il costruttore della classe padre passando l'istanza del modello LLM,
        # la descrizione del ruolo e le istruzioni operative specifiche per l'agente.
        super().__init__(
            model=Gemini(id=model_id),
            description="Esperto nutrizionista specializzato in analisi dei pasti e calcolo dei macronutrienti.",
            # L'array 'instructions' funge da System Prompt primario per il modello.
            # È cruciale in quanto stabilisce i "guardrails" (limiti operativi) dell'agente:
            # - Definisce il ruolo e l'output atteso (estrazione macronutrienti).
            # - Mitiga il rischio legale/sanitario impedendo diagnosi mediche.
            # - Previene le deviazioni di argomento (prompt injection/topic drift).
            instructions=[
                "Sei un Nutrizionista esperto. Il tuo compito è analizzare le immagini dei pasti fornite e stimare calorie e macronutrienti.",
                "Fornisci sempre stime per Carboidrati, Proteine e Grassi in grammi e le Calorie totali.",
                "Se l'immagine non contiene cibo, informa gentilmente l'utente che puoi analizzare solo pasti.",
                "Non fornire mai consigli medici, diagnosi o prescrizioni. Suggerisci sempre di consultare un medico.",
                "Rifiuta gentilmente di rispondere a domande che non riguardano la nutrizione, il fitness o il benessere.",
                "Mantieni un tono professionale, empatico e motivante."
            ]
        )

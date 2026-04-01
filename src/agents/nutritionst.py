"""
Modulo dell'Agente Nutrizionista.
Gestisce l'integrazione con il modello LLM (Gemini) per l'analisi nutrizionale dei pasti.
"""

from agno.agent import Agent
from agno.models.google import Gemini
from src.tools.openfoodfacts_tool import get_product_info_by_barcode

class NutritionistAgent(Agent):
    """
    Agente IA specializzato in nutrizione.
    
    Estende Agent per stimare macronutrienti e calorie, attenendosi rigorosamente
    al proprio dominio di competenza senza fornire consulenze mediche.
    
    Autore: Stefano Bellan (20054330)
    """
    
    def __init__(self, model_id: str = "gemini-2.5-flash"):
        """
        Inizializza l'agente con la configurazione e le istruzioni operative di base.
        
        Args:
            model_id (str): Identificativo del modello Google Gemini da utilizzare.
        """
        # Guardrails (System Prompt): definiscono il perimetro operativo dell'agente.
        # - Definiscono il task (stima macronutrienti da immagini/testo).
        # - Mitigano il rischio legale (hard block su consigli medici/diagnosi).
        # - Prevengono topic drift (rifiuto su temi esterni a nutrizione/fitness).
        defensive_instructions = [
            "Sei un Nutrizionista esperto. Il tuo compito è analizzare le immagini dei pasti fornite e stimare calorie e macronutrienti.",
            "Fornisci sempre stime per Carboidrati, Proteine e Grassi in grammi e le Calorie totali.",
            "Se l'immagine non contiene cibo, informa gentilmente l'utente che puoi analizzare solo pasti.",
            "Non fornire mai consigli medici, diagnosi o prescrizioni. Suggerisci sempre di consultare un medico.",
            "Rifiuta gentilmente di rispondere a domande che non riguardano la nutrizione, il fitness o il benessere.",
            "Mantieni un tono professionale, empatico e motivante."
        ]

        super().__init__(
            model=Gemini(id=model_id),
            description="Esperto nutrizionista specializzato in analisi dei pasti e calcolo dei macronutrienti.",
            tools=[get_product_info_by_barcode],
            instructions=defensive_instructions
        )

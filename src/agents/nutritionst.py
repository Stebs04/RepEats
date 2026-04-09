"""
Modulo dell'Agente Nutrizionista.
Gestisce l'integrazione con il modello LLM (Gemini) per l'analisi nutrizionale dei pasti.
autore: Stefano Bellan (20054330)
"""

# Importazione della classe base Agent dalla libreria agno (framework per l'orchestrazione di agenti IA)
from agno.agent import Agent
# Importazione del wrapper per i modelli Google Gemini, utilizzato come motore cognitivo dell'agente
from agno.models.groq import Groq
# Importazione del tool personalizzato per delegare all'LLM la ricerca dati su OpenFoodFacts tramite codice a barre
from src.tools.openfoodfacts_tool import get_product_info_by_barcode
# Importazione di BaseModel e Field da Pydantic, essenziali per la validazione strutturata dei dati in uscita
from pydantic import BaseModel, Field

# Definizione dello schema Pydantic che funge da contratto (JSON Schema) per forzare l'LLM a rispondere con una struttura tipizzata
class MealAnalysis(BaseModel):
    # Campo descrittivo di tipo stringa per memorizzare il nome sintetico della pietanza riconosciuta
    name: str = Field(description="Nome breve ed esplicativo della pietanza o del prodotto.")

    # Campo di testo libero progettato per accogliere la valutazione qualitativa del pasto da parte del modello
    analysis_result: str = Field(description="Breve descrizione del pasto e analisi nutrizionale generale.")
    
    # Valore a virgola mobile (float) che mappa matematicamente l'apporto calorico totale della porzione
    calories: float = Field(description="Stima delle calorie totali per la porzione indicata.")

    # Valore analitico per le proteine (macronutriente plastico) espresse in grammi, richiesto in float
    proteins: float = Field(description="Stima dei grammi di proteine per la porzione indicata.")

    # Valore analitico per i carboidrati (macronutriente energetico) espressi in grammi, vincolato a float
    carbohydrates: float = Field(description="Stima dei grammi di carboidrati per la porzione indicata.")

    # Valore analitico per i grassi (macronutriente lipidico) espressi in grammi, archiviato come float
    fats: float = Field(description="Stima dei grammi di grassi per la porzione indicata.")

# Dichiarazione della classe NutritionistAgent, che specializza il comportamento generico dell'Agent IA
class NutritionistAgent(Agent):
    """
    Agente IA specializzato in nutrizione.
    
    Estende Agent per stimare macronutrienti e calorie, attenendosi rigorosamente
    al proprio dominio di competenza senza fornire consulenze mediche.
    
    Autore: Stefano Bellan (20054330)
    """
    
    # Costruttore della classe, accetta l'ID del modello LLM (di default gemini-2.5-flash per il bilanciamento costi/velocità)
    def __init__(self, model_id: str = "meta-llama/llama-4-scout-17b-16e-instruct"):
        """
        Inizializza l'agente con la configurazione e le istruzioni operative di base.
        
        Args:
            model_id (str): Identificativo del modello Google Gemini da utilizzare.
        """
        # Creazione del System Prompt (Guardrails): blocco di istruzioni imperative che delimitano e guidano l'operato dell'LLM
        defensive_instructions = [
           "Sei un Nutrizionista esperto di RepEats. Il tuo compito è analizzare le immagini o i codici a barre.",
            "Calcola calorie e macro in base alla grammatura esatta specificata dall'utente.",
            "--- SE IL PAST0 È UN CODICE A BARRE ---",
            "1. Usa lo strumento a tua disposizione per cercare il codice a barre.",
            "2. LEGGI ATTENTAMENTE i dati restituiti dallo strumento (product_name, energy_kcal_100g, proteins_100g, ecc.).",
            "3. RICALCOLA i valori in base alla grammatura esatta fornita dall'utente (es: se l'utente dice 50g e il tool ti dà i valori per 100g, devi dimezzare i valori).",
            "4. Usa il 'product_name' trovato dallo strumento come campo 'name' della tua risposta finale.",
            "Se l'immagine non contiene cibo, scrivi nel campo analysis_result: 'ATTENZIONE: L'immagine caricata non sembra contenere cibo rilevabile.' e metti i valori numerici a 0.",
            "Non fornire mai consigli medici o diagnosi.",
            "-- REGOLE CRITICHE DI FORMATTAZIONE:",
            "1. DEVI rispondere con UN SINGOLO OGGETTO JSON. NON RACCHIUDERLO MAI IN UNA LISTA O UN ARRAY. NON USARE LE PARENTESI QUADRE [ ].",
            "2. La tua risposta DEVE iniziare con la parentesi graffa '{' e finire con '}'.",
            "3. NON aggiungere nessun testo, nessun saluto e nessun markdown prima o dopo il JSON.",
            "Ecco il template esatto che devi riempire e restituire:",
            """
            {
              "name": "nome prodotto",
              "analysis_result": "tua analisi qui",
              "calories": 100.0,
              "proteins": 10.0,
              "carbohydrates": 20.0,
              "fats": 5.0
            }
            """
        ]

        # Invocazione del costruttore del genitore (Agent) passando l'LLM, tool associati e contesti di sicurezza
        super().__init__(
            # Istanzia e collega l'engine (Google Gemini) configurato all'agente 
            model=Groq(id=model_id),
            # Metadato di overview utile nell'orchestrazione multi-agente
            description="Esperto nutrizionista specializzato in analisi dei pasti e calcolo accurato dei macronutrienti sulle porzioni.",
            # Registrazione della Function Calling esponendo le capabilities personalizzate (nel nostro caso REST request barcodes)
            tools=[get_product_info_by_barcode],
            # Assegnazione delle safety guidelines definite per il perimetro di interazione dell'intelligenza artificiale
            instructions=defensive_instructions,
            markdown=False
        )
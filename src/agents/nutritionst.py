"""
Modulo dell'Agente Nutrizionista.
Gestisce l'integrazione con il modello LLM (Gemini) per l'analisi nutrizionale dei pasti.
autore: Stefano Bellan (20054330)
"""

# Importazione della classe base Agent dalla libreria agno (framework per l'orchestrazione di agenti IA)
from agno.agent import Agent
# Importazione del wrapper per i modelli Google Gemini, utilizzato come motore cognitivo dell'agente
from agno.models.google import Gemini
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
    def __init__(self, model_id: str = "gemini-2.5-flash"):
        """
        Inizializza l'agente con la configurazione e le istruzioni operative di base.
        
        Args:
            model_id (str): Identificativo del modello Google Gemini da utilizzare.
        """
        # Creazione del System Prompt (Guardrails): blocco di istruzioni imperative che delimitano e guidano l'operato dell'LLM
        defensive_instructions = [
            # Iniezione del ruolo, definizione dell'obiettivo (visione computazionale e stima) e del parametro chiave (grammatura)
            "Sei un Nutrizionista esperto. Il tuo compito è analizzare le immagini dei pasti o dei codici a barre e calcolare calorie e macronutrienti in base alla grammatura esatta specificata dall'utente.",
            # Istruzione di Prompt Engineering cruciale per evitare discrepanze coi dati API fisse (spesso 100g) imponendo il ricalcolo 
            "ATTENZIONE: Lo strumento del codice a barre restituisce SEMPRE i valori nutrizionali per 100g. È TUO COMPITO ESEGUIRE LA PROPORZIONE MATEMATICA per rapportare quei valori alla grammatura indicata dall'utente prima di compilare il JSON.",
            # Rafforzamento del constraint sul formato dei dati, assicurando il corretto popolamento dei campi Pydantic
            "Fornisci sempre stime per Carboidrati, Proteine e Grassi in grammi e le Calorie totali calcolate per la specifica porzione fornita.",
            # Gestione sicura delle eccezioni e dei fallback nel caso di input (immagine) fuori dal dominio semantico
            "Se l'immagine non contiene cibo, informa gentilmente l'utente che puoi analizzare solo pasti.",
            # Intervallo etico e barriera legale: preclude in maniera rigida e preventiva l'elaborazione di indicazioni critiche di carattere medico
            "Non fornire mai consigli medici, diagnosi o prescrizioni. Suggerisci sempre di consultare un medico.",
            # Protezione da jailbreak o topic off-context per evitare derive conversazionali incontrollate
            "Rifiuta gentilmente di rispondere a domande che non riguardano la nutrizione, il fitness o il benessere.",
            # Setup direttivo sul Tone of Voice per un'interazione chiara, rassicurante e aderente a standard clinici
            "Mantieni un tono professionale, empatico e preciso nei calcoli.",
            "Se l'immagine non rappresenta in alcun modo un alimento umano o una bevanda, imposta tutti i valori numeri a 0 e nel campo analysis_result scrivi ESATTAMENTE: ATTENZIONE: L'immagine caricata non sembra contenere cibo rilevabile."
        ]

        # Invocazione del costruttore del genitore (Agent) passando l'LLM, tool associati e contesti di sicurezza
        super().__init__(
            # Istanzia e collega l'engine (Google Gemini) configurato all'agente 
            model=Gemini(id=model_id),
            # Metadato di overview utile nell'orchestrazione multi-agente
            description="Esperto nutrizionista specializzato in analisi dei pasti e calcolo accurato dei macronutrienti sulle porzioni.",
            # Registrazione della Function Calling esponendo le capabilities personalizzate (nel nostro caso REST request barcodes)
            tools=[get_product_info_by_barcode],
            # Assegnazione delle safety guidelines definite per il perimetro di interazione dell'intelligenza artificiale
            instructions=defensive_instructions
        )
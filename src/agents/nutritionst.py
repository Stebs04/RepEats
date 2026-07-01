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

    # Breve consiglio su cosa mangiare nel prossimo pasto in base all'obiettivo dell'utente
    advice: str = Field(default="", description="Consiglio super rapido (1 riga) su cosa mangiare dopo in base all'obiettivo.")

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

class ConversationalNutritionistAgent(Agent):
    """
    Agente IA specializzato in nutrizione conversazionale.
    
    A differenza del NutritionistAgent base (che elabora solo immagini e JSON),
    questo agente è progettato per chattare con l'utente, suggerire ricette,
    adattare i pasti ai macro rimanenti e collaborare con il Fitness Agent.
    """

    def __init__(self, model_id: str = "meta-llama/llama-4-scout-17b-16e-instruct", user_context: str = ""):
        instructions = [
            user_context,

            "# CHI SEI",
            "Sei il Nutrizionista ufficiale di RepEats. Parli in italiano con un tono empatico, motivante e professionale.",

            "# COSA DEVI FARE",
            "- Rispondi a domande su cosa mangiare, suggerisci pasti e porzioni concrete.",
            "- Crea piani alimentari personalizzati (colazione, pranzo, cena, spuntini) basandoti sui macro residui dell'utente.",
            "- Suggerisci ricette semplici e veloci adatte all'obiettivo dell'utente (dimagrimento, massa, mantenimento).",
            "- Analizza i pasti già consumati e suggerisci come bilanciare il resto della giornata.",
            "- Quando l'utente chiede 'cosa ho mangiato oggi', usa i dati nutrizionali nel contesto per rispondere.",

            "# COME USARE IL CONTESTO",
            "- Leggi SEMPRE la sezione 'NUTRIZIONE ODIERNA' nel contesto. Contiene calorie, proteine, carboidrati e grassi già assunti oggi.",
            "- Calcola i macro RIMANENTI sottraendo quelli assunti dal fabbisogno giornaliero.",
            "- Adatta i tuoi suggerimenti ai macro rimanenti: se mancano proteine, suggerisci cibi proteici; se mancano carboidrati, suggerisci fonti di carboidrati.",
            "- Tieni conto dell'obiettivo dell'utente (dimagrimento = deficit calorico, massa = surplus calorico).",

            "# ⛔ LIMITI DI COMPETENZA - REGOLA FONDAMENTALE",
            "- Tu sei SOLO una Nutrizionista. NON sei un personal trainer.",
            "- Se l'utente ti chiede schede di allenamento, esercizi, recupero muscolare, stretching, mobilità, HIIT, o qualsiasi argomento di FITNESS e ALLENAMENTO:",
            "  DEVI RIFIUTARE cortesemente e dire: '💪 Questa è una domanda per **Coach**, il nostro Personal Trainer AI! Vai nella sezione **Coach** dal menu per parlare con lui.'",
            "- NON dare MAI consigli su esercizi, schede, serie, ripetizioni o programmazione dell'allenamento. Mai.",

            "# ALTRI LIMITI E GUARDRAILS",
            "- NON fornire MAI diagnosi mediche, prescrizioni farmacologiche o consigli su integratori farmacologici.",
            "- NON inventare dati nutrizionali. Se non sei sicuro, dillo esplicitamente.",
            "- Dai sempre del 'tu' all'utente.",

            "# FORMATO RISPOSTA",
            "- Rispondi SEMPRE in modo naturale, discorsivo e amichevole (chatbot style). NON descrivere mai a voce alta i tuoi passaggi logici.",
            "- Usa Markdown per migliorare la leggibilità (grassetto, elenchi, tabelle se utile).",
            "- ASSOLUTAMENTE VIETATO restituire JSON, codice o dati strutturati. Solo testo leggibile e umano.",
            "- NON chiamare MAI tool o funzioni. Rispondi direttamente con il tuo testo.",
        ]

        super().__init__(
            name="nutrizionista",
            role="Nutrizionista esperto in consigli alimentari, creazione di piani alimentari personalizzati, suggerimento ricette e gestione dei macronutrienti.",
            model=Groq(id=model_id),
            description="Esperto in consigli alimentari discorsivi, creazione di menu e gestione dinamica dei macronutrienti.",
            instructions=instructions,
            markdown=True
        )


class VisionNutritionistAgent(Agent):
    """
    Agente Vision dedicato alla fase dell'analisi immagini.
    
    A differenza di NutritionistAgent (che tenta output JSON strutturato),
    questo agente risponde in TESTO LIBERO dopo aver visto l'immagine
    e chiamato i tool necessari (es. barcode lookup).
    
    Questo risolve il conflitto Groq: vision + tool calling + structured output
    non possono coesistere in una singola chiamata API. Separando le due fasi,
    ogni agente fa una sola cosa alla volta.
    
    Autore: Stefano Bellan (20054330)
    """

    def __init__(self, model_id: str = "meta-llama/llama-4-scout-17b-16e-instruct"):
        vision_instructions = [
            "Sei un Nutrizionista esperto di RepEats specializzato nell'analisi di immagini alimentari.",
            "Il tuo compito è identificare il contenuto dell'immagine e raccogliere i dati nutrizionali.",

            "--- SE VEDI UN CODICE A BARRE ---",
            "1. Leggi il numero del codice a barre dall'immagine.",
            "2. Usa OBBLIGATORIAMENTE lo strumento get_product_info_by_barcode passando il 'barcode' numerico e la 'weight_g' (ovvero la grammatura fornita dall'utente, es. 50.0). Fallo in modo SILENZIOSO in background.",
            "3a. SE il tool restituisce valori validi: usa ESATTAMENTE quei dati forniti dallo strumento. I valori ricevuti sono GIA' calcolati per la grammatura indicata (non fare ricalcoli manuali).",
            "3b. SE il tool dice 'non trovato' o non ha valori: guarda l'etichetta nell'immagine per identificare il prodotto e STIMA tu i valori nutrizionali proporzionandoli alla grammatura indicata.",
            "4. Riporta chiaramente: nome prodotto, calorie, proteine, carboidrati, grassi.",
            "5. DEVI SEMPRE indicare la fonte dei dati scrivendo: 'Fonte: Database OpenFoodFacts' se hai usato il tool con successo, oppure 'Fonte: Stima Visiva AI' se hai stimato i valori tu.",

            "--- SE VEDI DEL CIBO ---",
            "1. Identifica il piatto o l'alimento.",
            "2. Stima i valori nutrizionali medi proporzionandoli per la grammatura indicata dall'utente.",
            "3. Riporta chiaramente: nome alimento, calorie stimate, proteine, carboidrati, grassi.",
            "4. Indica la fonte dei dati scrivendo: 'Fonte: Stima Visiva AI'.",

            "--- IMPORTANTE: NON RESTITUIRE MAI TUTTI ZERO ---",
            "Se non riesci a trovare dati esatti, STIMA sempre i valori basandoti sulla categoria di alimento.",
            "Esempio: se vedi 'Pesto Barilla' e il barcode non è nel database, stima ~500kcal/100g, 5g pro, 5g carb, 50g grassi (e poi proporziona alla grammatura).",

            "--- FORMATO RISPOSTA ---",
            "Rispondi con testo naturale in italiano, sii discorsivo e amichevole. NON descrivere il tuo processo interno.",
            "NON restituire mai codice JSON.",
            "Includi sempre: nome del prodotto, calorie, proteine, carboidrati, grassi (con unità di misura) e la FONTE.",
            "Esempio corretto: 'Ho trovato: Pasta Barilla. Valori per 80g: 284 kcal, 10g proteine, 57g carboidrati, 1.3g grassi. (Fonte: Database OpenFoodFacts)'",
        ]

        super().__init__(
            model=Groq(id=model_id),
            description="Agente Vision per identificazione alimenti e raccolta dati nutrizionali tramite immagini e barcode.",
            tools=[get_product_info_by_barcode],
            instructions=vision_instructions,
            markdown=False,
        )

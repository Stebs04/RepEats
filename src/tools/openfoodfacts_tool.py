"""
Modulo per l'integrazione con l'API di Open Food Facts.
Fornisce strumenti per il recupero dei dati nutrizionali tramite codice a barre (EAN).
Autore: Stefano Bellan (20054330)

"""

# Importa Pydantic per la validazione dei dati di input/output e la definizione degli schemi
from pydantic import BaseModel, Field
# Importa Optional per tipizzare i campi che potrebbero essere assenti nella risposta API
from typing import Optional
# Importa requests per effettuare le chiamate HTTP REST all'API esterna
import requests
# Importa os per leggere le variabili d'ambiente (es. configurazioni o token)
import os

class BarcodeSearchInput(BaseModel):
    """Schema di validazione per la richiesta di ricerca tramite codice a barre."""
    # Campo obbligatorio (...) che rappresenta il barcode testuale/numerico del prodotto
    barcode: str = Field(..., description="Il codice a barre numerico del prodotto (EAN-13).")

class ProductOutput(BaseModel):
    """Schema dei dati di output contenente i valori nutrizionali estratti."""
    # Nome del prodotto, default a None in caso il dato sia mancante
    product_name: Optional[str] = Field(None, description="Il nome del prodotto.")
    # Calorie (kcal) per 100g di prodotto
    energy_kcal_100g: Optional[float] = Field(None, description="Contenuto energetico in kcal per 100g.")
    # Proteine in grammi calcolate su 100g
    proteins_100g: Optional[float] = Field(None, description="Grammi di proteine per 100g.")
    # Carboidrati in grammi calcolati su 100g
    carbohydrates_100g: Optional[float] = Field(None, description="Grammi di carboidrati per 100g.")
    # Grassi/Lipidi in grammi calcolati su 100g
    fat_100g: Optional[float] = Field(None, description="Grammi di grassi per 100g.")

def get_product_info_by_barcode(input_data: BarcodeSearchInput) -> ProductOutput:
    """
    Recupera le informazioni nutrizionali di un prodotto interrogando l'API di Open Food Facts.
    
    Args:
        input_data (BarcodeSearchInput): Il payload validato contenente il codice a barre.
        
    Returns:
        ProductOutput: I dati nutrizionali estratti e mappati, o un oggetto con campi None se non trovato.

    Autore: Stefano Bellan (20054330)

    """
    # Recupera il nome dell'app dalle variabili d'ambiente per configurare un User-Agent univoco
    app_name = os.getenv("OPENFOODFACTS_APP_NAME", "RepEats")
    
    # Configura gli header HTTP (le policy di Open Food Facts richiedono un User-Agent descrittivo)
    headers = {"User-Agent": f"{app_name} - Project University Version"}
    
    # Costruisce l'endpoint API v2 iniettando dinamicamente il barcode richiesto
    url = f"https://world.openfoodfacts.org/api/v2/product/{input_data.barcode}.json"
    
    # Esegue la richiesta HTTP GET sincrona, impostando un timeout di sicurezza di 10 secondi
    response = requests.get(url, headers=headers, timeout=10)
    
    # Gestione graceful degli errori HTTP:
    # - 404: il prodotto non è nel database OpenFoodFacts (barcode sconosciuto)
    # - Altri errori: problemi di rete o server
    # NON usiamo raise_for_status() perché un 404 è un caso normale e atteso,
    # non un errore critico. L'agente deve ricevere un risultato vuoto e poterlo
    # comunicare all'utente, non crashare con un'eccezione.
    if response.status_code == 404:
        return ProductOutput(
            product_name=f"Prodotto con barcode {input_data.barcode} non trovato nel database OpenFoodFacts. Prova a stimare i valori nutrizionali manualmente."
        )
    
    if response.status_code != 200:
        return ProductOutput(
            product_name=f"Errore API OpenFoodFacts (HTTP {response.status_code}). Impossibile recuperare i dati del prodotto."
        )
    
    # Deserializza il corpo della risposta JSON in un dizionario Python
    data = response.json()
    
    # L'API restituisce status=1 se il prodotto è stato trovato; in caso contrario, ritorna un DTO descrittivo
    if data.get("status") != 1:
        return ProductOutput(
            product_name=f"Prodotto con barcode {input_data.barcode} non presente nel database OpenFoodFacts."
        )
        
    # Estrae il sotto-dizionario 'product' (con fallback su dict vuoto, programmazione difensiva)
    product_data = data.get("product", {})
    
    # Estrae il sotto-dizionario 'nutriments' contenente i valori macro e micro nutrizionali
    nutriments = product_data.get("nutriments", {})

    # Fallback a catena: OpenFoodFacts spesso lascia 'product_name' vuoto.
    # Prova varianti localizzate, poi nome generico, poi marca, infine il barcode.
    product_name = (
        product_data.get("product_name")
        or product_data.get("product_name_it")
        or product_data.get("product_name_en")
        or product_data.get("generic_name")
        or product_data.get("brands")
        or f"Prodotto {input_data.barcode}"
    )

    # Mappa individualmente i dati JSON nel modello Pydantic di risposta, usando .get() per prevenire KeyError
    return ProductOutput(
        product_name=product_name,
        energy_kcal_100g=nutriments.get("energy-kcal_100g"),
        proteins_100g=nutriments.get("proteins_100g"),
        carbohydrates_100g=nutriments.get("carbohydrates_100g"),
        fat_100g=nutriments.get("fat_100g")
    )
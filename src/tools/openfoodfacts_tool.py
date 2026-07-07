"""
Modulo di integrazione per l'API di Open Food Facts.

Gestisce le comunicazioni esterne per l'estrazione dei profili nutrizionali
partendo dalla lettura di un codice a barre standard (EAN).

Author: Stefano Bellan (20054330)
"""

# Strutture dati per la modellazione e validazione dei contratti I/O
from pydantic import BaseModel, Field
# Gestione dei tipi nullable per i campi opzionali del payload
from typing import Optional
# Client HTTP per le richieste REST verso il backend remoto
import requests
# Utilità di sistema per l'accesso dinamico alle variabili d'ambiente
import os

class BarcodeSearchInput(BaseModel):
    """
    Schema per validare l'input della richiesta del codice a barre.
    
    Author: Stefano Bellan (20054330)
    """
    # Identificativo EAN-13 ricavato dallo scanner
    barcode: str = Field(..., description="Il codice a barre numerico del prodotto (EAN-13).")

class ProductOutput(BaseModel):
    """
    Modello di risposta che incapsula i valori macro-nutrizionali estratti.
    
    Author: Stefano Bellan (20054330)
    """
    # Denominazione commerciale, resa opzionale per gestire eventuali mancanze nel DB
    product_name: Optional[str] = Field(None, description="Il nome del prodotto.")
    # Resa energetica espressa in kilocalorie per cento grammi
    energy_kcal_100g: Optional[float] = Field(None, description="Contenuto energetico in kcal per 100g.")
    # Quota proteica per cento grammi di riferimento
    proteins_100g: Optional[float] = Field(None, description="Grammi di proteine per 100g.")
    # Quota glucidica per cento grammi di riferimento
    carbohydrates_100g: Optional[float] = Field(None, description="Grammi di carboidrati per 100g.")
    # Quota lipidica per cento grammi di riferimento
    fat_100g: Optional[float] = Field(None, description="Grammi di grassi per 100g.")

def get_product_info_by_barcode(input_data: BarcodeSearchInput) -> ProductOutput:
    """
    Contatta il servizio di Open Food Facts per mappare un codice a barre sui suoi valori nutrizionali.
    
    Args:
        input_data (BarcodeSearchInput): Oggetto contenente il parametro di ricerca validato.
        
    Returns:
        ProductOutput: Struttura con i macro e i riferimenti energetici. In caso di errore o
        assenza di dati vengono restituiti campi vuoti per favorire la resilienza del flusso.

    Author: Stefano Bellan (20054330)
    """
    # Recupero dinamico del nome dell'applicazione per la formattazione dell'User-Agent
    app_name = os.getenv("OPENFOODFACTS_APP_NAME", "RepEats")
    
    # Le direttive di Open Food Facts richiedono un'intestazione esplicita per tracciare il traffico
    headers = {"User-Agent": f"{app_name} - Project University Version"}
    
    # Generazione dell'endpoint inserendo il parametro in modo sicuro
    url = f"https://world.openfoodfacts.org/api/v2/product/{input_data.barcode}.json"
    
    # Chiamata bloccante al servizio esterno con timeout preimpostato per non incastrare l'agente
    response = requests.get(url, headers=headers, timeout=10)
    
    # La gestione degli errori è progettata per non sollevare eccezioni che romperebbero il ciclo.
    # Restituendo uno stato gestibile in caso di 404 (assenza prodotto) o errori generici,
    # deleghiamo la risoluzione finale al sistema chiamante senza crash.
    if response.status_code == 404:
        return ProductOutput(
            product_name=f"Prodotto con barcode {input_data.barcode} non trovato nel database OpenFoodFacts. Prova a stimare i valori nutrizionali manualmente."
        )
    
    if response.status_code != 200:
        return ProductOutput(
            product_name=f"Errore API OpenFoodFacts (HTTP {response.status_code}). Impossibile recuperare i dati del prodotto."
        )
    
    # Parsing del payload JSON di risposta
    data = response.json()
    
    # Verifichiamo il flag di stato restituito dal backend prima di accedere ai nodi dati
    if data.get("status") != 1:
        return ProductOutput(
            product_name=f"Prodotto con barcode {input_data.barcode} non presente nel database OpenFoodFacts."
        )
        
    # Isoliamo il nodo radice garantendo una chiave di default per evitare crash
    product_data = data.get("product", {})
    
    # Estraiamo l'oggetto relativo alla sezione nutrizionale
    nutriments = product_data.get("nutriments", {})

    # Adottiamo una strategia a cascata per ricavare una stringa identificativa valida,
    # in quanto il servizio non assicura sempre la compilazione del nome base.
    product_name = (
        product_data.get("product_name")
        or product_data.get("product_name_it")
        or product_data.get("product_name_en")
        or product_data.get("generic_name")
        or product_data.get("brands")
        or f"Prodotto {input_data.barcode}"
    )

    # Cerchiamo di recuperare le kcal dirette. In molti record è presente unicamente
    # il valore espresso in joule, per cui effettuiamo una conversione matematica di fallback
    # per preservare la consistenza dei dati inoltrati allo scanner.
    energy_kcal = nutriments.get("energy-kcal_100g")
    if energy_kcal is None:
        energy_kj = nutriments.get("energy_100g")
        if energy_kj is not None:
            energy_kcal = round(energy_kj / 4.184, 1)

    # Riassegniamo i parametri estratti all'interno del modello finale in modo sicuro
    return ProductOutput(
        product_name=product_name,
        energy_kcal_100g=energy_kcal,
        proteins_100g=nutriments.get("proteins_100g"),
        carbohydrates_100g=nutriments.get("carbohydrates_100g"),
        fat_100g=nutriments.get("fat_100g")
    )
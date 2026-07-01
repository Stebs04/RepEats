"""
Modulo per l'integrazione con l'API di Open Food Facts.
Fornisce strumenti per il recupero dei dati nutrizionali tramite codice a barre (EAN).
Autore: Stefano Bellan (20054330)

"""

from pydantic import BaseModel, Field
from typing import Optional
import requests
import os

class BarcodeSearchInput(BaseModel):
    """Schema di validazione per la richiesta di ricerca tramite codice a barre."""
    barcode: str = Field(..., description="Il codice a barre numerico del prodotto (EAN-13).")
    weight_g: float = Field(100.0, description="La grammatura (peso in grammi) indicata dall'utente per cui calcolare i valori nutrizionali esatti.")

class ProductOutput(BaseModel):
    """Schema dei dati di output contenente i valori nutrizionali riproporzionati."""
    product_name: Optional[str] = Field(None, description="Il nome del prodotto trovato su OpenFoodFacts.")
    energy_kcal: Optional[float] = Field(None, description="Contenuto energetico in kcal, già riproporzionato per la grammatura richiesta.")
    proteins: Optional[float] = Field(None, description="Grammi di proteine, già riproporzionati per la grammatura richiesta.")
    carbohydrates: Optional[float] = Field(None, description="Grammi di carboidrati, già riproporzionati per la grammatura richiesta.")
    fats: Optional[float] = Field(None, description="Grammi di grassi, già riproporzionati per la grammatura richiesta.")

def safe_float(val, fallback=0.0):
    """Converte un valore in float in modo sicuro, ritornando un fallback se fallisce."""
    try:
        if val is None or str(val).strip() == "":
            return float(fallback)
        return float(val)
    except (ValueError, TypeError):
        return float(fallback)

def get_product_info_by_barcode(input_data: BarcodeSearchInput) -> ProductOutput:
    """
    Recupera le informazioni nutrizionali di un prodotto interrogando l'API di Open Food Facts
    e ricalcola i valori in base alla grammatura (weight_g) fornita in input.
    
    Args:
        input_data (BarcodeSearchInput): Il payload validato contenente il codice a barre e la grammatura.
        
    Returns:
        ProductOutput: I dati nutrizionali estratti e riproporzionati.

    Autore: Stefano Bellan (20054330)
    """
    app_name = os.getenv("OPENFOODFACTS_APP_NAME", "RepEats")
    headers = {"User-Agent": f"{app_name} - Project University Version"}
    url = f"https://world.openfoodfacts.org/api/v2/product/{input_data.barcode}.json"
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
    except requests.exceptions.RequestException:
        return ProductOutput(product_name=f"Errore di rete durante la connessione a OpenFoodFacts. Usa stima visiva.")

    if response.status_code == 404:
        return ProductOutput(
            product_name=f"Prodotto con barcode {input_data.barcode} non trovato. Usa la stima visiva dell'immagine."
        )
    
    if response.status_code != 200:
        return ProductOutput(
            product_name=f"Errore API OpenFoodFacts (HTTP {response.status_code}). Usa stima visiva."
        )
    
    data = response.json()
    
    if data.get("status") != 1:
        return ProductOutput(
            product_name=f"Prodotto con barcode {input_data.barcode} non presente nel database OpenFoodFacts. Usa stima visiva."
        )
        
    product_data = data.get("product", {})
    nutriments = product_data.get("nutriments", {})
    
    # 1. Ricerca del Nome (logica a cascata per massima affidabilità)
    name = (
        product_data.get("product_name_it") or 
        product_data.get("product_name") or 
        product_data.get("product_name_en") or 
        product_data.get("generic_name_it") or 
        product_data.get("generic_name") or 
        product_data.get("brands") or 
        "Prodotto Sconosciuto"
    )
    
    # 2. Parsing Valori per 100g con Fallback
    kcal_100g = safe_float(nutriments.get("energy-kcal_100g"))
    if kcal_100g == 0.0 and nutriments.get("energy_100g"):
        kcal_100g = safe_float(nutriments.get("energy_100g")) / 4.184
        
    proteins_100g = safe_float(nutriments.get("proteins_100g"), fallback=safe_float(nutriments.get("proteins_value")))
    carbs_100g = safe_float(nutriments.get("carbohydrates_100g"), fallback=safe_float(nutriments.get("carbohydrates_value")))
    fats_100g = safe_float(nutriments.get("fat_100g"), fallback=safe_float(nutriments.get("fat_value")))
    
    # 3. Ricalcolo Matematico Assoluto (Partizione/Maggiorazione)
    factor = input_data.weight_g / 100.0
    
    return ProductOutput(
        product_name=name,
        energy_kcal=round(kcal_100g * factor, 2),
        proteins=round(proteins_100g * factor, 2),
        carbohydrates=round(carbs_100g * factor, 2),
        fats=round(fats_100g * factor, 2)
    )
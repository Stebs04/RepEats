from pydantic import BaseModel, Field
from typing import Optional
import requests
import os

class BarcodeSearchInput(BaseModel):
    barcode: str = Field(..., description="Il codice a barre numerico del prodotto (EAN-13).")

class ProductOutput(BaseModel):
    product_name: Optional[str] = Field(None, description="Il nome del prodotto.")
    energy_kcal_100g: Optional[float] = Field(None, description="Contenuto energetico in kcal per 100g.")
    proteins_100g: Optional[float] = Field(None, description="Grammi di proteine per 100g.")
    carbohydrates_100g: Optional[float] = Field(None, description="Grammi di carboidrati per 100g.")
    fat_100g: Optional[float] = Field(None, description="Grammi di grassi per 100g.")

def get_product_info_by_barcode(input_data: BarcodeSearchInput) -> ProductOutput:
    app_name = os.getenv("OPENFOODFACTS_APP_NAME")
    headers = {"User-Agent": f"{app_name} - Project University Version"}
    url = f"https://world.openfoodfacts.org/api/v2/product/{input_data.barcode}.json"
    response = requests.get(url, headers=headers, timeout=10)
    response.raise_for_status()
    data = response.json
    if data.get("igi")
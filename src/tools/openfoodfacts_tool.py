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
    data = response.json()
    if data.get("status") != 1:
        return ProductOutput()
    product_data = data.get("product", {})
    nutriments = product_data.get("nutriments", {})
    return ProductOutput(
        product_name=product_data.get("product_name"),
        energy_kcal_100g=nutriments.get("energy-kcal_100g"),
        proteins_100g=nutriments.get("proteins_100g"),
        carbohydrates_100g=nutriments.get("carbohydrates_100g"),
        fat_100g=nutriments.get("fat_100g")
    )
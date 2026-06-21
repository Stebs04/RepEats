import asyncio
from src.agents.nutritionst import NutritionistAgent, MealAnalysis
from dotenv import load_dotenv
from agno.models.message import Image as AgnoImage

load_dotenv()

def main():
    agent = NutritionistAgent()
    prompt_agente = (
        f"Analizza accuratamente l'immagine del pasto o il codice a barre (usa gli strumenti a tua disposizione). "
        f"IMPORTANTE: L'utente ha indicato che la porzione consumata è di ESATTAMENTE 100 grammi. "
        f"Se usi lo strumento del codice a barre (che restituisce valori per 100g), DEVI FARE LA PROPORZIONE MATEMATICA per ricalcolare i valori su 100g. "
        "Restituisci ESCLUSIVAMENTE un oggetto JSON valido per lo schema MealAnalysis. Non aggiungere testo prima o dopo. "
        "DEVI restituire i dati seguendo rigorosamente lo schema MealAnalysis: "
        "name: estrai il nome del prodotto o un nome descrittivo. "
        f"analysis_result: una breve descrizione. Includi una frase del tipo 'Valori stimati per 100g'. "
        f"calories, proteins, carbohydrates, fats: solo numeri (i valori finali calcolati per 100g). "
        "NON aggiungere chiacchiere extra, rispondi solo con i dati strutturati."
    )
    print("Running agent with image...")
    # write a dummy image
    with open("dummy.jpg", "wb") as f:
        f.write(b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00\xff\xdb\x00\x43\x00\xff\xc0\x00\x0b\x08\x00\x01\x00\x01\x01\x01\x11\x00\xff\xc4\x00\x1f\x00\x00\x01\x05\x01\x01\x01\x01\x01\x01\x00\x00\x00\x00\x00\x00\x00\x00\x01\x02\x03\x04\x05\x06\x07\x08\t\n\x0b\xff\xda\x00\x08\x01\x01\x00\x00\x3f\x00\xd2\xcf\x20\xff\xd9")
    try:
        response = agent.run(prompt_agente, images=[AgnoImage(filepath="dummy.jpg")], response_model=MealAnalysis)
        print("Content:", repr(response.content))
        print("Type:", type(response.content))
    except Exception as e:
        print("Error:", e)

if __name__ == "__main__":
    main()

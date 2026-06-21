import asyncio
from src.agents.nutritionst import NutritionistAgent, MealAnalysis
from dotenv import load_dotenv

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
    print("Running agent...")
    try:
        response = agent.run(prompt_agente, response_model=MealAnalysis)
        print("Content:", repr(response.content))
        print("Type:", type(response.content))
    except Exception as e:
        print("Error:", e)

if __name__ == "__main__":
    main()

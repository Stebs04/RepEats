import asyncio
from src.agents.nutritionst import NutritionistAgent, MealAnalysis
from dotenv import load_dotenv

load_dotenv()

def main():
    agent = NutritionistAgent()
    print("Running agent...")
    try:
        response = agent.run("Hello, this is a test.", response_model=MealAnalysis)
        print("Content:", response.content)
    except Exception as e:
        print("Error:", e)

if __name__ == "__main__":
    main()

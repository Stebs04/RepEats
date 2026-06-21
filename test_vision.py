import asyncio
from agno.agent import Agent
from agno.models.groq import Groq
from dotenv import load_dotenv

load_dotenv()

def main():
    agent = Agent(model=Groq(id="llama-3.2-90b-vision-preview"))
    print("Running Groq vision agent...")
    try:
        response = agent.run("Hello, this is a test.")
        print("Content:", response.content)
    except Exception as e:
        print("Error:", e)

if __name__ == "__main__":
    main()

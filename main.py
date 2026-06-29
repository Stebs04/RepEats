from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse
import os
from dotenv import load_dotenv
from backend.auth import router as auth_router
from backend.chat_api import router as chat_router
from backend.dashboard_api import router as dashboard_router
from backend.profile_api import router as profile_router



# Caricamento configurazioni dal file .env
load_dotenv()

# Inizializziamo il database se non esiste!
from src.database.init_db import init_database
init_database()

# Inizializzazione dell'istanza principale FastAPI
app = FastAPI(title="RepEats API")

app.include_router(auth_router, prefix="/api/auth", tags=["Auth"])

app.include_router(chat_router, prefix="/api/chat", tags=["Chat AI"])
app.include_router(dashboard_router, prefix="/api/dashboard", tags=["Dashboard"])
app.include_router(profile_router, prefix="/api/profile", tags=["Profile"])



# Risoluzione del percorso assoluto per la directory degli asset statici
FRONTEND_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "frontend")

@app.get("/api/health")
def health_check():
    """Endpoint di health check per il monitoraggio del servizio."""
    return {"status": "ok", "message": "Il backend RepEats è attivo e funzionante!"}

@app.get("/")
def read_root():
    """Reindirizza la root dell'applicazione alla logica di smistamento frontend."""
    return RedirectResponse(url="/index.html", status_code=302)

# Montaggio della sottodirectory per l'erogazione dei file statici se presente nel file system
# NOTA: html=False per evitare che index.html venga servito come fallback per tutte le rotte,
# il che poteva causare conflitti con la logica di autenticazione nelle pagine.
if os.path.exists(FRONTEND_DIR):
    app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=False), name="frontend")
else:
    print("ATTENZIONE: Cartella 'frontend' non trovata!")
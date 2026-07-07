"""
Entry point principale dell'applicazione backend FastAPI.

Gestisce il bootstrap del server, la configurazione dei router,
l'inizializzazione delle connessioni persistenti e il mounting
del frontend statico.

Author: Stefano Bellan (20054330)
"""
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse
import os
from dotenv import load_dotenv
from backend.auth import router as auth_router
from backend.chat_api import router as chat_router
from backend.dashboard_api import router as dashboard_router
from backend.profile_api import router as profile_router



# Iniezione delle variabili d'ambiente nel contesto di esecuzione corrente
load_dotenv()

# Validazione della connessione al database relazionale.
# Il provisioning dello schema è ora interamente governato dalle migrazioni Alembic,
# evitando collisioni strutturali a runtime durante il bootstrap.
from src.database.init_db import init_database
init_database()

# Sincronizzazione a freddo del vector store RAG.
# Il modulo di ingestione riconcilia lo stato del file system con gli indici
# vettoriali applicando una strategia differenziale per ottimizzare i tempi di avvio.
from src.knowledge_base.ingest import sync
sync()

# Bootstrap dell'istanza ASGI principale
app = FastAPI(title="RepEats API")

app.include_router(auth_router, prefix="/api/auth", tags=["Auth"])

app.include_router(chat_router, prefix="/api/chat", tags=["Chat AI"])
app.include_router(dashboard_router, prefix="/api/dashboard", tags=["Dashboard"])
app.include_router(profile_router, prefix="/api/profile", tags=["Profile"])



# Risoluzione canonica del path per l'erogazione dei file statici front-end
FRONTEND_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "frontend")

@app.get("/api/health")
def health_check():
    """
    Sonda diagnostica per le architetture di orchestrazione e monitoraggio uptime.
    
    Author: Stefano Bellan (20054330)
    """
    return {"status": "ok", "message": "Il backend RepEats è attivo e funzionante!"}

@app.get("/")
def read_root():
    """
    Risoluzione della rotta base mediante redirect verso l'entrypoint della SPA.
    
    Author: Stefano Bellan (20054330)
    """
    return RedirectResponse(url="/index.html", status_code=302)

# Configurazione del file server statico subordinata all'esistenza della directory.
# L'inibizione del mapping automatico su index.html previene interferenze 
# collaterali con le policy di reindirizzamento imposte dai layer di autenticazione.
if os.path.exists(FRONTEND_DIR):
    app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=False), name="frontend")
else:
    print("ATTENZIONE: Cartella 'frontend' non trovata!")
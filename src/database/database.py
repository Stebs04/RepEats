import os
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Inizializza il modulo caricando le variabili d'ambiente necessarie dal file .env.
# Questo permette di centralizzare la configurazione senza esporre credenziali nel codice sorgente.
load_dotenv()

def get_database_url() -> str:
    """
    Recupera l'URL di connessione al database dalle variabili d'ambiente.
    Solleva un'eccezione in caso di assenza, applicando il principio fail-fast
    per impedire l'avvio dell'applicazione con una configurazione invalida.
    Autori: Stefano Bellan, Timothy Giolito
    """
    # Ottiene la stringa di connessione (es. postgresql://user:pass@host/db)
    db_url = os.getenv("DATABASE_URL")
    
    # Verifica critica: se la variabile d'ambiente non è impostata, interrompe l'esecuzione.
    if not db_url:
        raise ValueError("ERRORE CRITICO: Variabile d'ambiente DATABASE_URL non definita nel file .env!")
    
    return db_url


def get_engine():
    """
    Istanzia e restituisce il motore (engine) di SQLAlchemy, che costituisce
    il layer di base per la gestione del pool di connessioni al database.
    Autori: Stefano Bellan, Timothy Giolito
    """
    # Recupera l'URL validato dalla funzione dedicata
    db_url = get_database_url()
    
    # Crea l'engine. Il parametro echo=True è utile in fase di sviluppo/debug
    # in quanto esegue il logging a terminale di tutte le query SQL generate.
    # In produzione, si consiglia di impostare echo=False o gestirlo tramite una variabile d'ambiente.
    engine = create_engine(db_url, echo=True)
    
    return engine


def get_session():
    """
    Crea e restituisce una nuova sessione per interagire con il database tramite ORM.
    Le sessioni fungono da 'holding zone' per tutti gli oggetti caricati o associati
    al database durante una transazione.
    Autori: Stefano Bellan, Timothy Giolito
    """
    # Ottiene l'engine inizializzato
    engine = get_engine()
    
    # Utilizza la factory sessionmaker per configurare le nuove sessioni
    # e le collega (bind) all'engine precedentemente creato.
    SessionLocal = sessionmaker(bind=engine)
    
    # Istanzia una sessione pronta all'uso per l'esecuzione di query
    return SessionLocal()

"""
Modulo per il provisioning della connessione al datastore relazionale.

Author: Timothy Giolito (20054431)
"""
import os
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Bootstrap del modulo ambientale per l'iniezione sicura delle credenziali a runtime
load_dotenv()

def get_database_url() -> str:
    """
    Risoluzione della URI di connessione al datastore.
    Implementa una policy fail-fast bloccante in assenza di parametri critici.
    
    Author: Timothy Giolito (20054431)
    """
    # Parsing della stringa di connessione dal layer ambientale
    db_url = os.getenv("DATABASE_URL")
    
    # Validazione vincolante del puntatore al cluster
    if not db_url:
        raise ValueError("ERRORE CRITICO: Variabile d'ambiente DATABASE_URL non definita nel file .env!")
    
    return db_url


def get_engine():
    """
    Factory per l'engine ORM SQLAlchemy.
    Inizializza il connection pool primario garantendo la gestione concorrenziale dei thread.
    
    Author: Timothy Giolito (20054431)
    """
    # Acquisizione DSN validata
    db_url = get_database_url()
    
    # Allocazione dell'engine con statement logging esplicito
    engine = create_engine(db_url, echo=True)
    
    return engine


def get_session():
    """
    Istanziazione di un generatore di unit-of-work per le transazioni ORM.
    Produce factory bound all'engine primario per l'isolamento transazionale.
    
    Author: Timothy Giolito (20054431)
    """
    # Recupero pool di connessione attivo
    engine = get_engine()
    
    # Binding della factory transazionale all'istanza ORM
    SessionLocal = sessionmaker(bind=engine)
    
    # Generazione sessione operativa standard
    return SessionLocal()

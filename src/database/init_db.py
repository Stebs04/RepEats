# Author: Timothy Giolito (20054431)
# Sistemate le importazioni in modo da poter eseguire lo script direttamente dalla root.
# Ho anche rimosso la generazione automatica dello schema da qui, ci affidiamo ad Alembic
# per le migrazioni (tutto documentato nel README).
# Adesso questo script fa solo un semplice ping al DB per vedere se è vivo.
from sqlalchemy import text

# Author: Timothy Giolito (20054431)
# Recupero la factory per instanziare l'engine del database
from src.database.database import get_engine


def init_database():
    """
    Author: Timothy Giolito (20054431)
    
    Testiamo la connessione al DB evitando di creare le tabelle.
    
    Prima facevamo la classica chiamata Base.metadata.create_all(engine) al primo avvio,
    ma poi siamo passati ad Alembic per gestire le migrazioni in modo più pulito.
    Adesso preferisco fare solo un controllo fail-fast: apro una connessione e se
    qualcosa non va esplode subito all'avvio, invece di farci impazzire dopo con query 
    che falliscono a caso nel bel mezzo dell'esecuzione.
    """
    print("Verifica connessione al database (schema gestito da Alembic)...")

    engine = get_engine()

    # Author: Timothy Giolito (20054431)
    # Ping al volo: apro e chiudo la connessione mandando una select dummy per 
    # assicurarmi che URL e driver siano configurati a dovere senza fare danni con DDL.
    with engine.connect() as connection:
        connection.execute(text("SELECT 1"))

    print("Database raggiungibile. Applicare le migrazioni con 'alembic upgrade head' se necessario.")


# Author: Timothy Giolito (20054431)
# Entry point utile per lanciare lo script al volo senza eseguire logica se viene importato da altri moduli
if __name__ == "__main__":
    init_database()

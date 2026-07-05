# modified by Stefano Bellan 20054330 - Correzione importazioni assolute per esecuzione da radice progetto
# La creazione dello schema NON avviene piu' qui: la gestione delle tabelle e'
# ora delegata ad Alembic (vedi cartella alembic/ e sezione "Gestione Database"
# del README). Questo modulo si limita a verificare la raggiungibilita' del DB.
from sqlalchemy import text
# Importa la funzione factory per ottenere l'istanza dell'engine del database
from src.database.database import get_engine


def init_database():
    """
    Verifica la connettivita' al database SENZA crearne lo schema.

    Storicamente questa funzione eseguiva Base.metadata.create_all(engine),
    creando implicitamente le tabelle al primo avvio. La creazione/evoluzione
    dello schema e' ora responsabilita' di Alembic (`alembic upgrade head`),
    per avere migrazioni versionate e riproducibili. Qui eseguiamo solo un
    controllo di raggiungibilita' fail-fast, cosi' un DB non configurato viene
    segnalato all'avvio invece di fallire piu' avanti durante le query.

    Autori: Stefano Bellan, Timothy Giolito
    """
    print("Verifica connessione al database (schema gestito da Alembic)...")

    engine = get_engine()

    # Apertura e chiusura immediata di una connessione: valida URL/driver e
    # raggiungibilita' del DB senza emettere alcuna istruzione DDL.
    with engine.connect() as connection:
        connection.execute(text("SELECT 1"))

    print("Database raggiungibile. Applicare le migrazioni con 'alembic upgrade head' se necessario.")


# Entry point locale: protegge da esecuzioni accidentali in caso il modulo venga solo importato altrove
if __name__ == "__main__":
    init_database()

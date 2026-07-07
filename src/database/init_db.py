# Author: Timothy Giolito (20054431)
# Sistemate le importazioni in modo da poter eseguire lo script direttamente dalla root.
# Ho anche rimosso la generazione automatica dello schema da qui, ci affidiamo ad Alembic
# per le migrazioni (tutto documentato nel README).
# Al primo avvio (tabella alembic_version assente) le migrazioni vengono applicate
# automaticamente; ai successivi avvii si fa solo un ping di connettività.
import os

from sqlalchemy import inspect, text

# Author: Timothy Giolito (20054431)
# Recupero la factory per instanziare l'engine del database
from src.database.database import get_engine


def _needs_first_run_migration(engine) -> bool:
    """
    Author: Timothy Giolito (20054431)

    Determina se il database necessita della migrazione iniziale.
    
    Controlla l'esistenza della tabella 'alembic_version': se manca, il DB
    è vergine e le migrazioni non sono mai state applicate.
    """
    inspector = inspect(engine)
    return "alembic_version" not in inspector.get_table_names()


def _run_alembic_upgrade():
    """
    Author: Timothy Giolito (20054431)
    
    Esegue 'alembic upgrade head' programmaticamente senza bisogno della CLI.
    
    Utilizza le API Python di Alembic per applicare tutte le migrazioni
    pendenti, puntando al file alembic.ini nella root del progetto.
    """
    from alembic.config import Config
    from alembic import command

    # Risale alla root del progetto (due livelli sopra src/database/)
    project_root = os.path.dirname(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    )
    alembic_cfg = Config(os.path.join(project_root, "alembic.ini"))

    print("Applicazione migrazioni Alembic (upgrade head)...")
    command.upgrade(alembic_cfg, "head")
    print("Migrazioni applicate con successo.")


def init_database():
    """
    Author: Timothy Giolito (20054431)
    
    Bootstrap del database con rilevamento automatico del primo avvio.
    
    Al primo avvio (tabella alembic_version assente) esegue automaticamente
    'alembic upgrade head' per creare lo schema completo. Ai successivi avvii
    verifica soltanto che il DB sia raggiungibile (fail-fast).
    """
    print("Verifica connessione al database (schema gestito da Alembic)...")

    engine = get_engine()

    # Author: Timothy Giolito (20054431)
    # Ping al volo: apro e chiudo la connessione mandando una select dummy per 
    # assicurarmi che URL e driver siano configurati a dovere senza fare danni con DDL.
    with engine.connect() as connection:
        connection.execute(text("SELECT 1"))

    # Al primo avvio le migrazioni vengono applicate automaticamente;
    # ai successivi avvii questo blocco viene saltato.
    if _needs_first_run_migration(engine):
        print("Primo avvio rilevato: tabella alembic_version non trovata.")
        _run_alembic_upgrade()
    else:
        print("Database raggiungibile e già inizializzato.")


# Author: Timothy Giolito (20054431)
# Entry point utile per lanciare lo script al volo senza eseguire logica se viene importato da altri moduli
if __name__ == "__main__":
    init_database()

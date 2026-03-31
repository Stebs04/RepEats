# Importa la funzione factory per ottenere l'istanza dell'engine del database
from database import get_engine
# Importa la classe Base dichiarativa di SQLAlchemy che contiene il registro di tutti i modelli
from models import Base

def init_database():
    """
    Inizializza lo schema del database creando fisicamente le tabelle definite nei modelli ORM.
    Questa funzione dovrebbe essere invocata al primo avvio dell'applicativo.
    
    Autori: Stefano Bellan, Timothy Giolito
    """
    # Stampa a terminale che l'operazione di creazione dello schema è iniziata
    print("Iniziando la creazione dello schema del database...")
    
    # Ottiene l'oggetto Engine che funge da interfaccia centrale verso il database e ne gestisce il connection pool
    engine = get_engine()
    
    # Attraverso la classe Base, si recuperano i metadati dei modelli registrati 
    # per tradurli ed inviare al DBMS le corrispondenti istruzioni DDL (es. CREATE TABLE).
    # Il metodo create_all crea in modo sicuro solo le tabelle non ancora esistenti.
    Base.metadata.create_all(engine)
    
    # Conferma testuale della corretta terminazione dell'operazione
    print("Database e tabelle creati con successo!")

# Entry point locale: protegge da esecuzioni accidentali in caso il modulo venga solo importato altrove
if __name__ == "__main__":
    init_database()
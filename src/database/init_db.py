from sqlalchemy import create_engine
from models import Base

def init_database():
    db_url = 'sqlite:///repeats_database.db'
    engine = create_engine(db_url, echo=True)
    print("Iniziando la creazione dello schema del database...")
    Base.metadata.create_all(engine)
    print("Database e tabelle creati con successo!")

if __name__ == "__main__":
    init_database()
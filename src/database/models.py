from sqlalchemy import create_engine, Column, Integer, String, Float, ForeignKey, DateTime, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, sessionmaker
from datetime import datetime, timezone

# Classe base dichiarativa da cui ereditano tutti i modelli ORM.
# Fornisce il mapping automatico tra le classi Python e le tabelle del database.
Base = declarative_base()

class User(Base):
    """
    Modello che rappresenta un account utente all'interno del sistema.
    Gestisce l'autenticazione di base e le associazioni con i dati di profilo e le conversazioni.
    
    Autori: Stefano Bellan, Timothy Giolito
    """
    __tablename__ = 'users'
    
    # Chiave primaria: identificatore univoco autoincrementante per l'utente.
    id = Column(Integer, primary_key=True, autoincrement=True)
    
    # Credenziali e dati di base: obbligatori e univoci.
    username = Column(String(50), unique=True, nullable=False)
    email = Column(String(100), unique=True, nullable=False)
    
    # Timestamp di creazione. Viene utilizzata una lambda per assicurare che il valore
    # di datetime.now(timezone.utc) venga calcolato dinamicamente al momento dell'inserimento,
    # anziché al momento del caricamento del modulo.
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    # Relazione 1-a-1: collega l'utente al suo profilo dettagliato.
    # uselist=False indica a SQLAlchemy di caricare una singola istanza (non una collezione).
    profile = relationship("UserProfile", back_populates="user", uselist=False)
    
    # Relazione 1-a-N: collega l'utente a tutte le sue cronologie di conversazione.
    conversations = relationship("Conversation", back_populates="user")

  # NUOVA RELAZIONE: collega l'utente ai suoi pasti registrati
    meal_logs = relationship("MealLog", back_populates="user", cascade="all, delete-orphan")

    def __repr__(self):
        """Rappresentazione testuale dell'oggetto, utile in fase di debugging."""
        return f"<User(username='{self.username}')>"
    
class UserProfile(Base):
    """
    Modello che raccoglie i dati biometrici e gli obiettivi di fitness dell'utente.
    Queste informazioni arricchiscono l'entità User principale.
    
    Autori: Stefano Bellan, Timothy Giolito
    """
    __tablename__ = 'user_profiles'
    
    # Chiave primaria del profilo.
    id = Column(Integer, primary_key=True)
    
    # Chiave esterna per la relazione col modello User.
    # nullable=False impone l'integrità referenziale: non esiste profilo senza un utente associato.
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    
    # Dati descrittivi e misurazioni fisiche.
    age = Column(Integer)
    weight = Column(Float)  # Memorizzato in chilogrammi (kg).
    height = Column(Float)  # Memorizzato in centimetri (cm).
    
    #Peso Ideale che l'utente vuole raggiungere
    target_weight = Column(Float)
    #Tipo di obiettivo che l'utente si è posto
    goal_type = Column(String(50))
    
    # Back-reference alla proprietà profile di User. 
    # Mantiene coerenza nella navigazione bidirezionale in memoria.
    user = relationship("User", back_populates="profile")

class Conversation(Base):
    """
    Modello che rappresenta una singola sessione logica di chat tra l'utente e il sistema assistente.
    Raggruppa strutturalmente una sequenza temporale di messaggi.
    
    Autori: Stefano Bellan, Timothy Giolito
    """
    __tablename__ = 'conversations'
    
    # Identificatore univoco per l'istanza della conversazione.
    id = Column(Integer, primary_key=True)
    
    # Collegamento referenziale forte all'utente che ha generato la conversazione.
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    
    # Metadati descrittivi visibili nell'interfaccia utente.
    title = Column(String(200), default="Nuova Conversazione")
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    # Relazione definita verso il modello genitore.
    user = relationship("User", back_populates="conversations")
    
    # Relazione 1-a-N verso la cronologia dei messaggi scambiati (modello Message).
    # Configurazione di cascade "all, delete-orphan": assicura che se una Conversations
    # viene rimossa, i record associati nella tabella Message vengano conseguentemente
    # cancellati dal database senza creare record orfani.
    messages = relationship("Message", back_populates="conversation", cascade="all, delete-orphan")

class Message(Base):
    """
    Modello che memorizza una singola iterazione comunicativa testuale.
    Funziona come unit of work basilare per la cronologia della conversazione.
    
    Autori: Stefano Bellan, Timothy Giolito
    """
    __tablename__ = 'messages'
    
    # Definizione univoca del singolo record-messaggio.
    id = Column(Integer, primary_key=True)
    
    # Associazione obbligatoria alla sessione di appartenenza (conversations).
    conversation_id = Column(Integer, ForeignKey('conversations.id'), nullable=False)
    
    # Classificazione dell'attore (es. 'user' per input umano, 'assistant' per l'elaborazione AI).
    role = Column(String(20), nullable=False)
    
    # Payload effettivo, supporta lunga persistenza del testo tramite column Text.
    content = Column(Text, nullable=False)
    
    # Registrazione temporale accurata dell'interazione.
    timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    # Definizione inversa della correlazione ORM con l'oggetto Conversation.
    conversation = relationship("Conversation", back_populates="messages")

    
    
class MealLog(Base):
    """
    Modello che memorizza le analisi nutrizionali effettuate dall'agente Nutrizionista.
    Consente di mantenere uno storico dei pasti per ogni utente.
    Autore: Stefano Bellan (20054330)
    """

    __tablename__ = 'meal_logs'

    #Chiave primaria
    id = Column(Integer, primary_key=True)

    #Foreign Key che lo collega alla tabella degli utenti
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)

    #Campo per l'analisi
    analysis_result = Column(Text, nullable=False)

    # --- NUOVI CAMPI PER I MACRONUTRIENTI (Valori strutturati) ---
    calories = Column(Float, nullable=True)
    proteins = Column(Float, nullable=True)
    carbohydrates = Column(Float, nullable=True)
    fats = Column(Float, nullable=True)

    #Data e ora dell'analisi
    timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    #Relazione inversa verso User
    user = relationship("User", back_populates="meal_logs")
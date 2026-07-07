from sqlalchemy import create_engine, Column, Integer, String, Float, ForeignKey, DateTime, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, sessionmaker

# Author: Timothy Giolito (20054431)
# Ho rimosso l'importazione di timezone perché causava problemi di compatibilità con SQLite.
# Per ora ci basta importare datetime base per gestire i timestamp senza complicarci la vita.
from datetime import datetime

# Author: Timothy Giolito (20054431)
# Questa è la classe base dichiarativa. La usiamo per far ereditare tutti i nostri modelli ORM,
# in modo che SQLAlchemy sappia come mappare automaticamente le classi in tabelle sul database.
Base = declarative_base()

class User(Base):
    """
    Author: Timothy Giolito (20054431)
    
    Questo modello rappresenta l'utente nel nostro sistema.
    Lo usiamo per salvare le credenziali di base e per fare da ponte tra il profilo 
    dettagliato dell'utente e tutte le sue interazioni (come le conversazioni o i log dei pasti).
    """
    __tablename__ = 'users'
    
    # Author: Timothy Giolito (20054431)
    # Identificativo univoco per ogni utente, lo facciamo incrementare da solo
    id = Column(Integer, primary_key=True, autoincrement=True)
    
    # Author: Timothy Giolito (20054431)
    # Dati essenziali per il login, entrambi obbligatori e unici
    username = Column(String(50), unique=True, nullable=False)
    email = Column(String(100), unique=True, nullable=False)

    # Author: Timothy Giolito (20054431)
    # Ovviamente ci salviamo solo l'hash della password per questioni di sicurezza
    password_hash = Column(String(255), nullable=False)
    
    # Author: Timothy Giolito (20054431)
    # Ho usato una lambda qui per registrare la data di creazione.
    # In questo modo datetime.now() viene chiamato esattamente quando inseriamo il record 
    # e non quando Python legge questo file, altrimenti avremmo timestamp tutti sballati.
    created_at = Column(DateTime, default=lambda: datetime.now())

    # Author: Timothy Giolito (20054431)
    # Qui colleghiamo l'utente al suo profilo fisico. Impostando uselist a False
    # diciamo a SQLAlchemy che c'è una relazione stretta 1 a 1, non una lista di profili.
    profile = relationship("UserProfile", back_populates="user", uselist=False)
    
    # Author: Timothy Giolito (20054431)
    # Lista delle chat salvate da questo utente
    conversations = relationship("Conversation", back_populates="user")

    # Author: Timothy Giolito (20054431)
    # Relazione con lo storico dei pasti. Se cancelliamo l'utente facciamo pulizia 
    # di tutti i suoi log grazie a delete-orphan
    meal_logs = relationship("MealLog", back_populates="user", cascade="all, delete-orphan")

    def __repr__(self):
        """
        Author: Timothy Giolito (20054431)
        
        Una rapida rappresentazione testuale, torna sempre utile quando stampo l'oggetto per debug.
        """
        return f"<User(username='{self.username}')>"
    
class UserProfile(Base):
    """
    Author: Timothy Giolito (20054431)
    
    Questo modello espande l'utente con tutti i suoi dati biometrici e obiettivi di fitness.
    Ci serve per tenere traccia delle misurazioni senza ingolfare la tabella principale.
    """
    __tablename__ = 'user_profiles'
    
    # Author: Timothy Giolito (20054431)
    # Chiave primaria standard per il profilo
    id = Column(Integer, primary_key=True)
    
    # Author: Timothy Giolito (20054431)
    # Riferimento rigido all'utente proprietario: non ha senso che esista un profilo scollegato
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    
    # Author: Timothy Giolito (20054431)
    # Dati fisici di base, peso in chili e altezza in centimetri
    age = Column(Integer)
    weight = Column(Float)
    height = Column(Float)
    
    # Author: Timothy Giolito (20054431)
    # Valori necessari per il calcolo del metabolismo basale e consumo energetico totale
    gender = Column(String(10), default="uomo")
    activity_level = Column(Float, default=1.55)
    
    # Author: Timothy Giolito (20054431)
    # Dettagli sugli obiettivi dell'utente: quanto peso vuole raggiungere, in quanto tempo,
    # la natura dell'obiettivo, e le sue preferenze per le schede di allenamento
    target_weight = Column(Float)
    target_weeks = Column(Integer, default=12)
    goal_type = Column(String(50))
    workout_duration = Column(Integer, default=60)
    workout_preference = Column(String(100), default="Ipertrofia")

    # Author: Timothy Giolito (20054431)
    # Campi di testo libero per segnarsi eventuali allergie o scelte dietetiche particolari
    allergies = Column(String(500), default="")
    dietary_preferences = Column(String(500), default="")

    # Author: Timothy Giolito (20054431)
    # Riferimento inverso per poter accedere comodamente all'utente partendo dal profilo
    user = relationship("User", back_populates="profile")

class Conversation(Base):
    """
    Author: Timothy Giolito (20054431)
    
    Questo modello fa da contenitore per una chat tra l'utente e il sistema.
    Serve a tenere raggruppati in ordine cronologico tutti i messaggi scambiati in una singola sessione.
    """
    __tablename__ = 'conversations'
    
    # Author: Timothy Giolito (20054431)
    # Id univoco della conversazione
    id = Column(Integer, primary_key=True)
    
    # Author: Timothy Giolito (20054431)
    # Riferimento all'utente che ha avviato questa sessione
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    
    # Author: Timothy Giolito (20054431)
    # Un titolo di cortesia da mostrare sulla UI, con un fallback se l'utente non lo imposta
    title = Column(String(200), default="Nuova Conversazione")
    
    # Author: Timothy Giolito (20054431)
    # Distingue se stiamo parlando col nutrizionista o col coach, così filtriamo bene sulla frontend
    chat_type = Column(String(50), default="nutritionist", nullable=False)
    
    # Author: Timothy Giolito (20054431)
    # Stesso discorso di prima per il timestamp dinamico alla creazione
    created_at = Column(DateTime, default=lambda: datetime.now())

    # Author: Timothy Giolito (20054431)
    # Riferimento all'oggetto utente proprietario
    user = relationship("User", back_populates="conversations")
    
    # Author: Timothy Giolito (20054431)
    # Tutti i messaggi di questa chat. Anche qui usiamo delete-orphan così 
    # se cestiniamo la chat spazziamo via in automatico anche i suoi messaggi
    messages = relationship("Message", back_populates="conversation", cascade="all, delete-orphan")

class Message(Base):
    """
    Author: Timothy Giolito (20054431)
    
    Singolo messaggio scambiato all'interno di una conversazione.
    """
    __tablename__ = 'messages'
    
    # Author: Timothy Giolito (20054431)
    # Identificativo di questo specifico messaggio
    id = Column(Integer, primary_key=True)
    
    # Author: Timothy Giolito (20054431)
    # Chat a cui questo messaggio appartiene obbligatoriamente
    conversation_id = Column(Integer, ForeignKey('conversations.id'), nullable=False)
    
    # Author: Timothy Giolito (20054431)
    # Ci dice chi ha scritto: se è un input umano o la risposta del bot
    role = Column(String(20), nullable=False)
    
    # Author: Timothy Giolito (20054431)
    # Il corpo del messaggio vero e proprio, uso Text perché può essere bello lungo
    content = Column(Text, nullable=False)
    
    # Author: Timothy Giolito (20054431)
    # Salvo esattamente l'istante in cui il messaggio è stato registrato
    timestamp = Column(DateTime, default=lambda: datetime.now())

    # Author: Timothy Giolito (20054431)
    # Legame inverso verso l'oggetto della conversazione madre
    conversation = relationship("Conversation", back_populates="messages")
    
class MealLog(Base):
    """
    Author: Timothy Giolito (20054431)
    
    Storico delle valutazioni nutrizionali richieste dall'utente.
    Ogni volta che il nutrizionista analizza un pasto, ci salviamo tutto qui.
    """

    __tablename__ = 'meal_logs'

    # Author: Timothy Giolito (20054431)
    # Identificatore del singolo log
    id = Column(Integer, primary_key=True)

    # Author: Timothy Giolito (20054431)
    # Utente che ha effettuato l'analisi
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)

    # Author: Timothy Giolito (20054431)
    # Risultato grezzo dell'analisi testuale
    analysis_result = Column(Text, nullable=False)

    # Author: Timothy Giolito (20054431)
    # Valori macro strutturati: nome della pietanza e ripartizione esatta per facilitare le statistiche
    name = Column(String(200), nullable=True)
    calories = Column(Float, nullable=True)
    proteins = Column(Float, nullable=True)
    carbohydrates = Column(Float, nullable=True)
    fats = Column(Float, nullable=True)
    
    # Author: Timothy Giolito (20054431)
    # In che momento della giornata è stato consumato
    category = Column(String(50), nullable=True)

    # Author: Timothy Giolito (20054431)
    # Data di salvataggio del pasto calcolata in tempo reale
    timestamp = Column(DateTime, default=lambda: datetime.now())

    # Author: Timothy Giolito (20054431)
    # Riferimento inverso al modello User
    user = relationship("User", back_populates="meal_logs")

class WorkoutPlan(Base):
    """
    Author: Timothy Giolito (20054431)
    
    Rappresenta una scheda di allenamento intera suggerita dal personal trainer virtuale.
    """
    __tablename__ = 'workout_plans'
    
    # Author: Timothy Giolito (20054431)
    # Identificativo univoco della scheda
    id = Column(Integer, primary_key=True, autoincrement=True)
    
    # Author: Timothy Giolito (20054431)
    # Riferimento all'utente per cui è stata creata la scheda
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    
    # Author: Timothy Giolito (20054431)
    # Un nome descrittivo della scheda per ritrovarla al volo
    name = Column(String(200), nullable=False)
    
    # Author: Timothy Giolito (20054431)
    # Data di creazione della scheda
    created_at = Column(DateTime, default=lambda: datetime.now())
    
    # Author: Timothy Giolito (20054431)
    # Relazioni: verso l'utente e verso la lista di esercizi, gestendo l'eliminazione a cascata
    user = relationship("User", backref="workout_plans")
    exercises = relationship("WorkoutExercise", back_populates="plan", cascade="all, delete-orphan")

class WorkoutExercise(Base):
    """
    Author: Timothy Giolito (20054431)
    
    Questa classe modella il singolo esercizio dentro una scheda di allenamento.
    Contiene tutti i dettagli operativi per faticare in palestra.
    """
    __tablename__ = 'workout_exercises'
    
    # Author: Timothy Giolito (20054431)
    # Id di base per questo singolo blocco di esercizio
    id = Column(Integer, primary_key=True, autoincrement=True)
    
    # Author: Timothy Giolito (20054431)
    # Collega l'esercizio alla sua scheda di riferimento
    plan_id = Column(Integer, ForeignKey('workout_plans.id'), nullable=False)
    
    # Author: Timothy Giolito (20054431)
    # Quale esercizio fare e su quale muscolo focalizzarsi
    name = Column(String(200), nullable=False)
    muscle_group = Column(String(100), nullable=True)
    
    # Author: Timothy Giolito (20054431)
    # Serie, ripetizioni (testo perché potrebbe essere roba tipo "a cedimento") e tempo di recupero
    sets = Column(Integer, nullable=False)
    reps = Column(String(50), nullable=False)
    rest_time = Column(String(50), nullable=True)
    
    # Author: Timothy Giolito (20054431)
    # In che ordine eseguire gli esercizi durante l'allenamento
    order_index = Column(Integer, default=0)
    
    # Author: Timothy Giolito (20054431)
    # Il puntatore inverso verso la scheda principale
    plan = relationship("WorkoutPlan", back_populates="exercises")
from sqlalchemy.orm import Session
from src.database.models import User, UserProfile, Conversation, Message
from src.database.database import get_session

"""
Creazione e recupero del profilo dell'utente, con i dati personali e gli obiettivi di fitness.
Gestisce la creazione di nuovi utenti, l'aggiornamento dei profili esistenti e il recupero dei dati degli utenti da DB.
Autore: Timothy Giolito 20054431

"""
def get_all_users():
    """Recupero dal DB di tutti gli utenti registrati"""
    session = get_session()
    users = session.query(User).all()
    session.close()
    return users


def create_user(username: str, email: str):
    """Creazione  di un nuovo utente nel DB"""
    session = get_session()
    new_user = User(username = username, email = email)
    session.add(new_user)
    session.commit()

    """"A questo punto è necessario creare un profilo vuoto associato al nuovo utente"""
    profile = UserProfile(user_id = new_user.id)
    session.add(profile)
    session.commit()

    session.refresh(new_user)
    session.close()
    
    return new_user


"""Dopo aver creato un nuovo utente e un nuovo profilo, bisogna aggiornare i dati inerenti a quell'utente"""
def update_user_profile(user_id: int, weight: float, height: float, age: int, goals: str):

    session = get_session()
    profile = session.query(UserProfile).filter_by(user_id = user_id).first()

    if profile: 
        profile.weight = weight
        profile.height = height
        profile.age = age
        profile.fitness_goals = goals
        session.commit()
    session.close()

"""Recupero dei dati di uno specifico utente"""
def get_user_data(user_id: int):
    
    """Recupera il profilo completo dell'utente specificato"""
    session = get_session()
    user = session.query(User).filter_by(id=user_id).first()
    data = {
        "username": user.username,
        "weight": user.profile.weight,
        "height": user.profile.height,
        "age": user.profile.age,
        "goals": user.profile.fitness_goals
    }
    session.close()
    return data


def get_user_conversations(user_id: int):

    """Recupero di tutte le conversazioni associate a un utente specifico"""
    session = get_session()
    convs = session.query(Conversation).filter_by(user_id=user_id).order_by(Conversation.created_at.desc()).all()
    session.close()
    return convs


def create_new_conversation(user_id: int, title: str = "Nuova conversazione"):

    """Crea una nuova sessione per ogni chat"""
    session = get_session()
    new_conv = Conversation(user_id=user_id, title=title)
    session.add(new_conv)
    session.commit()
    session.refresh(new_conv)
    session.close()
    return new_conv


def save_message(conversation_id: int, role: str, content: str):
    
    """Salva un singolo messaggio (utente o assistente) nel DB."""
    session = get_session()
    new_msg = Message(conversation_id=conversation_id, role=role, content=content)
    session.add(new_msg)
    session.commit()
    session.close()

def get_chat_history(conversation_id: int):
    
    """Recupera la cronologia messaggi di una specifica conversazione."""
    session = get_session()
    messages = session.query(Message).filter_by(conversation_id=conversation_id).order_by(Message.timestamp.asc()).all()
    history = [{"role": m.role, "content": m.content} for m in messages]
    session.close()
    return history
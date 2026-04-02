from sqlalchemy.orm import Session
from src.database.models import User, UserProfile, Conversation, Message, MealLog
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
def update_user_profile(user_id: int, weight: float, height: float, age: int, target_weight: float, goal_type: str):

    session = get_session()
    profile = session.query(UserProfile).filter_by(user_id = user_id).first()

    if profile: 
        profile.weight = weight
        profile.height = height
        profile.age = age
        profile.target_weight = target_weight
        profile.goal_type = goal_type
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
        "target_weight": user.profile.target_weight,
        "goal_type": user.profile.goal_type
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

def save_meal_log(user_id: int, analysis_result: str, calories: float = None, proteins: float = None, carbs: float = None, fats: float = None):
    """
    Salva il log dell'analisi di un pasto nel database associandolo a uno specifico utente.

    La funzione crea un nuovo record `MealLog` contenente i risultati dell'analisi 
    e i valori nutrizionali (calorie e macronutrienti) calcolati, per poi persisterlo
    tramite la sessione del database.

    Args:
        user_id (int): L'ID univoco dell'utente che ha registrato il pasto.
        analysis_result (str): L'esito testuale dell'analisi effettuata sul pasto.
        calories (float, opzionale): Valore calorico stimato. Default a None.
        proteins (float, opzionale): Grammi stimati di proteine. Default a None.
        carbs (float, opzionale): Grammi stimati di carboidrati. Default a None.
        fats (float, opzionale): Grammi stimati di grassi. Default a None.

    Returns:
        None

    Autore: Stefano Bellan (20054330)
    """
    # Ottiene un'istanza della sessione del database
    session = get_session()
    
    # Istanzia un nuovo log popolando i campi del modello MealLog
    new_log = MealLog(
        user_id = user_id,
        analysis_result = analysis_result, 
        calories = calories,
        proteins = proteins,
        carbohydrates= carbs,
        fats = fats
    )

    # Aggiunge il nuovo record alla transazione e lo salva permanentemente sul database
    session.add(new_log)
    session.commit()
    
    # Chiude la sessione per rilasciare le connessioni al database
    session.close()

def calculate_daily_macros(user_id: int):
    """
    Calcola i macro-nutrienti e il fabbisogno calorico giornaliero di un utente 
    in base alle proprie metriche biometriche e agli obiettivi di fitness.
    Autore: Stefano Bellan (20054330)
    """
    # Recupera il profilo dell'utente (dati biometrici e obiettivi) dal database
    user_data = get_user_data(user_id)

    # Se mancano i dati fondamentali, restituiamo valori a zero per evitare il crash
    if not user_data or not user_data['weight'] or not user_data['height'] or not user_data['age']:
        return {
            "tdee": 0,
            "target_calories": 0,
            "proteins": 0,
            "fats": 0,
            "carbohydrates": 0
        }
    
    # Calcola il Metabolismo Basale (BMR) utilizzando l'equazione di Mifflin-St Jeor (permette di stimare le calorie consumate a riposo)
    bmr = (10 * user_data['weight'] + (6.25 * user_data['height']) - (5 * user_data['age']))
    
    # Calcola il Dispendio Energetico Totale Giornaliero (TDEE) moltiplicando il BMR per un fattore di attività stimato standard (PAL = 1.55, attività moderata)
    tdee = bmr * 1.55
    
    # Imposta le calorie target inziali pari al livello di mantenimento energetico (TDEE)
    target_calories = tdee
    
    # Applica un deficit calorico di 500 kcal per facilitare la perdita di grasso corporeo (fase di cut)
    if user_data['goal_type'] == 'dimagrimento':
        target_calories = target_calories - 500
    # Applica un surplus calorico di 300 kcal per facilitare l'ipertrofia e l'aumento di massa muscolare (fase di bulk)
    elif user_data['goal_type'] == 'massa':
         target_calories = target_calories + 300
         
    # Calcola il fabbisogno proteico in base al peso corporeo (fissato a 2.0g per kg per preservare/costruire massa magra)
    proteins = user_data['weight'] * 2.0
    
    # Calcola il fabbisogno lipidico in base al peso corporeo (fissato a 0.9g per kg per un corretto apporto ormonale)
    fats = user_data['weight'] * 0.9
    
    # Calcola le calorie rimanenti per i carboidrati decurtando le calorie di proteine (4 kcal/g) e grassi (9 kcal/g)
    remaining_calories = target_calories - (proteins * 4.0) - (fats * 9.0)
    
    # Converte le calorie rimanenti in grammi di carboidrati (4 kcal per grammo)
    carbohydrates = remaining_calories / 4.0
    
    # Restituisce il dizionario come payload con i valori arrotondati a 1 cifra decimale per un'esperienza UI pulita
    return {
        "tdee": round(tdee, 1),
        "target_calories": round(target_calories, 1),
        "proteins": round(proteins, 1),
        "fats": round(fats, 1),
        "carbohydrates": round(carbohydrates, 1)
    }

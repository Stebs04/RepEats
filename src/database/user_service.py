from sqlalchemy.orm import Session
from src.database.models import User, UserProfile, Conversation, Message, MealLog
from src.database.database import get_session
from sqlalchemy import func
from datetime import datetime, timezone

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
def update_user_profile(user_id: int, weight: float, height: float, age: int, gender: str, activity_level: float, target_weight: float, target_weeks: int, goal_type: str):

    session = get_session()
    profile = session.query(UserProfile).filter_by(user_id = user_id).first()

    if profile: 
        profile.weight = weight
        profile.height = height
        profile.age = age
        profile.gender = gender
        profile.activity_level = activity_level
        profile.target_weight = target_weight 
        profile.target_weeks = target_weeks
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
        "gender": user.profile.gender or "uomo",
        "activity_level": user.profile.activity_level or 1.55,
        "target_weight": user.profile.target_weight,
        "target_weeks": user.profile.target_weeks or 12,
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

def save_meal_log(user_id: int, analysis_result: str, category: str = None, name: str = None, calories: float = None, proteins: float = None, carbs: float = None, fats: float = None):
    """
    Salva il log dell'analisi di un pasto nel database associandolo a uno specifico utente e categoria.

    La funzione crea un nuovo record `MealLog` contenente i risultati dell'analisi,
    il nome associativo, la categoria del pasto, e i valori nutrizionali (calorie e macronutrienti) calcolati, 
    per poi persisterlo tramite la sessione del database.

    Args:
        user_id (int): L'ID univoco dell'utente che ha registrato il pasto.
        analysis_result (str): L'esito testuale dell'analisi effettuata sul pasto.
        category (str, opzionale): Categoria del pasto (es. Colazione, Pranzo). Default a None.
        name (str, opzionale): Nome identificativo o marchio del prodotto. Default a None.
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
        category = category,
        name = name,
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
    Calcola i macro-nutrienti e il fabbisogno calorico giornaliero completo di un utente 
    in base alle proprie metriche biometriche (peso, altezza, età e genere) 
    e ai ritmi metabolici personali tramite formula Mifflin-St Jeor.
    
    Su richiesta, il calcolo delle calorie target, dei macro e la ripartizione pasti 
    sono basati ESCLUSIVAMENTE sul TDEE (nessun deficit o surplus applicato), 
    mantenendo solo le proporzioni dei macro in base all'obiettivo.
    
    Autore: Stefano Bellan (20054330)
    """
    # Recupera il profilo dell'utente (dati biometrici, identificativi e obiettivi) dal database
    user_data = get_user_data(user_id)

    # Se mancano i dati fondamentali preventivi, restituiamo un pacchetto a zero per ovviare ad errori Null Pointer 
    if not user_data or not user_data['weight'] or not user_data['height'] or not user_data['age']:
        return {
            "tdee": 0,
            "target_calories": 0,
            "proteins": 0,
            "fats": 0,
            "carbohydrates": 0
        }
    
    # Esegue formula basale base indipendente Mifflin-St Jeor = 10*Weight + 6.25*Height - 5*Age
    bmr_base = (10 * user_data['weight']) + (6.25 * user_data['height']) - (5 * user_data['age'])
    
    # Applica l'aggiustamento genere specifico richiesto dalla formula di riferimento scientifico
    if user_data.get('gender', 'uomo') == 'uomo':
        # Offset per maschi (+5 costante fissa fisiologica)
        bmr = bmr_base + 5
    else:
        # Offset per femmine (-161 costante fissa per incidenza adiposa biologica)
        bmr = bmr_base - 161
    
    # Determina il LAF (Livello Attività Fisica) moltiplicatore prelevato o fallback default 1.55 (Moderate) 
    activity_multiplier = float(user_data.get('activity_level', 1.55))
    
    # Calcola il Dispendio Energetico Totale Giornaliero (TDEE) moltiplicando il BMR con il LAF dell'utente
    tdee = bmr * activity_multiplier
    
    # Inizializza l'obiettivo attuale dell'utente
    goal = user_data.get('goal_type', 'mantenimento')
    
    # Imposta le calorie target in modo che siano SEMPRE rigorosamente uguali al TDEE
    target_calories = tdee
    
    # Scompone i percorsi nutrizionali utilizzando le percentuali calcolate sul TDEE
    if goal == 'dimagrimento':
        # Percentuali per preservare massa muscolare (35% Pro, 25% Fat, 40% Carbs)
        perc_pro = 0.35
        perc_fat = 0.25
        perc_carbs = 0.40
    elif goal == 'massa':
         # Percentuali per la crescita muscolare (25% Pro, 25% Fat, 50% Carbs)
         perc_pro = 0.25
         perc_fat = 0.25
         perc_carbs = 0.50
    else:
        # Formule di normomantenimento atletico e bilanciato (25% Pro, 30% Fat, 45% Carbs)
        perc_pro = 0.25
        perc_fat = 0.30
        perc_carbs = 0.45
         
    # Calcolo dei macronutrienti basato ESCLUSIVAMENTE sul TDEE (target_calories)
    # (Proteine = 4 kcal/g, Grassi = 9 kcal/g, Carboidrati = 4 kcal/g)
    proteins = (target_calories * perc_pro) / 4.0
    fats = (target_calories * perc_fat) / 9.0
    carbohydrates = (target_calories * perc_carbs) / 4.0
    
    # Restituisce il dizionario payload: le calorie target saranno ora identiche al TDEE
    return {
        "tdee": round(tdee, 1),
        "target_calories": round(target_calories, 1),
        "proteins": round(proteins, 1),
        "fats": round(fats, 1),
        "carbohydrates": round(carbohydrates, 1)
    }

def get_todays_macros(user_id: int):
    """
    Calcola e restituisce la somma totale dei macronutrienti e delle calorie assunte da un utente nella giornata odierna.
    Autore: Stefano Bellan (20054330)
    """
    # Ottiene un'istanza della sessione del database
    session = get_session()
    
    # Recupera la data odierna nel fuso orario UTC
    today_date = datetime.now(timezone.utc).date()
    
    # Esegue una query per calcolare la somma di calorie, proteine, grassi e carboidrati
    somma_macro = session.query(
        func.sum(MealLog.calories),
        func.sum(MealLog.proteins),
        func.sum(MealLog.fats),
        func.sum(MealLog.carbohydrates)
    ).filter(
        # Filtra i record associati allo specifico utente
        MealLog.user_id == user_id,
        # Filtra i log relativi esclusivamente alla data odierna
        func.date(MealLog.timestamp) == today_date
    ).first()
    
    # Chiude la sessione per rilasciare le risorse
    session.close()
    
    # Restituisce un dizionario con i totali, gestendo il caso di valori nulli (es. nessun pasto registrato)
    return {
        "calories": somma_macro[0] or 0,
        "proteins": somma_macro[1] or 0,
        "fats": somma_macro[2] or 0, 
        "carbohydrates": somma_macro[3] or 0
    }

def get_meals_by_category(user_id: int, category: str):
    """
    Recupera tutti i log dei pasti corrispondenti a una specifica categoria per un determinato utente.
    
    Questa funzione interroga il database per estrarre lo storico dei pasti (MealLog)
    filtrandoli per l'identificativo dell'utente e per la categoria desiderata (es. 'Colazione', 'Pranzo', ecc.).
    I risultati vengono restituiti in ordine cronologico decrescente, dal pasto più recente al più vecchio.

    Args:
        user_id (int): L'identificativo univoco dell'utente.
        category (str): La stringa che rappresenta la categoria del pasto da cercare.

    Returns:
        list: Una lista di oggetti MealLog che corrispondono ai criteri di validazione inseriti.

    Autore: Stefano Bellan (20054330)
    """
    # Ottiene un'istanza della sessione per interagire con il database in modo sicuro
    session = get_session()
    
    # Inizializza la query sul modello MealLog e applica i filtri necessari
    meals = session.query(MealLog).filter(
        # Verifica la corrispondenza esatta con l'identificativo dell'utente
        MealLog.user_id == user_id,
        # Verifica la corrispondenza esatta con la categoria di pasto richiesta
        MealLog.category == category
    ).order_by(
        # Ordina l'intero set di risultati per data/ora in ordine decrescente (timestamp)
        MealLog.timestamp.desc()
    ).all() # Esegue materialmente la query restituendo tutti i record trovati come lista
    
    # Chiude la sessione di lavoro, rilasciando così le risorse e la connessione al database
    session.close()
    
    # Restituisce la lista di oggetti (pasti) popolata e formattata precedentemente
    return meals

def delete_meal_log(user_id: int, meal_id: int) -> bool:
    """
    Elimina un record specifico relativo a un pasto registrato (MealLog) dal database.
    
    Questa funzione interroga il database per trovare un pasto specifico tramite il suo ID
    e verifica che appartenga effettivamente all'utente specificato per garantire la sicurezza.
    Se il record esiste e i controlli sono superati, procede con la rimozione permanente,
    aggiornando lo stato del database.

    Args:
        user_id (int): L'identificativo univoco dell'utente che richiede la cancellazione.
        meal_id (int): L'identificativo univoco del log del pasto da eliminare.

    Returns:
        bool: True se il pasto è stato trovato ed eliminato con successo, False altrimenti.

    Autore: Stefano Bellan (20054330)
    """
    # Ottiene un'istanza della sessione per comunicare attivamente con il database
    session = get_session()
    
    # Esegue una query mirata alla tabella MealLog applicando i filtri necessari
    meal_to_delete = session.query(MealLog).filter(
        # Filtra i risultati ricercando l'esatta corrispondenza con l'ID del pasto
        MealLog.id == meal_id,
        # Filtra i risultati assicurandosi che il proprietario sia l'utente indicato
        MealLog.user_id == user_id
    ).first() # Estrae l'unico record atteso, oppure None se inesistente
    
    # Valuta se la query precedente ha restituito un oggetto valido
    if meal_to_delete:
        # Segnala alla sessione l'intenzione di marcare l'oggetto per l'eliminazione
        session.delete(meal_to_delete)
        # Esegue fisicamente la transazione sul database, confermando la cancellazione
        session.commit()
        # Chiude la connessione e rilascia la memoria associata alla sessione
        session.close()
        # Ritorna valore booleano positivo comunicando il corretto esito dell'azione
        return True
    
    # Nel caso in cui l'oggetto non sia stato trovato, procediamo a liberare le risorse
    session.close()
    
    # Ritorna valore booleano negativo indicando il fallimento della procedura
    return False


def rename_conversation(conversation_id: int, new_title: str):
    """
    Rinomina una conversazione esistente nel database.
    """
    session = get_session()
    conv = session.query(Conversation).filter_by(id=conversation_id).first()
    if conv:
        conv.title = new_title
        session.commit()
    session.close()

def delete_conversation(conversation_id: int):
    """
    Elimina una conversazione e (tramite cascade) tutti i suoi messaggi.
    """
    session = get_session()
    conv = session.query(Conversation).filter_by(id=conversation_id).first()
    if conv:
        session.delete(conv)
        session.commit()
    session.close()
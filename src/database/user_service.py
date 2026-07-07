from sqlalchemy.orm import Session
from src.database.models import User, UserProfile, Conversation, Message, MealLog, WorkoutPlan, WorkoutExercise
from src.database.database import get_session
from sqlalchemy import func
from datetime import datetime, timezone, date
import bcrypt

"""
Author: Timothy Giolito (20054431)

Questo modulo gestisce l'intera logica di accesso ai dati per gli utenti.
Ci occupiamo della registrazione di nuovi account, dell'aggiornamento dei profili fisici 
e del recupero di tutte le informazioni necessarie per la dashboard, dalle chat ai log dei pasti.
"""
def get_all_users():
    """
    Author: Timothy Giolito (20054431)
    
    Tira giù dal database l'elenco completo di tutti gli utenti registrati a sistema.
    """
    session = get_session()
    users = session.query(User).all()
    session.close()
    return users


def create_user(username: str, email: str, password: str):
    """
    Author: Timothy Giolito (20054431)
    
    Crea un nuovo account nel database preoccupandosi di hashare correttamente la password.
    """
    session = get_session()
    
    # Author: Timothy Giolito (20054431)
    # Generiamo un salt casuale e lo usiamo per calcolare l'hash della password
    salt = bcrypt.gensalt()
    hashed_password = bcrypt.hashpw(password.encode('utf-8'), salt)
    
    # Author: Timothy Giolito (20054431)
    # Creiamo l'entità utente salvando solo la versione cryptata (decodificata in stringa per il db)
    new_user = User(
        username=username, 
        email=email, 
        password_hash=hashed_password.decode('utf-8')
    )
    session.add(new_user)
    session.commit()

    # Author: Timothy Giolito (20054431)
    # Per evitare problemi di coerenza relazionale, prepariamo subito un profilo vuoto
    profile = UserProfile(user_id=new_user.id)
    session.add(profile)
    session.commit()

    session.refresh(new_user)
    session.close()
    
    return new_user


# Author: Timothy Giolito (20054431)
# Servizio che si occupa di popolare e aggiornare i dati biometrici del profilo utente
def update_user_profile(user_id: int, weight: float, height: float, age: int, gender: str, activity_level: float, target_weight: float, target_weeks: int, goal_type: str, workout_duration: int = 60, workout_preference: str = "Ipertrofia", allergies: str = None, dietary_preferences: str = None):

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
        profile.workout_duration = workout_duration
        profile.workout_preference = workout_preference
        profile.allergies = allergies or ""
        profile.dietary_preferences = dietary_preferences or ""
        session.commit()
    session.close()

# Author: Timothy Giolito (20054431)
# Funzione per estrarre tutti i dettagli di un singolo utente incrociando User e UserProfile
def get_user_data(user_id: int):
    
    """
    Author: Timothy Giolito (20054431)
    
    Recupera l'utente richiesto e impacchetta le sue info in un dizionario comodo per la logica applicativa.
    """
    session = get_session()
    user = session.query(User).filter_by(id=user_id).first()

    if not user:
        session.close()
        return None

    profile = user.profile
    data = {
        "user_id": user_id,
        "username": user.username,
        "weight": profile.weight if profile else None,
        "height": profile.height if profile else None,
        "age": profile.age if profile else None,
        "gender": (profile.gender if profile else None) or "uomo",
        "activity_level": (profile.activity_level if profile else None) or 1.55,
        "target_weight": profile.target_weight if profile else None,
        "target_weeks": (profile.target_weeks if profile else None) or 12,
        "goal_type": profile.goal_type if profile else None,
        "workout_duration": (profile.workout_duration if profile else None) or 60,
        "workout_preference": (profile.workout_preference if profile else None) or "Ipertrofia",
        "allergies": (profile.allergies if profile else None) or "",
        "dietary_preferences": (profile.dietary_preferences if profile else None) or ""
        }
    session.close()
    return data


def get_user_conversations(user_id: int, chat_type: str = None):

    """
    Author: Timothy Giolito (20054431)
    
    Cerca nel database tutte le sessioni di chat attive per l'utente, 
    dandoci la possibilità di filtrare per assistente specifico.
    """
    session = get_session()
    query = session.query(Conversation).filter_by(user_id=user_id)
    if chat_type:
        query = query.filter(Conversation.chat_type == chat_type)
    convs = query.order_by(Conversation.created_at.desc()).all()
    session.close()
    return convs


def create_new_conversation(user_id: int, title: str = "Nuova conversazione", chat_type: str = "nutritionist"):

    """
    Author: Timothy Giolito (20054431)
    
    Inizializza una nuova chat nel database da associare a uno specifico bot.
    """
    session = get_session()
    new_conv = Conversation(user_id=user_id, title=title, chat_type=chat_type)
    session.add(new_conv)
    session.commit()
    session.refresh(new_conv)
    session.close()
    return new_conv


def save_message(conversation_id: int, role: str, content: str):
    
    """
    Author: Timothy Giolito (20054431)
    
    Mette a registro il singolo messaggio scambiato all'interno di una sessione.
    """
    session = get_session()
    new_msg = Message(conversation_id=conversation_id, role=role, content=content)
    session.add(new_msg)
    session.commit()
    session.close()

def get_chat_history(conversation_id: int):
    
    """
    Author: Timothy Giolito (20054431)
    
    Estrae lo storico cronologico di tutti i messaggi per ricostruire a schermo l'intera conversazione.
    """
    session = get_session()
    messages = session.query(Message).filter_by(conversation_id=conversation_id).order_by(Message.timestamp.asc()).all()
    history = [{"role": m.role, "content": m.content} for m in messages]
    session.close()
    return history

def save_meal_log(user_id: int, analysis_result: str, category: str = None, name: str = None, calories: float = None, proteins: float = None, carbs: float = None, fats: float = None):
    """
    Author: Timothy Giolito (20054431)

    Registra l'esito dell'analisi nutritiva eseguita dal nostro modello sul pasto dell'utente.
    Mi occupo di inserire a database sia la risposta di testo estesa sia i macronutrienti stimati 
    che ci tornano comodi dopo per fare statistiche.
    """
    # Author: Timothy Giolito (20054431)
    # Recuperiamo la sessione pulita
    session = get_session()
    
    # Author: Timothy Giolito (20054431)
    # Prepopoliamo l'oggetto del log con i valori calcolati 
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

    # Author: Timothy Giolito (20054431)
    # Confermiamo l'inserimento
    session.add(new_log)
    session.commit()
    
    # Author: Timothy Giolito (20054431)
    # Ricordiamoci sempre di rilasciare la connessione
    session.close()

def calculate_daily_macros(user_id: int):
    """
    Author: Timothy Giolito (20054431)
    
    Questa funzione calcola il fabbisogno energetico dell'utente applicando la Mifflin-St Jeor.
    Utilizziamo peso, altezza ed età per avere il BMR e poi lo moltiplichiamo per lo stile di vita.
    Attualmente ci manteniamo direttamente sul TDEE senza fare deficit o surplus, 
    ma ripartiamo i macro percentualmente in base all'obiettivo di fitness scelto dall'utente.
    """
    # Author: Timothy Giolito (20054431)
    # Tiro fuori tutti i dati per avere a disposizione i fattori fisici necessari
    user_data = get_user_data(user_id)

    # Author: Timothy Giolito (20054431)
    # Se il profilo non è ancora compilato del tutto restituisco zeri per evitare crash più a valle
    if not user_data or not user_data['weight'] or not user_data['height'] or not user_data['age']:
        return {
            "tdee": 0,
            "target_calories": 0,
            "proteins": 0,
            "fats": 0,
            "carbohydrates": 0,
            "target_proteins": 0,
            "target_fats": 0,
            "target_carbohydrates": 0
        }
    
    # Author: Timothy Giolito (20054431)
    # Base di partenza del metabolismo
    bmr_base = (10 * user_data['weight']) + (6.25 * user_data['height']) - (5 * user_data['age'])
    
    # Author: Timothy Giolito (20054431)
    # Calibrazione specifica sul sesso biologico
    if user_data.get('gender', 'uomo') == 'uomo':
        # Offset maschile
        bmr = bmr_base + 5
    else:
        # Offset femminile
        bmr = bmr_base - 161
    
    # Author: Timothy Giolito (20054431)
    # Moltiplicatore sull'attività sportiva, di base lo metto su un generico 1.55 se manca
    activity_multiplier = float(user_data.get('activity_level', 1.55))
    
    # Author: Timothy Giolito (20054431)
    # Calcolo del TDEE finale
    tdee = bmr * activity_multiplier
    
    # Author: Timothy Giolito (20054431)
    # Controlliamo l'obiettivo salvato nel profilo
    goal = user_data.get('goal_type', 'mantenimento')
    
    # Author: Timothy Giolito (20054431)
    # Mappiamo le calorie obiettivo sul dispendio giornaliero calcolato
    target_calories = tdee
    
    # Author: Timothy Giolito (20054431)
    # Setup delle percentuali a seconda dell'obiettivo 
    if goal == 'dimagrimento':
        perc_pro = 0.35
        perc_fat = 0.25
        perc_carbs = 0.40
    elif goal == 'massa':
         perc_pro = 0.25
         perc_fat = 0.25
         perc_carbs = 0.50
    else:
        perc_pro = 0.25
        perc_fat = 0.30
        perc_carbs = 0.45
         
    # Author: Timothy Giolito (20054431)
    proteins = (target_calories * perc_pro) / 4.0
    fats = (target_calories * perc_fat) / 9.0
    carbohydrates = (target_calories * perc_carbs) / 4.0

    # Author: Timothy Giolito (20054431)
    categories_split = {"Colazione": 0.20, "Pranzo": 0.35, "Cena": 0.35, "Spuntino": 0.10}
    targets_by_category = {cat: {"calories": round(target_calories * perc, 1), "proteins": round(proteins * perc, 1), "fats": round(fats * perc, 1), "carbohydrates": round(carbohydrates * perc, 1)} for cat, perc in categories_split.items()}

    # Author: Timothy Giolito (20054431)
    return {"tdee": round(tdee, 1), "target_calories": round(target_calories, 1), "proteins": round(proteins, 1), "fats": round(fats, 1), "carbohydrates": round(carbohydrates, 1), "target_proteins": round(proteins, 1), "target_fats": round(fats, 1), "target_carbohydrates": round(carbohydrates, 1), "targets_by_category": targets_by_category}

def get_macros_by_date(user_id: int, target_date: date | None = None):
    """
    Author: Timothy Giolito (20054431)
    
    Somma tutti i valori nutrizionali dei pasti registrati dall'utente nella data richiesta.
    Comodo per far vedere le progress bar aggiornate a schermo. Se omettiamo la data prende oggi.
    """
    # Author: Timothy Giolito (20054431)
    # Apertura sessione
    session = get_session()

    # Author: Timothy Giolito (20054431)
    # Fallback sulla data di oggi se chi chiama la funzione non ci passa nulla di specifico
    if target_date is None:
        target_date = datetime.now(timezone.utc).date()

    # Author: Timothy Giolito (20054431)
    # Chiedo direttamente al db di fare la somma tramite func.sum così è molto più veloce
    somma_macro = session.query(
        func.sum(MealLog.calories),
        func.sum(MealLog.proteins),
        func.sum(MealLog.fats),
        func.sum(MealLog.carbohydrates)
    ).filter(
        MealLog.user_id == user_id,
        func.date(MealLog.timestamp) == target_date
    ).first()
    
    # Author: Timothy Giolito (20054431)
    # Chiusura della connessione
    session.close()
    
    # Author: Timothy Giolito (20054431)
    # Ritorniamo i totali mettendo 0 al posto di None se non ci sono dati
    return {
        "calories": somma_macro[0] or 0,
        "proteins": somma_macro[1] or 0,
        "fats": somma_macro[2] or 0, 
        "carbohydrates": somma_macro[3] or 0
    }

def get_meals_by_category(user_id: int, category: str):
    """
    Author: Timothy Giolito (20054431)
    
    Raccoglie dal database tutti i pasti mangiati da questo utente in una certa categoria temporale,
    ad esempio tutte le 'Colazioni'. Ordiniamo dal più recente al più vecchio in modo da mostrare
    i risultati migliori in cima.
    """
    # Author: Timothy Giolito (20054431)
    # Avviamo la sessione al DB
    session = get_session()
    
    # Author: Timothy Giolito (20054431)
    # Costruiamo la query impostando il filtro utente e categoria e gestendo l'ordinamento
    meals = session.query(MealLog).filter(
        MealLog.user_id == user_id,
        MealLog.category == category
    ).order_by(
        MealLog.timestamp.desc()
    ).all()
    
    # Author: Timothy Giolito (20054431)
    # Liberiamo le risorse
    session.close()
    
    # Author: Timothy Giolito (20054431)
    # Torniamo la lista
    return meals

def delete_meal_log(user_id: int, meal_id: int) -> bool:
    """
    Author: Timothy Giolito (20054431)
    
    Rimuove fisicamente il record di un pasto. Faccio un controllo incrociato con l'ID utente
    per stare sereni che nessuno possa cancellare il pasto di qualcun altro per sbaglio o per malizia.
    """
    # Author: Timothy Giolito (20054431)
    # Connessione al database
    session = get_session()
    
    # Author: Timothy Giolito (20054431)
    # Estraggo il pasto ricercato e mi assicuro che il proprietario coincida
    meal_to_delete = session.query(MealLog).filter(
        MealLog.id == meal_id,
        MealLog.user_id == user_id
    ).first()
    
    # Author: Timothy Giolito (20054431)
    # Se esiste la referenza, la procediamo alla cancellazione
    if meal_to_delete:
        session.delete(meal_to_delete)
        session.commit()
        session.close()
        return True
    
    # Author: Timothy Giolito (20054431)
    # Rilascio sessione nel caso la query abbia fallito e ritorno False
    session.close()
    return False


def rename_conversation(conversation_id: int, new_title: str):
    """
    Author: Timothy Giolito (20054431)
    
    Applica un nuovo titolo a una chat esistente nel db.
    """
    session = get_session()
    conv = session.query(Conversation).filter_by(id=conversation_id).first()
    if conv:
        conv.title = new_title
        session.commit()
    session.close()

def delete_conversation(conversation_id: int):
    """
    Author: Timothy Giolito (20054431)
    
    Fa tabula rasa di un'intera sessione di chat. Grazie alla logica a cascata 
    ci porta via automaticamente anche tutti i messaggi collegati.
    """
    session = get_session()
    conv = session.query(Conversation).filter_by(id=conversation_id).first()
    if conv:
        session.delete(conv)
        session.commit()
    session.close()

def authenticate_user(username: str, password: str):
    """
    Author: Timothy Giolito (20054431)
    
    Risolve il login controllando l'esistenza dell'utente e matchando l'hash della password.
    """
    session = get_session()
    user = session.query(User).filter_by(username=username).first()
    session.close()
    
    # Author: Timothy Giolito (20054431)
    # Se trovo l'utente valido il check cryptato con bcrypt per vedere se è tutto a posto
    if user and bcrypt.checkpw(password.encode('utf-8'), user.password_hash.encode('utf-8')):
        return user
    
    return None

def save_workout_plan(user_id: int, plan_name: str, exercises: list):
    """
    Author: Timothy Giolito (20054431)
    
    Salva sul database una scheda d'allenamento pulita prodotta dal nostro coach.
    Scorre la lista degli esercizi passata come dizionario e popola la tabella dedicata agganciando 
    tutto all'ID della nuova scheda creata.
    """
    session = get_session()
    new_plan = WorkoutPlan(user_id=user_id, name=plan_name)
    session.add(new_plan)
    session.flush()
    
    for idx, ex in enumerate(exercises):
        new_ex = WorkoutExercise(
            plan_id=new_plan.id,
            name=ex.get('name', 'Esercizio'),
            muscle_group=ex.get('muscle_group', ''),
            sets=ex.get('sets', 3),
            reps=str(ex.get('reps', '10')),
            rest_time=str(ex.get('rest_time', '90s')),
            order_index=idx
        )
        session.add(new_ex)

    session.commit()
    session.close()

def get_macros_breakdown_by_category(user_id: int, target_date: date | None = None):
    """
    Author: Timothy Giolito (20054431)

    Aggrega i macronutrienti consumati dall'utente nella data richiesta spaccandoli per fascia
    alimentare (Colazione, Pranzo, Cena, Spuntino), così l'AI sa cosa manca per ogni pasto.
    """
    session = get_session()
    if target_date is None: target_date = datetime.now(timezone.utc).date()
    risultati = session.query(MealLog.category, func.sum(MealLog.calories), func.sum(MealLog.proteins), func.sum(MealLog.fats), func.sum(MealLog.carbohydrates)).filter(MealLog.user_id == user_id, func.date(MealLog.timestamp) == target_date).group_by(MealLog.category).all()
    session.close()

    breakdown = {cat: {"calories": 0, "proteins": 0, "fats": 0, "carbohydrates": 0} for cat in ["Colazione", "Pranzo", "Cena", "Spuntino"]}
    for row in risultati:
        cat = row[0] if row[0] else "Sconosciuto"
        if cat in breakdown: breakdown[cat] = {"calories": row[1] or 0, "proteins": row[2] or 0, "fats": row[3] or 0, "carbohydrates": row[4] or 0}
    return breakdown

def get_user_workout_plans(user_id: int):
    """
    Author: Timothy Giolito (20054431)
    
    Cerca nel database lo storico di tutte le schede prodotte per un utente, con annessi esercizi,
    strutturandole comodamente per chi dovrà smontarle sul frontend.
    """
    session = get_session()
    plans = session.query(WorkoutPlan).filter_by(user_id=user_id).order_by(WorkoutPlan.created_at.desc()).all()
    
    # Author: Timothy Giolito (20054431)
    # Aggreghiamo il tutto in una lista di dizionari comoda
    result = []
    for plan in plans:
        exercises = session.query(WorkoutExercise).filter_by(plan_id=plan.id).order_by(WorkoutExercise.order_index.asc()).all()
        plan_dict = {
            "id": plan.id,
            "name": plan.name,
            "created_at": plan.created_at.isoformat(),
            "exercises": [
                {
                    "id": ex.id,
                    "name": ex.name,
                    "muscle_group": ex.muscle_group,
                    "sets": ex.sets,
                    "reps": ex.reps,
                    "rest_time": ex.rest_time
                } for ex in exercises
            ]
        }
        result.append(plan_dict)
        
    session.close()
    return result

def delete_workout_plan(user_id: int, plan_id: int) -> bool:
    """
    Author: Timothy Giolito (20054431)
    
    Cancella una scheda fitness specifica controllando che colui che fa la richiesta ne sia
    davvero il proprietario, onde evitare pasticci e intrusioni.
    """
    session = get_session()
    plan = session.query(WorkoutPlan).filter_by(id=plan_id, user_id=user_id).first()
    
    if plan:
        session.delete(plan)
        session.commit()
        session.close()
        return True
        
    session.close()
    return False

def update_workout_plan_by_id(user_id: int, plan_id: int, plan_name: str, exercises: list) -> bool:
    """
    Author: Timothy Giolito (20054431)
    
    Punto di ingresso per modificare a mano una scheda di allenamento dall'interfaccia.
    Andiamo a cercare la scheda per ID, controlliamo i permessi dell'utente, aggiorniamo il nome 
    e per far prima svuotiamo e reinseriamo brutalmente tutti gli esercizi aggiornati 
    anziché fare delta complicati.
    """
    session = get_session()
    plan = session.query(WorkoutPlan).filter_by(id=plan_id, user_id=user_id).first()

    if not plan:
        session.close()
        return False

    plan.name = plan_name

    # Author: Timothy Giolito (20054431)
    # Tranciamo via le dipendenze degli esercizi vecchi
    session.query(WorkoutExercise).filter_by(plan_id=plan.id).delete()
    for idx, ex in enumerate(exercises):
        new_ex = WorkoutExercise(
            plan_id=plan.id,
            name=ex.get('name', 'Esercizio'),
            muscle_group=ex.get('muscle_group', ''),
            sets=ex.get('sets', 3),
            reps=str(ex.get('reps', '10')),
            rest_time=str(ex.get('rest_time', '90s')),
            order_index=idx
        )
        session.add(new_ex)

    session.commit()
    session.close()
    return True

def update_workout_plan(user_id: int, plan_name: str, exercises: list):
    """
    Author: Timothy Giolito (20054431)
    
    Versione più permissiva dell'aggiornamento scheda, la va a cercare in base al suo nome in chiaro.
    Se la trova la sovrascrive azzerando gli esercizi, se non esiste la genera ex novo senza batter ciglio.
    """
    session = get_session()
    plan = session.query(WorkoutPlan).filter_by(user_id=user_id, name=plan_name).first()
    
    if not plan:
        session.close()
        save_workout_plan(user_id, plan_name, exercises)
        return
        
    # Author: Timothy Giolito (20054431)
    # Azzeriamo gli esercizi attualmente associati
    session.query(WorkoutExercise).filter_by(plan_id=plan.id).delete()
    
    # Author: Timothy Giolito (20054431)
    # Procediamo col re-inserimento usando i nuovi valori proposti
    for idx, ex in enumerate(exercises):
        new_ex = WorkoutExercise(
            plan_id=plan.id,
            name=ex.get('name', 'Esercizio'),
            muscle_group=ex.get('muscle_group', ''),
            sets=ex.get('sets', 3),
            reps=str(ex.get('reps', '10')),
            rest_time=str(ex.get('rest_time', '90s')),
            order_index=idx
        )
        session.add(new_ex)
        
    session.commit()
    session.close()
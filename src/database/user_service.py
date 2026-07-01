from sqlalchemy.orm import Session
from src.database.models import User, UserProfile, Conversation, Message, MealLog, WorkoutPlan, WorkoutExercise
from src.database.database import get_session
from sqlalchemy import func
from datetime import datetime, timezone
import bcrypt

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


def create_user(username: str, email: str, password: str):
    """Creazione di un nuovo utente nel DB con password hashata"""
    session = get_session()
    
    # Generiamo un "salt" e l'hash della password
    salt = bcrypt.gensalt()
    hashed_password = bcrypt.hashpw(password.encode('utf-8'), salt)
    
    # Salviamo la password hashata nel database (decodificata in stringa)
    new_user = User(
        username=username, 
        email=email, 
        password_hash=hashed_password.decode('utf-8')
    )
    session.add(new_user)
    session.commit()

    # Creazione profilo vuoto
    profile = UserProfile(user_id=new_user.id)
    session.add(profile)
    session.commit()

    session.refresh(new_user)
    session.close()
    
    return new_user


"""Dopo aver creato un nuovo utente e un nuovo profilo, bisogna aggiornare i dati inerenti a quell'utente"""
def update_user_profile(user_id: int, weight: float, height: float, age: int, gender: str, activity_level: float, target_weight: float, target_weeks: int, goal_type: str, workout_duration: int = 60, workout_preference: str = "Ipertrofia"):

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
        session.commit()
    session.close()

"""Recupero dei dati di uno specifico utente"""
def get_user_data(user_id: int):
    
    """Recupera il profilo completo dell'utente specificato"""
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
        "workout_preference": (profile.workout_preference if profile else None) or "Ipertrofia"
        }
    session.close()
    return data


def get_user_conversations(user_id: int, chat_type: str = None):

    """Recupero di tutte le conversazioni associate a un utente specifico, filtrando opzionalmente per tipo di agente."""
    session = get_session()
    query = session.query(Conversation).filter_by(user_id=user_id)
    if chat_type:
        query = query.filter(Conversation.chat_type == chat_type)
    convs = query.order_by(Conversation.created_at.desc()).all()
    session.close()
    return convs


def create_new_conversation(user_id: int, title: str = "Nuova conversazione", chat_type: str = "nutritionist"):

    """Crea una nuova sessione per ogni chat, associata al tipo di agente specificato"""
    session = get_session()
    new_conv = Conversation(user_id=user_id, title=title, chat_type=chat_type)
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
            "carbohydrates": 0,
            "target_proteins": 0,
            "target_fats": 0,
            "target_carbohydrates": 0
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
        "carbohydrates": round(carbohydrates, 1),
        # Alias con prefisso target_ per compatibilità con il frontend dashboard
        "target_proteins": round(proteins, 1),
        "target_fats": round(fats, 1),
        "target_carbohydrates": round(carbohydrates, 1)
    }

def get_todays_macros(user_id: int, target_date=None):
    """
    Calcola e restituisce la somma totale dei macronutrienti e delle calorie assunte da un utente nella data specificata (o odierna se non fornita).
    Autore: Stefano Bellan (20054330)
    """
    # Ottiene un'istanza della sessione del database
    session = get_session()
    
    # Recupera la data specificata o odierna nel fuso orario UTC
    if target_date is None:
        target_date = datetime.now(timezone.utc).date()
    
    # Esegue una query per calcolare la somma di calorie, proteine, grassi e carboidrati
    somma_macro = session.query(
        func.sum(MealLog.calories),
        func.sum(MealLog.proteins),
        func.sum(MealLog.fats),
        func.sum(MealLog.carbohydrates)
    ).filter(
        # Filtra i record associati allo specifico utente
        MealLog.user_id == user_id,
        # Filtra i log relativi esclusivamente alla data richiesta
        func.date(MealLog.timestamp) == target_date
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

def get_recent_macros_history(user_id: int, days: int = 7):
    """
    Recupera i totali giornalieri dei macronutrienti per gli ultimi N giorni.
    Utile per dare contesto agli agenti IA sui progressi recenti dell'utente.
    """
    session = get_session()
    from datetime import timedelta
    
    today = datetime.now(timezone.utc).date()
    start_date = today - timedelta(days=days-1)
    
    # Query raggruppata per data
    results = session.query(
        func.date(MealLog.timestamp).label("giorno"),
        func.sum(MealLog.calories).label("calories"),
        func.sum(MealLog.proteins).label("proteins"),
        func.sum(MealLog.carbohydrates).label("carbs"),
        func.sum(MealLog.fats).label("fats")
    ).filter(
        MealLog.user_id == user_id,
        func.date(MealLog.timestamp) >= start_date,
        func.date(MealLog.timestamp) < today # Escludiamo oggi, dato che viene passato a parte
    ).group_by(
        func.date(MealLog.timestamp)
    ).order_by(
        func.date(MealLog.timestamp).asc()
    ).all()
    
    session.close()
    
    history = []
    for row in results:
        history.append({
            "date": str(row.giorno),
            "calories": round(row.calories or 0, 1),
            "proteins": round(row.proteins or 0, 1),
            "carbs": round(row.carbs or 0, 1),
            "fats": round(row.fats or 0, 1)
        })
    return history

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

def authenticate_user(username: str, password: str):
    """Verifica se l'utente esiste e se la password è corretta"""
    session = get_session()
    user = session.query(User).filter_by(username=username).first()
    session.close()
    
    # Se l'utente esiste, controlliamo che la password inserita corrisponda all'hash salvato
    if user and bcrypt.checkpw(password.encode('utf-8'), user.password_hash.encode('utf-8')):
        return user
    
    return None # Ritorna None se il login fallisce

def save_workout_plan(user_id: int, plan_name: str, exercises: list):
    """
    Salva una nuova scheda di allenamento con i relativi esercizi.
    `exercises` è una lista di dizionari con chiavi: name, muscle_group, sets, reps, rest_time.
    """
    session = get_session()
    new_plan = WorkoutPlan(user_id=user_id, name=plan_name)
    session.add(new_plan)
    session.flush() # Per ottenere l'ID del piano
    
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

def get_user_workout_plans(user_id: int):
    """
    Recupera tutte le schede di allenamento di un utente, complete di esercizi.
    """
    session = get_session()
    plans = session.query(WorkoutPlan).filter_by(user_id=user_id).order_by(WorkoutPlan.created_at.desc()).all()
    
    # Costruisce una struttura dati dictionary compatibile con il frontend
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
    Elimina una scheda di allenamento dal database.
    Verifica che la scheda appartenga all'utente.
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

def update_workout_plan(user_id: int, plan_name: str, exercises: list):
    """
    Aggiorna una scheda di allenamento esistente (ricerca per nome e utente).
    Se esiste, sostituisce tutti gli esercizi con i nuovi.
    Se non esiste, la crea.
    """
    session = get_session()
    plan = session.query(WorkoutPlan).filter_by(user_id=user_id, name=plan_name).first()
    
    if not plan:
        session.close()
        save_workout_plan(user_id, plan_name, exercises)
        return
        
    # Elimina vecchi esercizi
    session.query(WorkoutExercise).filter_by(plan_id=plan.id).delete()
    
    # Inserisce nuovi esercizi
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

def update_workout_plan_by_id(user_id: int, plan_id: int, plan_name: str, exercises: list) -> bool:
    """
    Aggiorna il nome e gli esercizi di una scheda tramite il suo ID.
    Ritorna True se l'operazione ha successo.
    """
    session = get_session()
    plan = session.query(WorkoutPlan).filter_by(id=plan_id, user_id=user_id).first()
    
    if not plan:
        session.close()
        return False
        
    plan.name = plan_name
    
    # Elimina vecchi esercizi
    session.query(WorkoutExercise).filter_by(plan_id=plan.id).delete()
    
    # Inserisce nuovi esercizi
    for idx, ex in enumerate(exercises):
        new_ex = WorkoutExercise(
            plan_id=plan.id,
            name=ex.get('name', 'Esercizio'),
            muscle_group=ex.get('muscle_group', ''),
            sets=int(ex.get('sets', 3)),
            reps=str(ex.get('reps', '10')),
            rest_time=str(ex.get('rest_time', '90s')),
            order_index=idx
        )
        session.add(new_ex)
        
    session.commit()
    session.close()
    return True
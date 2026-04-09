import streamlit as st
import os
import tempfile
from dotenv import load_dotenv
from src.agents.nutritionst import NutritionistAgent
from PIL import Image
from agno.models.message import Image as AgnoImage
from src.agents.nutritionst import MealAnalysis
import re
from src.database.user_service import authenticate_user




# Importazione dei servizi del database
from src.database.user_service import (
    get_all_users, 
    create_user, 
    update_user_profile, 
    get_user_data,
    get_user_conversations,
    create_new_conversation,
    save_message,
    get_chat_history,
    save_meal_log,
    calculate_daily_macros,
    get_todays_macros,
    get_meals_by_category,
    delete_meal_log,
    rename_conversation,    
    delete_conversation
)

# --- CONFIGURAZIONE INIZIALE ---
def setup_environment() -> None:
    """
    Carica le variabili d'ambiente e verifica i requisiti minimi di avvio.
    """
    load_dotenv()
    
    if not os.getenv("GROQ_API_KEY"):
        st.error("Errore critico: GROQ_API_KEY non trovata. Controlla il file .env.")
        st.stop()

def init_session_state() -> None:
    """
    Inizializza lo stato dell'applicazione per l'utente corrente.
    """
    if 'current_user_id' not in st.session_state:
        st.session_state['current_user_id'] = None
    
    if 'app_initialized' not in st.session_state:
        st.session_state['app_initialized'] = True
    


# --- ENTRY POINT DELL'APPLICAZIONE ---
def main() -> None:
    """
    Funzione principale che definisce il layout e il routing della Single Page Application.
    """
    # 1. Configurazione della pagina
    st.set_page_config(
        page_title="RepEats | AI Fitness & Nutrition",
        page_icon="🍏",
        layout="wide",
        initial_sidebar_state="expanded"
    )

    # 2. Inizializzazione sistema
    setup_environment()
    init_session_state()

    # === 3. Costruzione della UI - Sidebar ===
    with st.sidebar:
        
        # Layout dell'header della sidebar: Logo e Titolo
        col_logo, col_titolo = st.columns([1.5,3], vertical_alignment="center")

        with col_logo:
            # Risoluzione dinamica del percorso assoluto del logo
            base_dir = os.path.dirname(os.path.abspath(__file__))
            logo_path = os.path.join(base_dir, "assets", "logo.png")
            
            try:
                st.image(logo_path, use_container_width=True)
            except Exception:
                st.warning("⚠️ Logo non trovato.")
                
        with col_titolo:
            st.markdown("<h1 style='margin: 0px; padding: 0px;'>RepEats</h1>", unsafe_allow_html=True)
            
        st.markdown("<hr style='margin-top: -25px; margin-bottom: 15px;'>", unsafe_allow_html=True)

        # === Gestione Autenticazione e Sessione ===
        if not st.session_state.get('current_user_id'):
            # Utente non autenticato: rendering dei form di login o registrazione
            scelta = st.radio("Cosa vuoi fare?", ["Accedi", "Registrati"])
            
            if scelta == "Registrati":
                st.subheader("Nuovo Utente")
                new_username = st.text_input("Username")
                new_email = st.text_input("Email")
                new_password = st.text_input("Password", type="password") # Maschera l'input della password
                
                if st.button("Crea Account"):
                    # Validazione formale dell'indirizzo email tramite espressione regolare
                    email_pattern = r'^[\w\.-]+@[\w\.-]+\.\w+$'
                    
                    # Verifica della completezza dei campi obbligatori
                    if not new_username or not new_email or not new_password:
                        st.warning("Compila tutti i campi.")
                    elif not re.match(email_pattern, new_email):
                        st.error("Inserisci un'email valida (es. mario@email.com)")
                    else:
                        try:
                            # Persistenza del nuovo utente sul database
                            user = create_user(new_username, new_email, new_password)
                            st.success(f"Account {user.username} creato! Ora seleziona 'Accedi'.")
                        except Exception as e:
                            # Gestione collisioni su vincoli di unicità (Username o Email duplicati)
                            st.error("Errore: Username o Email già esistenti.")
                            
            elif scelta == "Accedi":
                st.subheader("Accedi")
                login_username = st.text_input("Username")
                login_password = st.text_input("Password", type="password")
                
                if st.button("Login"):
                    if login_username and login_password:
                        # Verifica delle credenziali ed estrazione del profilo dal layer di persistenza
                        user = authenticate_user(login_username, login_password)
                        if user:
                            # Inizializzazione della sessione globale
                            st.session_state['current_user_id'] = user.id
                            st.success(f"Bentornato, {user.username}!")
                            st.rerun() # Reinizializza il ciclo di vita dell'applicazione
                        else:
                            st.error("Username o password non corretti.")
                    else:
                        st.warning("Inserisci credenziali valide.")
        else:
            # Utente autenticato: recupero profilo corrente e gestione logout
            users = get_all_users()
            current_user = next((u for u in users if u.id == st.session_state['current_user_id']), None)
            if current_user:
                st.success(f"Loggato come: **{current_user.username}**")
                if st.button("Esci (Logout)"):
                    # Terminazione della sessione e pulizia dello stato utente
                    st.session_state['current_user_id'] = None
                    st.rerun()

        st.markdown("---")
        st.info("Agenti attivi:\n- 🥗 Nutrizionista\n- 🏋️ Personal Trainer")

    #Costruzione della UI - Area Principale
    st.title("Benvenuto in RepEats")
    
    if not st.session_state['current_user_id']:
        st.warning("Per favore, seleziona o crea un utente nella barra laterale per iniziare.")
        return

    # Creazione delle schede
    tab_nutrizione, tab_allenamento, tab_profilo = st.tabs([
        "🥗 Nutrizione (Agente)", 
        "💪 Allenamento (Agente)", 
        "👤 Profilo Utente"
    ])

    # === TAB 1: NUTRIZIONE (Vision AI) ===
   
    # Questo segmento gestisce la dashboard nutrizionale, occupandosi della visualizzazione dei target
    # metabolici e dei progressi giornalieri. Gestisce inoltre il caricamento di un'immagine di un pasto e 
    # l'invocazione di un Agente di Intelligenza Artificiale per l'analisi visiva e la classificazione nutrizionale,
    # salvando i risultati ottenuti direttamente nel database.
    # Autore: Stefano Bellan (20054330)
   
    with tab_nutrizione:
        # 1. Recuperiamo i dati dell'utente per controllare se il profilo è completo
        user_data = get_user_data(st.session_state['current_user_id'])
            
            # Controlliamo se i tre campi fondamentali esistono (non sono None)
        profile_complete = user_data.get('weight') and user_data.get('height') and user_data.get('age')

        if not profile_complete:
                # Se il profilo è incompleto, mostriamo l'avviso e ci fermiamo qui
                st.warning("⚠️ **Benvenuto su RepEats!**\n\nPer calcolare il tuo fabbisogno giornaliero e usare l'Agente Nutrizionista, devi prima completare il tuo profilo (Peso, Altezza, Età) nella scheda **👤 Profilo Utente**.")
        else: 
            # Mostra l'intestazione principale per la sezione relativa alla dashboard nutrizionale
            st.header("📊 Dashboard Nutrizionale")
            
            # Interroga il layer di servizio per calcolare gli obiettivi macro-nutrizionali in base al profilo utente
            daily_targets = calculate_daily_macros(st.session_state['current_user_id'])
            
            # Recupera dal database la somma dei macronutrienti e delle calorie consumate nella giornata odierna
            consumed_today = get_todays_macros(st.session_state['current_user_id'])
            
            # Calcola il progresso percentuale delle calorie consumate limitandolo a 1.0 (100%) per la barra della UI
            cal_progress = min(consumed_today['calories'] / (daily_targets['target_calories'] or 1), 1.0)
            
            # Calcola il progresso percentuale delle proteine garantendo che non ecceda 1.0 a scopo di visualizzazione
            prot_progress = min(consumed_today['proteins'] / (daily_targets['proteins'] or 1), 1.0)
            
            # Calcola il progresso percentuale dei grassi, con divisione sicura tramite operatore OR in caso di assenza
            fat_progress = min(consumed_today['fats'] / (daily_targets['fats'] or 1), 1.0)
            
            # Calcola il progresso percentuale dei carboidrati bloccando il valore massimo a 1.0 per il componente progress
            carb_progress = min(consumed_today['carbohydrates'] / (daily_targets['carbohydrates'] or 1), 1.0)

            # Ripartisce il layout orizzontale definendo due colonne separate su cui disporre i contenuti
            col1, col2 = st.columns(2)
            
            # Specifica il blocco di codice destinato al rendering per la prima colonna creata
            with col1:
                # Mostra una metrica per il TDEE (Fabbisogno Calorico Giornaliero Totale)
                st.metric("Fabbisogno Calorico Giornaliero (TDEE)", f"{daily_targets['tdee']} kcal")
                
            # Specifica il blocco di codice destinato al rendering per la seconda colonna creata
            with col2:
                # Mostra in stile markdown il rapporto tra calorie attuali rispetto a quelle target totali giornaliere
                st.markdown(f"**Calorie:** {consumed_today['calories']} / {daily_targets['target_calories']} kcal")
                # Disegna la relativa barra di avanzamento passando il valore in scala precedentemente elaborato
                st.progress(cal_progress)
                
            # Inserisce un divisore visivo orizzontale a livello d'interfaccia 
            st.divider()
            
            # Crea un sotto-titolo per la successiva area specifica dei macronutrienti consumati
            st.subheader("I tuoi Macronutrienti")
            
            # Alloca tre ulteriori colonne disposte orizzontalmente per distribuire in modo equi-proporzionato i macro
            mcol1, mcol2, mcol3 = st.columns(3)
            
            # Gestisce i componenti esposti visivamente per la prima di queste 3 colonne
            with mcol1:
                # Renderizza le misurazioni assolute per le proteine (consumate vs target)
                st.markdown(f"**Proteine:** {consumed_today['proteins']} / {daily_targets['proteins']} g")
                # Implementa visivamente la barra indicante il caricamento del progresso proteico calcolato
                st.progress(prot_progress)
                
            # Gestisce i componenti esposti visivamente per la seconda delle 3 colonne
            with mcol2:
                # Renderizza le misurazioni assolute per i grassi assunti (consumati vs target)
                st.markdown(f"**Grassi:** {consumed_today['fats']} / {daily_targets['fats']} g")
                # Implementa l'indicatore a barra associato alla quota lipidica già ingerita
                st.progress(fat_progress)
                
            # Gestisce i componenti esposti visivamente per l'ultima delle 3 colonne specificate
            with mcol3:
                # Renderizza le misurazioni assolute riferite ai carboidrati assunti
                st.markdown(f"**Carboidrati:** {consumed_today['carbohydrates']} / {daily_targets['carbohydrates']} g")
                # Inserisce la progress bar per la quota glicidica odierna consumata limitata all'unità (1.0)
                st.progress(carb_progress)
            
            # Definisce un dizionario per mappare i pasti della giornata alle relative emoji identificative
            categorie_icone = {"colazione": "☕", "pranzo": "🍽️", "cena": "🥗", "spuntini": "🍎"}
            
            # Stabilisce le aliquote percentuali ideali che ogni pasto dovrebbe ricoprire rispetto al TDEE giornaliero
            percentuali_pasto = {"colazione": 0.20, "pranzo": 0.40, "cena": 0.30, "spuntini": 0.10}
            
            # Cicla dinamicamente attraverso tutte le categorie di pasto definite e configurate precedentemente
            for categoria, icona in categorie_icone.items():
                
                # Invoca il servizio a database per recuperare esclusivamente i log della categoria per l'utente odierno o tutti i log della categoria?
                # get_meals_by_category restituisce tutti i pasti della categoria per l'utente, non sono filtrati per data odierna nella funzione, ma consideriamo l'intera iterazione come richiesto
                # Nota: se servisse un filtro per data, si potrebbe fare a DB, ma in questa iterazione usiamo direttamente i log recuperati da DB
                log_pasti_categoria = get_meals_by_category(st.session_state['current_user_id'], categoria)
                
                # Somma in modo aggregato i valori calorici considerando i record presenti per la categoria ed evitando errori di None Type
                calorie_consumate = sum((p.calories or 0) for p in log_pasti_categoria)
                # Calcola l'obiettivo calorico proporzionato e raccomandato dalla ratio definita per lo specifico pasto
                target_pasto = int((daily_targets['target_calories'] or 0) * percentuali_pasto[categoria])
                
                # Apre un contenitore a tendina espandibile intitolato con l'icona, il nome, i consumi e gli obiettivi del pasto in corso
                with st.expander(f"{icona} {categoria.capitalize()} -> {calorie_consumate}/{target_pasto} kcal"):
                    
                    # Calcola cumulativamente l'apporto proteico analizzato e fornito dalla persistenza dei log nel DB 
                    proteine_tot = sum((p.proteins or 0) for p in log_pasti_categoria)
                    # Calcola parimenti l'apporto in grassi per tutti i log accorpati nella specifica categoria
                    fats_tot = sum((p.fats or 0) for p in log_pasti_categoria)
                    # Calcola la quota di carboidrati totale ottenuta aggregando i log tramite list comprehension condizionali 
                    carbs_tot = sum((p.carbohydrates or 0) for p in log_pasti_categoria)
                    
                    # Calcola le saturazioni in scala per tracciare le barre in UI limitando per sicurezza l'overflow a 1.0 (100%)
                    progresso_calorie = min(calorie_consumate / (target_pasto or 1), 1.0)
                    
                    # Scomporre il fabbisogno giornaliero per allinearne le referenze di target al pasto locale 
                    target_proteine = (daily_targets['proteins'] or 0) * percentuali_pasto[categoria]
                    target_fats = (daily_targets['fats'] or 0) * percentuali_pasto[categoria]
                    target_carbs = (daily_targets['carbohydrates'] or 0) * percentuali_pasto[categoria]
                    
                    # Determina l'indice di caricamento proteico per il renderer limitando l'overflow massimo del grafico
                    progresso_pro = min(proteine_tot / (target_proteine or 1), 1.0)
                    # Determina l'indice di caricamento dei carboidrati bloccandolo entro i margini di disegno
                    progresso_carbs = min(carbs_tot / (target_carbs or 1), 1.0)
                    # Determina l'indice per la progress bar dei grassi con fallback se i target risultassero vuoti
                    progresso_fats = min(fats_tot / (target_fats or 1), 1.0)
                    
                    # Configura un subset di quattro colonne intermedie specifiche atte a ospitare gli indicatori di progress bar
                    c_col1, c_col2, c_col3, c_col4 = st.columns(4)

                    # Gestisce visivamente la colonna calorica del widget espandibile
                    with c_col1:
                        st.markdown(f"**Calorie:** {calorie_consumate} kcal")
                        st.progress(float(progresso_calorie))
                    # Gestisce visivamente la colonna per i risultati formativi relativi alle proteine
                    with c_col2: 
                        st.markdown(f"**Proteine:** {proteine_tot} g")
                        st.progress(float(progresso_pro))
                    # Popola la stringa testuale con il conteggio aggregato e avanza la UI bar dei glucidi
                    with c_col3:
                        st.markdown(f"**Carboidrati:** {carbs_tot} g")
                        st.progress(float(progresso_carbs))
                    # Applica testi e grafiche sulla quota lipidica del singolo micro-pasto
                    with c_col4: 
                        st.markdown(f"**Grassi:** {fats_tot} g")
                        st.progress(float(progresso_fats))
                    
                    # Applica il divisorio strutturale di design di Streamlit
                    st.divider()
                    
                    # Elabora tutti log appartenenti alla categoria, renderizzandone le righe testuali 
                    for pasto_db in log_pasti_categoria:
                        # Riparte l'architettura grafica isolando l'informazione alla prima e più ampia colonna, e il bottone al margine
                        col_info, col_btn = st.columns([3,1])
                        
                        # Identifica un nome descrittivo privilegiando il nuovo campo 'name'. Fallback su analysis o troncamento
                        desc_name = pasto_db.name if pasto_db.name else ("Pasto Analizzato" if len(pasto_db.analysis_result) > 40 else pasto_db.analysis_result)
                        
                        # Renderizza nella colonna informazionale le macro stringhe essenziali associate al record in memoria
                        with col_info:
                            st.markdown(f"🍕 **{desc_name}** - {pasto_db.calories} kcal")
                            
                        # Alloca l'interattività dei listener dei bottoni delegando l'eliminazione effettiva dal repository 
                        with col_btn: 
                            # Crea un button unico fornendo in key la concat con id univoco del database altrimenti sovrascriverebbe lo state  
                            if st.button("🗑️", key=f"del_{categoria}_{pasto_db.id}"):
                                # Tenta di eseguire la procedura CRUD di elusione ed eliminazione gestita a livello utente/sistema
                                is_deleted = delete_meal_log(st.session_state['current_user_id'], pasto_db.id)
                                # In caso di esito felice riavvia la sessione per eliminare l'elemento eliminato all'UI
                                if is_deleted:
                                    st.rerun()
                                    
                    # Conclude l'area di recap pasti stampando una separazione per dividere con la logica uploader AI
                    st.divider()

                # Attiva e mostra a schermo la componente drag&drop che attende immagini con MIME type strettamente vincolati
                    uploaded_file = st.file_uploader(f"Carica la foto per {categoria}...", type=["jpg", "jpeg", "png"], key=f"upload_{categoria}")
                    
                    # Verifica ed innesca la logica solamente nel caso in cui un file valido sia caricato instanziato
                    if uploaded_file is not None:
                        # Deserializza l'immagine proveniente dall'utente caricandola in memoria RAM tramite la libreria PIL
                        image = Image.open(uploaded_file)
                        
                        # Espone in UI l'anteprima dell'immagine aperta e associata tramite un div responsivo al container
                        st.image(image, caption="Anteprima del Pasto", use_container_width=True)
                        
                        # --- NUOVA IMPLEMENTAZIONE: Campo Grammatura ---
                        grammatura = st.number_input(
                            "⚖️ Inserisci la grammatura (in grammi)", 
                            min_value=1, max_value=3000, value=100, step=10, 
                            key=f"grammatura_{categoria}",
                            help="Inserisci il peso esatto per calcolare correttamente i valori nutrizionali."
                        )
                        
                        # Istanzia e predispone il Nutrizionista multi-modale per l'inferenza AI con l'ausilio di Agno
                        agent = NutritionistAgent()
                        
                        # Definisce un pulsante utile ad autorizzare manualmente ed istruire il processo d'inferenza dell'analisi
                        if st.button("Analizza Pasto", key=f"btn_analyze_{categoria}"):
                            # Applica uno spinner di caricamento visivo utile per la UX bloccando i concetti in attesa del risultato AI
                            with st.spinner(f"L'Agente AI sta calcolando i valori per {grammatura}g di prodotto..."):
                                try:
                                    # Si riserva e crea su disco di sistema un file temp di stoccaggio virtuale dove scrivere
                                    with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as tmp_file:
                                        # Preleva dal web-buffer di streamlit lo stream di byte per buttarlo in scrittura fisica su disco locale
                                        tmp_file.write(uploaded_file.getvalue())
                                        # Archivia in variabile di sessione temporanea l'hash referenziante il nuovo path del file su disco
                                        tmp_path = tmp_file.name
                                    
                                    # Istruisce l'agente a usare la grammatura
                                    prompt_agente = (
                                        f"Analizza accuratamente l'immagine del pasto o il codice a barre (usa gli strumenti a tua disposizione). "
                                        f"IMPORTANTE: L'utente ha indicato che la porzione consumata è di ESATTAMENTE {grammatura} grammi. "
                                        f"Se usi lo strumento del codice a barre (che restituisce valori per 100g), DEVI FARE LA PROPORZIONE MATEMATICA per ricalcolare i valori su {grammatura}g. "
                                        "Restituisci ESCLUSIVAMENTE un oggetto JSON valido per lo schema MealAnalysis. Non aggiungere testo prima o dopo. "
                                        "DEVI restituire i dati seguendo rigorosamente lo schema MealAnalysis: "
                                        "name: estrai il nome del prodotto o un nome descrittivo. "
                                        f"analysis_result: una breve descrizione. Includi una frase del tipo 'Valori stimati per {grammatura}g'. "
                                        f"calories, proteins, carbohydrates, fats: solo numeri (i valori finali calcolati per {grammatura}g). "
                                        "NON aggiungere chiacchiere extra, rispondi solo con i dati strutturati."
                                    )
                                    
                                    # Inizia il processo inferenziale invocando asincronamente l'Agente LLM
                                    response = agent.run(
                                        prompt_agente, 
                                        images=[AgnoImage(filepath=tmp_path)],
                                        response_model=MealAnalysis
                                    )
                                    
                                    # Associa alla variabile un binding sul payload restituito internamente da agent process ultimato
                                    raw_content = response.content

                                    # Gestisce un controllo dinamico se il framework perde colpi e rilascia la conformazione testuale raw (fallback in stringa)
                                    if isinstance(raw_content, str):
                                        try:
                                            # Normalizza eventuali stringhe parassitarie emesse in Markdown per prepararsi al casting JSON formale
                                            clean_json = raw_content.replace("```json", "").replace("```", "").strip()
                                            # Esegue il parsing effettivo del Base Model validandolo tramite Pydantic con input il testo sanificato  
                                            analysis = MealAnalysis.model_validate_json(clean_json)
                                        # Intercetta il sollevamento formale di errori sintattici in codifica che porterebbero a blocco d'applicazione
                                        except Exception as e:
                                            # Se il testo ricevuto non è JSON valido, molto probabilmente l'agente sta comunicando 
                                            # che non ha riconosciuto l'immagine o il codice a barre (es. "Mi dispiace, ma l'immagine...")
                                            st.warning(f"L'agente non è riuscito a estrarre i dati in formato strutturato.\n\n**Risposta ricevuta:** {raw_content}")
                                            # Esegue Garbage collection manuale per evitare leak del file
                                            os.remove(tmp_path)
                                            # Ferma l'esecuzione per evitare di procedere col salvataggio a DB
                                            st.stop()
                                    # Fallback case opposti ad eccezione stringa: L'implementazione si è attenuta al type model Pydantic di origine
                                    else:
                                        # Applica ed accoglie senza sanificazione l'oggetto nativo che soddisfa MealAnalysis BaseModel
                                        analysis = raw_content

                                    if analysis.analysis_result == "ATTENZIONE: L'immagine caricata non sembra contenere cibo rilevabile.":
                                        st.error("L'agente non ha rilevato cibo in questa immagine. Riprova con una foto valida.")
                                        st.stop()

                                    # Mostra e loggia il risultato generato e narrato dall'LLM sfruttando un componente standard informativo
                                    st.info(analysis.analysis_result)

                                    # Architetta nuovamente tre sub-colonne ad uso esclusivo dei tre indicatori derivati a valle del parsing del model AI
                                    res_col1, res_col2, res_col3 = st.columns(3)
                                    # Popola il primo segnaposto con la stima calorica generata
                                    res_col1.metric("Calorie", f"{analysis.calories} kcal")
                                    # Popola il secondo segnaposto con la stima in grammi alle proteine ingerite
                                    res_col2.metric("Proteine", f"{analysis.proteins} g")
                                    # Popola il terzo segnaposto adibito alle indicazioni lipidiche stimate per il pasto inserito
                                    res_col3.metric("Grassi", f"{analysis.fats} g")

                                    # Passa tutti i payload estrusi al CRUD layer interfacciante la persistenza tramite engine del database MySQL/SQLite locale ecc
                                    save_meal_log(
                                        # Trasmette l'intestatario ID relativo all'account autenticato di sessione ad uso Foreign Key
                                        user_id=st.session_state['current_user_id'],
                                        # Converte e fa il dump via format JSON di tutta l'integrità natia generatrice del responso analysis
                                        analysis_result=analysis.model_dump_json(),
                                        # Passa come stringa formattata la categoria del pasto determinata dal ciclo UI attuale
                                        category = categoria,
                                        # Estrae e passa testualmente il field generato riferito al nome della pietanza identificata
                                        name = analysis.name,
                                        # Trascrive specificatamente a database l'asset del modello per le calorie
                                        calories = analysis.calories,
                                        # Trascrive specificatamente le stime ad attributo del modello relative l'ingresso in Grammi proteico
                                        proteins= analysis.proteins,
                                        # Salva per attributo per colonna i grammi dei grassi del pasto
                                        fats = analysis.fats,
                                        # Salva per attributo al modello carboidrati nel table MealLog con reference in foreign key
                                        carbs = analysis.carbohydrates
                                    )

                                    # Effettua feedback grafico visualizzando a bandierina la conferma su transazione salva di fine procedura
                                    st.success("Analisi salvata con successo!")

                                    # Esegue Garbage collection manuale esplicita andando a disfare fisicamente il dummy temp.jpg creato sul root
                                    os.remove(tmp_path)
                                    # Inizializza un rebuild complessivo dell'intera GUI triggerando la catena dell'architettura di rendering Streamlit
                                    st.rerun()
                                    
                                # Prepara via exception di salvataggio try l'ingabbiamento logiche ad appannaggio di cadute generiche
                                except Exception as e:
                                    # Gestore preposto alla cattura di faults network API Agno o crasi critiche al file system del disco OS lanciandoli con banner custom  
                                    st.error(f"Si è verificato un errore critico durante l'analisi: {e}")


    with tab_allenamento:
        # Recuperiamo i dati dell'utente per controllare se il profilo è completo
        user_data = get_user_data(st.session_state['current_user_id'])
        profile_complete = user_data.get('weight') and user_data.get('height') and user_data.get('age')

        if not profile_complete:
            st.warning("⚠️ **Ehi, frena un attimo!** ✋\n\nIl Personal Trainer AI ha bisogno di conoscere le tue misure per farti allenare in sicurezza. Vai nella scheda **👤 Profilo Utente** e inserisci i tuoi dati fisici per iniziare.")
        else:
            st.header("💪 Personal Trainer AI")
            
            # Recupero dei dati per l'orchestrazione
            user_id = st.session_state['current_user_id']
            user_data = get_user_data(user_id)
            consumed_today = get_todays_macros(user_id)
            daily_targets = calculate_daily_macros(user_id)
            
            # Dividiamo lo schermo: 1/4 per la cronologia, 3/4 per la chat
            col_storia, col_chat = st.columns([1, 3])
            
            # Recupero conversazioni
            conversations = get_user_conversations(user_id)
            
            # 1. NUOVA LOGICA STATO IDLE: Se non c'è una chat attiva, la impostiamo a "Nessuna" (None)
            if 'active_conv_id' not in st.session_state:
                st.session_state['active_conv_id'] = None

            with col_storia:
                st.subheader("Cronologia")
                
                # Bottone per Nuova Chat Manuale
                if st.button("➕ Nuova Chat", use_container_width=True):
                    from datetime import datetime
                    titolo_data = f"Chat del {datetime.now().strftime('%d/%m %H:%M')}"
                    nuova_conv = create_new_conversation(user_id, titolo_data)
                    st.session_state['active_conv_id'] = nuova_conv.id
                    st.rerun()
                
                st.divider()
                
                # Visualizzazione delle chat raggruppate per titolo
                if conversations:
                    # Creiamo un dizionario {id: titolo}
                    conv_dict = {c.id: c.title for c in conversations}
                    
                    # Cerchiamo l'indice della chat attualmente attiva (se esiste)
                    keys_list = list(conv_dict.keys())
                    current_index = None
                    if st.session_state['active_conv_id'] in keys_list:
                        current_index = keys_list.index(st.session_state['active_conv_id'])

                    # Menu a tendina per selezionare la chat
                    chat_selezionata = st.radio(
                        "Le tue conversazioni:",
                        options=keys_list,
                        format_func=lambda x: conv_dict[x],
                        index=current_index if current_index is not None else 0
                    )
                    
                    # Se l'utente cambia chat dalla UI, aggiorniamo lo stato
                    if chat_selezionata != st.session_state['active_conv_id']:
                        st.session_state['active_conv_id'] = chat_selezionata
                        st.rerun()

                    # --- NUOVA SEZIONE: GESTIONE CHAT ---
                    if st.session_state['active_conv_id'] is not None:
                        st.divider()
                        
                        # Creiamo un menù espandibile per non occupare troppo spazio visivo
                        with st.expander("⚙️ Opzioni Chat"):
                            # Campo di testo per il nuovo nome (precompilato con quello attuale)
                            nuovo_nome = st.text_input(
                                "Rinomina", 
                                value=conv_dict[st.session_state['active_conv_id']], 
                                label_visibility="collapsed" # Nasconde la label testuale per fare pulizia
                            )
                            
                            col_btn1, col_btn2 = st.columns(2)
                            with col_btn1:
                                if st.button("✏️ Salva", use_container_width=True):
                                    rename_conversation(st.session_state['active_conv_id'], nuovo_nome)
                                    st.rerun()
                                    
                            with col_btn2:
                                # Tasto rosso (type="primary" in un tema standard, o comunque risalta)
                                if st.button("🗑️ Elimina", type="primary", use_container_width=True):
                                    delete_conversation(st.session_state['active_conv_id'])
                                    st.session_state['active_conv_id'] = None # Ritorna allo stato di riposo (Idle)
                                    st.rerun()

            with col_chat:
            # Troviamo la conversazione in modo SICURO: aggiungiamo ", None" alla fine.
            # Così, se non trova la chat (es. l'hai appena cancellata), non va in crash ma restituisce None.
                active_conv = next((c for c in conversations if c.id == st.session_state['active_conv_id']), None)

                # GESTIONE DELLO SCHERMO A DESTRA (Idle o Chat)
                # Se non c'è una chat attiva, o se la chat cercata non esiste più, mostriamo lo stato di benvenuto.
                if st.session_state['active_conv_id'] is None or active_conv is None:
                    # Per sicurezza, se l'ID era sbagliato o la chat è stata eliminata, resettiamo lo stato
                    st.session_state['active_conv_id'] = None 
                    
                    # --- STATO DI RIPOSO (IDLE) ---
                    st.info("👋 **Benvenuto nel tuo spazio di allenamento AI!**\n\nNessuna chat selezionata. Puoi selezionare una conversazione precedente dalla cronologia a sinistra oppure cliccare su **'➕ Nuova Chat'** per iniziare una nuova consulenza.")
                    
                else:
                    # --- STATO CHAT ATTIVA ---
                    st.caption(f"Sessione attiva: **{active_conv.title}**")

                    chat_container = st.container(height=500)

                    # Carichiamo la cronologia
                    history = get_chat_history(active_conv.id)
                    for msg in history:
                        with chat_container.chat_message(msg["role"]):
                            st.write(msg["content"])

                    # Input dell'utente
                    if prompt := st.chat_input("Chiedi al tuo trainer (Usa Maiusc+Invio per andare a capo nel testo)"):
                        
                        with chat_container.chat_message("user"):
                            st.write(prompt)
                        save_message(active_conv.id, "user", prompt)

                        from src.agents.fitness_agent import get_fitness_agent
                        agent = get_fitness_agent(user_data, consumed_today, daily_targets, history)
                        
                        with chat_container.chat_message("assistant"):
                            with st.spinner("L'AI sta analizzando la tua richiesta..."):
                                response = agent.run(prompt)
                                st.write(response.content)
                            
                        save_message(active_conv.id, "assistant", response.content) 
                        st.rerun()
                    
                

    with tab_profilo:
        st.header("Gestione Dati e Misurazioni")
        user_data = get_user_data(st.session_state['current_user_id'])
        
        st.write("Aggiorna i tuoi dati per ricevere consigli più precisi.")
        
        with st.form("update_profile_form"):
            col1, col2 = st.columns(2)
            with col1:
                weight = st.number_input(
                    "Peso (kg)", min_value=30.0, max_value=250.0, 
                    value=float(user_data['weight']) if user_data['weight'] else 70.0,
                    step=0.1
                )
                age = st.number_input(
                    "Età", min_value=10, max_value=100, 
                    value=int(user_data['age']) if user_data['age'] else 25
                )
                gender = st.selectbox(
                    "Sesso Biologico (Per accuratezza BMR)", 
                    options=["uomo", "donna"],
                    index=0 if user_data.get('gender', 'uomo') == "uomo" else 1
                )
            with col2:
                height = st.number_input(
                    "Altezza (cm)", min_value=100.0, max_value=250.0, 
                    value=float(user_data['height']) if user_data['height'] else 170.0,
                    step=0.5
                )
                activity_levels = {
                    "Sedentario (Nessun allenamento)": 1.2,
                    "Leggero (1-3 gg/sett)": 1.375,
                    "Moderato (3-5 gg/sett)": 1.55,
                    "Attivo (6-7 gg/sett)": 1.725,
                    "Molto Attivo (Estremo)": 1.9
                }
                
                # Mappatura del valore numerico per pre-popolare il menù a tendina
                current_activity_val = float(user_data.get('activity_level', 1.55))
                # Di base partiamo dall'indice "Moderato" qualora la mappatura non fallisse
                act_index = 2 
                for i, val in enumerate(activity_levels.values()):
                    # Matcho iterativamente l'indice se il db restituisce Float paritari
                    if val == current_activity_val:
                        act_index = i
                        break
                        
                activity_label = st.selectbox(
                    "Livello di Attività (PAL)", 
                    options=list(activity_levels.keys()),
                    index=act_index
                )
                activity_level = activity_levels[activity_label]
                
            # Campo numerico per l'inserimento del peso obiettivo desiderato
            target_weight = st.number_input(
                "Peso Obiettivo (kg)", min_value=30.0, max_value=250.0, 
                value=float(user_data['target_weight']) if user_data.get('target_weight') else 70.0,
                step=0.1
            )
            
            # Campo numerico per l'inserimenti del tempo in cui si vuole ambire al risultato
            target_weeks = st.number_input(
                "Tempo desiderato (Settimane)", min_value=1, max_value=156, 
                value=int(user_data['target_weeks']) if user_data.get('target_weeks') else 12,
                help="In quanto tempo vorresti raggiungere il tuo peso obiettivo? (Standard: 12 settimane)"
            )
            
            # Menu a tendina per selezionare la tipologia di obiettivo nutrizionale
            goal_type = st.selectbox(
                "Tipo di Obiettivo", 
                options=["dimagrimento", "mantenimento", "massa"],
                index=["dimagrimento", "mantenimento", "massa"].index(user_data['goal_type']) if user_data.get('goal_type') else 0
            )
            
            if st.form_submit_button("Salva Modifiche"):
                # Passa al servizio di aggiornamento tutte le 9 feature strutturali necessarie ad oggi all'autocalcolo metabolico
                update_user_profile(st.session_state['current_user_id'], weight, height, age, gender, activity_level, target_weight, target_weeks, goal_type)
                st.success("Profilo aggiornato!")
                st.rerun()

if __name__ == "__main__":
    main()
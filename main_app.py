import streamlit as st
import os
import tempfile
from dotenv import load_dotenv
from src.agents.nutritionst import NutritionistAgent
from PIL import Image
from agno.models.message import Image as AgnoImage
from src.agents.nutritionst import MealAnalysis




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
    get_todays_macros
)

# --- CONFIGURAZIONE INIZIALE ---
def setup_environment() -> None:
    """
    Carica le variabili d'ambiente e verifica i requisiti minimi di avvio.
    """
    load_dotenv()
    
    if not os.getenv("GEMINI_API_KEY"):
        st.error("Errore critico: GEMINI_API_KEY non trovata. Controlla il file .env.")
        st.stop()

def init_session_state() -> None:
    """F
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

    # 3. Costruzione della UI - Sidebar
    with st.sidebar:
        st.title("🏋️ RepEats")
        st.markdown("---")
        
        try:
            users = get_all_users()
            user_options = [u.username for u in users] + ["+ Nuovo Utente..."]
            
            selected_option = st.selectbox(
                "Seleziona il tuo profilo", 
                user_options,
                index=0 if users else 0
            )

            if selected_option == "+ Nuovo Utente...":
                st.subheader("Registra Nuovo Utente")
                new_username = st.text_input("Username")
                new_email = st.text_input("Email")
                if st.button("Crea Account"):
                    if new_username and new_email:
                        user = create_user(new_username, new_email)
                        st.success(f"Utente {user.username} creato!")
                        st.rerun()
                    else:
                        st.warning("Inserisci tutti i campi.")
            else:
                current_user = next(u for u in users if u.username == selected_option)
                st.session_state['current_user_id'] = current_user.id
                st.success(f"Loggato come: **{current_user.username}**")

        except Exception as e:
            st.error("Errore nel caricamento utenti. Hai inizializzato il database?")
            st.info("Esegui: python src/database/init_db.py")

        st.markdown("---")
        st.info("Agenti attivi:\n- 🥗 Nutrizionista\n- 🏋️ Personal Trainer")

    # 4. Costruzione della UI - Area Principale
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
    """
    Questo segmento gestisce la dashboard nutrizionale, occupandosi della visualizzazione dei target
    metabolici e dei progressi giornalieri. Gestisce inoltre il caricamento di un'immagine di un pasto e 
    l'invocazione di un Agente di Intelligenza Artificiale per l'analisi visiva e la classificazione nutrizionale,
    salvando i risultati ottenuti direttamente nel database.
    Autore: Stefano Bellan (20054330)
    """
    with tab_nutrizione:
        # Mostra l'intestazione principale per la sezione relativa alla dashboard nutrizionale
        st.header("📊 Dashboard Nutrizionale")
        
        # Interroga il layer di servizio per calcolare gli obiettivi macro-nutrizionali in base al profilo utente
        daily_targets = calculate_daily_macros(st.session_state['current_user_id'])
        
        # Recupera dal database la somma dei macronutrienti e delle calorie consumate nella giornata odierna
        consumed_today = get_todays_macros(st.session_state['current_user_id'])
        
        # Calcola il progresso percentuale delle calorie consumate limitandolo a 1.0 (100%) per la barra della UI
        cal_progress = min(consumed_today['calories']/ daily_targets['target_calories'] or 1, 1.0)
        
        # Calcola il progresso percentuale delle proteine garantendo che non ecceda 1.0 a scopo di visualizzazione
        prot_progress = min(consumed_today['proteins'] / daily_targets['proteins']or 1, 1.0)
        
        # Calcola il progresso percentuale dei grassi, con divisione sicura tramite operatore OR in caso di assenza
        fat_progress = min(consumed_today['fats'] / daily_targets['fats'] or 1, 1.0)
        
        # Calcola il progresso percentuale dei carboidrati bloccando il valore massimo a 1.0 per il componente progress
        carb_progress = min(consumed_today['carbohydrates'] / daily_targets['carbohydrates'] or 1, 1.0)

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
        
        # Attiva e mostra a schermo la componente drag&drop che attende immagini con MIME type strettamente vincolati
        uploaded_file = st.file_uploader("Carica la foto del tuo pasto...", type=["jpg", "jpeg", "png"])
        
        # Verifica ed innesca la logica solamente nel caso in cui un file valido sia caricato instanziato
        if uploaded_file is not None:
            # Deserializza l'immagine proveniente dall'utente caricandola in memoria RAM tramite la libreria PIL
            image = Image.open(uploaded_file)
            
            # Espone in UI l'anteprima dell'immagine aperta e associata tramite un div responsivo al container
            st.image(image, caption="Anteprima del Pasto", use_container_width=True)
            
            # Istanzia e predispone il Nutrizionista multi-modale per l'inferenza AI con l'ausilio di Agno
            agent = NutritionistAgent()
            
            # Definisce un pulsante utile ad autorizzare manualmente ed istruire il processo d'inferenza dell'analisi
            if st.button("Analizza Pasto"):
                # Applica uno spinner di caricamento visivo utile per la UX bloccando i concetti in attesa del risultato AI
                with st.spinner("L'Agente AI sta analizzando l'immagine..."):
                    try:
                        # Si riserva e crea su disco di sistema un file temp di stoccaggio virtuale dove scrivere
                        with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as tmp_file:
                            # Preleva dal web-buffer di streamlit lo stream di byte per buttarlo in scrittura fisica su disco locale
                            tmp_file.write(uploaded_file.getvalue())
                            # Archivia in variabile di sessione temporanea l'hash referenziante il nuovo path del file su disco
                            tmp_path = tmp_file.name
                        
                        # Inizia il processo inferenziale invocando asincronamente l'Agente LLM con parametri precisi in base al framework
                        response = agent.run(
                            "Analizza accuratamente l'immagine del pasto e restituisci ESCLUSIVAMENTE un oggetto JSON valido per lo schema MealAnalysis. Non aggiungere testo prima o dopo."
                            "DEVI restituire i dati seguendo rigorosamente lo schema MealAnalysis: "
                            "analysis_result: una breve descrizione. "
                            "calories, proteins, carbohydrates, fats: solo numeri (stima media). "
                            "NON aggiungere chiacchiere extra, rispondi solo con i dati strutturati.", 
                            # Cede al prompt di run la string path del file temporaneo castato per il formato oggetto richiesto da 'AgnoImage'
                            images=[AgnoImage(filepath=tmp_path)],
                            # Implementa coercizione formale all'output esigendo uno stream conformante lo schema del validatore BaseModel
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
                                # Segnala e notifica esplicitamente d'errore visivo per parsing errato all'utente
                                st.error(f"Errore nel parsing del JSON: {e}")
                                # Scrive il blocco malformattato così com'è per scopi da puro troubleshooting lato sviluppatori
                                st.write("Dati ricevuti:", raw_content)
                                # Ferma e distrugge le successivi esecuzioni procedurali interrompendo lo script del ciclo interno a Streamlit
                                st.stop()
                        # Fallback case opposti ad eccezione stringa: L'implementazione si è attenuta al type model Pydantic di origine
                        else:
                            # Applica ed accoglie senza sanificazione l'oggetto nativo che soddisfa MealAnalysis BaseModel
                            analysis = raw_content

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
        st.header("💪 Personal Trainer AI")
        
        # Recupero dati utente per il contesto dell'agente
        user_data = get_user_data(st.session_state['current_user_id'])
        
        # Recupero conversazioni esistenti
        conversations = get_user_conversations(st.session_state['current_user_id'])
        
        if not conversations:
            st.info("Non hai ancora una consulenza attiva.")
            if st.button("Inizia una nuova consulenza"):
                create_new_conversation(st.session_state['current_user_id'], "Consulenza Fitness")
                st.rerun()
        else:
            # Carichiamo l'ultima conversazione (la più recente)
            active_conv = conversations[0]
            st.caption(f"Sessione: {active_conv.title}")

            # Visualizzazione cronologia messaggi dal database
            history = get_chat_history(active_conv.id)
            for msg in history:
                with st.chat_message(msg["role"]):
                    st.write(msg["content"])

            # Input dell'utente
            if prompt := st.chat_input("Chiedi al tuo trainer (es. 'Che esercizi posso fare oggi?')"):
                # 1. Mostra e salva messaggio utente
                with st.chat_message("user"):
                    st.write(prompt)
                save_message(active_conv.id, "user", prompt)

                # 2. Generazione risposta con l'agente AI
                # L'import è locale per evitare conflitti se il file non è ancora pronto
                from src.agents.fitness_agent import get_fitness_agent
                agent = get_fitness_agent(user_data)
                
                with st.chat_message("assistant"):
                    # Passiamo la history per mantenere la memoria a breve termine
                    response = agent.run(prompt, history=history)
                    st.write(response.content)
                    
                # 3. Salva risposta dell'assistente nel database
                save_message(active_conv.id, "assistant", response.content)

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
            with col2:
                height = st.number_input(
                    "Altezza (cm)", min_value=100.0, max_value=250.0, 
                    value=float(user_data['height']) if user_data['height'] else 170.0,
                    step=0.5
                )
                
            # Campo numerico per l'inserimento del peso obiettivo desiderato
            target_weight = st.number_input(
                "Peso Obiettivo (kg)", min_value=30.0, max_value=250.0, 
                value=float(user_data['target_weight']) if user_data['target_weight'] else 70.0,
                step=0.1
            )
            
            # Menu a tendina per selezionare la tipologia di obiettivo nutrizionale
            goal_type = st.selectbox(
                "Tipo di Obiettivo", 
                options=["dimagrimento", "mantenimento", "massa"],
                index=0
            )
            
            if st.form_submit_button("Salva Modifiche"):
                update_user_profile(st.session_state['current_user_id'], weight, height, age, target_weight, goal_type)
                st.success("Profilo aggiornato!")
                st.rerun()

if __name__ == "__main__":
    main()
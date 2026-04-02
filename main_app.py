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
    calculate_daily_macros
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
    # Componente UI principale dedicato al tracciamento e all'analisi nutrizionale multimodale.
    # Gestisce il ciclo di vita dell'acquisizione dell'asset visivo, il calcolo algoritmico
    # del fabbisogno quotidiano (BMR/TDEE) e orchestra le transazioni con l'agente LLM 
    # per la classificazione e la persistenza strutturata dei macro-nutrienti estratti.
    # Autore: Stefano Bellan (20054330)
    with tab_nutrizione:
        # Renderizza l'intestazione principale della dashboard nutrizionale
        st.header("📊 Dashboard Nutrizionale")
        
        # Interroga il layer di servizio per calcolare i target metabolici basati sulle metriche utente
        daily_targets = calculate_daily_macros(st.session_state['current_user_id'])

        # Ripartisce la UI in un layout a griglia con due colonne di area equivalente
        col1, col2 = st.columns(2)
        
        with col1:
            # Espone il Total Daily Energy Expenditure (TDEE), o fabbisogno di mantenimento
            st.metric("Fabbisogno Calorico Giornaliero (TDEE)", f"{daily_targets['tdee']} kcal")
            
        with col2:
            # Espone il target calorico corretto asimmetricamente in dipendenza dalla tipologia di obiettivo
            st.metric("Obiettivo Calorico Giornaliero", f"{daily_targets['target_calories']} kcal")

        # Inserisce un padding strutturale e un nuovo livello di gerarchia per la sezione dei marconutrienti
        st.divider()
        st.subheader("I tuoi Macronutrienti")
        
        # Genera tre slot orizzontali per allocare le proiezioni nutrizionali di base
        mcol1, mcol2, mcol3 = st.columns(3)
        
        with mcol1:
            # Rendering del fabbisogno plastico raccomandato (Proteine)
            st.metric("Proteine", f"{daily_targets['proteins']} g")
            
        with mcol2:
            # Rendering del fabbisogno lipidico raccomandato (Grassi)
            st.metric("Grassi", f"{daily_targets['fats']} g")
            
        with mcol3:
            # Rendering del fabbisogno energetico residuo (Carboidrati)
            st.metric("Carboidrati", f"{daily_targets['carbohydrates']} g")
        
        # Instanzia il componente di upload, validando a livello applicativo l'MIME type per mitigare rischi
        uploaded_file = st.file_uploader("Carica la foto del tuo pasto...", type=["jpg", "jpeg", "png"])
        
        # Verifica la presenza del buffer binario file in ingresso
        if uploaded_file is not None:
            # Effettua la deserializzazione dell'immagine avvalendosi di PIL_Image per predisporre l'anteprima
            image = Image.open(uploaded_file)
            st.image(image, caption="Anteprima del Pasto", use_container_width=True)
            
            # Bootstrapping dell'agente reattivo designato al parsing e validazione nutrizionale
            agent = NutritionistAgent()
            
            # Definisce il trigger di evento action-oriented per innescare l'inferenza asincrona
            if st.button("Analizza Pasto"):
                # Evoca uno spinner di feedback per minimizzare percezioni di blocco applicativo
                with st.spinner("L'Agente AI sta analizzando l'immagine..."):
                    try:
                        # Predispone un file virtuale sul filesystem host in quanto la dipendenza Agno richiede hard link pass-through
                        with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as tmp_file:
                            tmp_file.write(uploaded_file.getvalue())
                            tmp_path = tmp_file.name
                        
                        # Invocazione sincrona dell'engine con pattern di costrizione, forzando output strutturati
                        response = agent.run(
                            "Analizza accuratamente l'immagine del pasto. "
                            "DEVI restituire i dati seguendo rigorosamente lo schema MealAnalysis: "
                            "1. analysis_result: una breve descrizione. "
                            "2. calories, proteins, carbohydrates, fats: solo numeri (stima media). "
                            "NON aggiungere chiacchiere extra, rispondi solo con i dati strutturati.", 
                            images=[AgnoImage(filepath=tmp_path)],
                            response_model=MealAnalysis
                        )
                        
                        # Estrazione del payload raw di risposta generato dallo schema
                        raw_content = response.content

                        # Gestisce dinamicamente il fallback text/json qualora avvenga un bypass dell'entity nativa
                        if isinstance(raw_content, str):
                            try:
                                # Normalizza la stringa epurando artefatti markdown introdotti tipicamente dall'LLM
                                clean_json = raw_content.replace("```json", "").replace("```", "").strip()
                                # Marshalling dell'oggetto instanziando il data model Pydantic validato
                                analysis = MealAnalysis.model_validate_json(clean_json)
                            except Exception as e:
                                # Intercetta malformazioni sintattiche JSON prevenendo il crash kernel dell'applicativo 
                                st.error(f"Errore nel parsing del JSON: {e}")
                                st.write("Dati ricevuti:", raw_content)
                                st.stop()
                        else:
                            # Pass-through in caso di type match sull'oggetto desiderato
                            analysis = raw_content

                        # Generazione UI finali: esposizione della descrizione generalistica
                        st.info(analysis.analysis_result)

                        # Isolamento visivo dei dati tabellari finali estratti dal pasto analizzato
                        res_col1, res_col2, res_col3 = st.columns(3)
                        res_col1.metric("Calorie", f"{analysis.calories} kcal")
                        res_col2.metric("Proteine", f"{analysis.proteins} g")
                        res_col3.metric("Grassi", f"{analysis.fats} g")

                        # Serializza il dump ed aggancia permanentemente lo snapshot analisi via ORM al context-user attivo
                        save_meal_log(
                            user_id=st.session_state['current_user_id'],
                            analysis_result=analysis.model_dump_json()
                        )
                        st.success("Analisi salvata con successo!")

                        # Esegue un cleanup esplicito dello swap file in ossequio ai pattern di disk-hygiene
                        os.remove(tmp_path)
                        
                    except Exception as e:
                        # Gestore di sistema di ultima istanza preposto alla cattura di faults di rete e file I/O
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

if __name__ == "__main__":
    main()
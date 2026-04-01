import streamlit as st
import os
from dotenv import load_dotenv

# Importazione dei servizi del database (Inclusi i nuovi per la gestione chat)
from src.database.user_service import (
    get_all_users, 
    create_user, 
    update_user_profile, 
    get_user_data,
    get_user_conversations,
    create_new_conversation,
    save_message,
    get_chat_history
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

    with tab_nutrizione:
        st.header("Analisi Pasto")
        st.write("Qui caricheremo le foto per l'agente Nutrizionista.")

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
                
            goals = st.text_area(
                "Obiettivi", value=user_data['goals'] if user_data['goals'] else ""
            )
            
            if st.form_submit_button("Salva Modifiche"):
                update_user_profile(st.session_state['current_user_id'], weight, height, age, goals)
                st.success("Profilo aggiornato!")

if __name__ == "__main__":
    main()
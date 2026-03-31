import streamlit as st
import os
from dotenv import load_dotenv

# --- CONFIGURAZIONE INIZIALE ---
def setup_environment() -> None:
    """
    Carica le variabili d'ambiente e verifica i requisiti minimi di avvio.
    """
    # Carica le variabili dal file .env nel dizionario os.environ
    load_dotenv()
    
    # Validazione fail-fast: controlla l'esistenza della chiave API
    if not os.getenv("GEMINI_API_KEY"):
        st.error("Errore critico: GEMINI_API_KEY non trovata. Controlla il file .env.")
        st.stop() # Ferma l'esecuzione di Streamlit immediatamente

def init_session_state() -> None:
    """
    Inizializza lo stato dell'applicazione per l'utente corrente.
    Garantisce che le variabili esistano prima di essere invocate dalla UI.
    """
    # Utilizziamo il pattern Singleton-like offerto da st.session_state
    if 'current_user_id' not in st.session_state:
        st.session_state['current_user_id'] = None
    
    if 'app_initialized' not in st.session_state:
        st.session_state['app_initialized'] = True

# --- ENTRY POINT DELL'APPLICAZIONE ---
def main() -> None:
    """
    Funzione principale che definisce il layout e il routing della Single Page Application.
    """
    # 1. Configurazione della pagina (deve essere il primo comando Streamlit)
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
        # Placeholder per il futuro selettore utente
        st.selectbox("Seleziona Utente", ["Utente Test", "Nuovo Utente..."], key="user_selector")
        st.markdown("---")
        st.info("Agenti attivi:\n- 🥗 Nutrizionista\n- 🏋️ Personal Trainer")

    # 4. Costruzione della UI - Area Principale (Routing tramite Tabs)
    st.title("Benvenuto in RepEats")
    st.write("La tua piattaforma multi-agente per fitness e nutrizione.")

    # Creazione delle schede logiche per dividere le funzionalità
    tab_nutrizione, tab_allenamento, tab_profilo = st.tabs([
        "🥗 Nutrizione (Agente)", 
        "💪 Allenamento (Agente)", 
        "👤 Profilo Utente"
    ])

    with tab_nutrizione:
        st.header("Analisi Pasto")
        st.write("Qui caricheremo le foto per l'agente Nutrizionista (Gemini Vision).")
        # TODO: Implementare l'interfaccia chat per l'agente Nutrizionista

    with tab_allenamento:
        st.header("Schede di Allenamento")
        st.write("Qui interagirai con l'agente Personal Trainer per i tuoi workout.")
        # TODO: Implementare l'interfaccia chat per l'agente Personal Trainer

    with tab_profilo:
        st.header("Gestione Dati e Misurazioni")
        st.write("Qui implementeremo il modulo SQLite per salvare altezza, peso e obiettivi.")
        # TODO: Implementare la form di salvataggio dati su database

# Python idiom per garantire che main() venga eseguito solo se il file è avviato direttamente
if __name__ == "__main__":
    main()
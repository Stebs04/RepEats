# Relazione di Progetto: RepEats (Agno Multi-Agent System)

![Agno](https://img.shields.io/badge/Agno-Multi_Agent_Framework-222222?logo=robot&logoColor=white)
![Python](https://img.shields.io/badge/Python-3.11-3776AB?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-009688?logo=fastapi&logoColor=white)
![SQLite](https://img.shields.io/badge/SQLite-003B57?logo=sqlite&logoColor=white)
![Alembic](https://img.shields.io/badge/Alembic-Migrations-6BA81E)
![LanceDB](https://img.shields.io/badge/LanceDB-Serverless_VectorDB-purple)
![Groq](https://img.shields.io/badge/Groq-LPU_Inference-f55036)
![TailwindCSS](https://img.shields.io/badge/TailwindCSS-38BDF8?logo=tailwindcss&logoColor=white)

**Team di Sviluppo:**
* Stefano Bellan (Matricola: 20054330)
* Timothy Giolito (Matricola: 20054431)

---

## 1. Obiettivo del Progetto

RepEats è un'applicazione web basata su un sistema multi-agente che funge da **assistente personale per fitness e nutrizione**. L'utente crea schede di allenamento personalizzate tramite un **Personal Trainer AI** (Coach), riceve feedback nutrizionali smart da un **Nutrizionista AI** — via chat discorsiva, riconoscimento immagini dei pasti e lettura barcode — e gestisce il proprio profilo biometrico.

L'architettura si fonda su tre principi cardine:

1. **Bassa latenza**: inferenza su Groq (LPU) con il modello leggero `llama-4-scout-17b-16e-instruct`, ed embedding locali (MiniLM) senza chiamate di rete.
2. **Prevenzione delle allucinazioni**: RAG isolato per dominio (ogni agente vede solo i propri documenti) e una **rete di sicurezza deterministica** che verifica lo stato del database invece di fidarsi del testo generato dall'LLM.
3. **Isolamento dei task**: routing strutturale — nel team è presente **solo** l'agente della pagina corrente, rendendo impossibile un instradamento errato da parte dell'LLM.

---

## 2. Architettura AI e Stack Tecnologico Dettagliato

### 2.1 Motore di Inferenza (LLM)

| Componente | Modello | Provider | Motivazione |
|---|---|---|---|
| **Orchestratore, Coach, Nutrizionista, Vision, Parser** | `meta-llama/llama-4-scout-17b-16e-instruct` | Groq | Le Language Processing Units di Groq offrono latenze estremamente ridotte. Llama 4 Scout è multimodale (vision) e multilingue nativo, coprendo con un solo modello chat testuale, analisi immagini dei pasti e parsing strutturato. |

Il modello è iniettato tramite il wrapper `agno.models.groq.Groq`. Il numero di run per messaggio varia per flusso: la chat è single-run (con un eventuale run di *recovery*, vedi §2.5), mentre l'analisi di un pasto da immagine è un pipeline a due/tre stadi (§3.4).

---

### 2.2 Architettura RAG (Retrieval-Augmented Generation)

La knowledge base è costruita dal builder centralizzato `src/database/knowledge_base.py` (unica sorgente di verità per gli oggetti `Knowledge` di Agno), con una **cache a singleton per dominio** che evita di ricaricare il modello di embedding ad ogni messaggio.

#### 2.2.1 Vector Database — LanceDB

**Scelta:** [LanceDB](https://lancedb.github.io/lancedb/), database colonnare *serverless* e persistente su file system.

**Motivazione:**
- **Serverless**: nessun server separato. I dati vivono in locale in `src/database/lancedb_vectors/`.
- **Hybrid Search nativa**: combina ricerca vettoriale (dense, semantica) e ricerca lessicale **FTS/BM25** in un unico engine. L'indice full-text sulla colonna `payload` viene creato automaticamente da Agno alla prima query hybrid — nessuna dipendenza esterna (es. Tantivy) richiesta.
- **Persistenza**: la KB sopravvive ai riavvii senza re-embedding.

```python
Knowledge(
    vector_db=LanceDb(
        table_name=table_name,                 # per dominio (vedi sotto)
        uri=db_dir,
        embedder=SentenceTransformerEmbedder(id=EMBEDDER_ID),
        search_type=SearchType.hybrid,          # vettoriale + BM25
        reranker=_build_reranker(),             # opzionale, vedi 2.2.3
    )
)
```

#### 2.2.2 Isolamento per Dominio

Ogni dominio applicativo ha **una tabella LanceDB dedicata**:

| Dominio | Tabella | Consumata da |
|---|---|---|
| `fitness` | `protocolli_allenamento` | Coach (Personal Trainer) |
| `nutrition` | `conoscenza_nutrizione` | Nutrizionista |

L'isolamento impedisce che un agente recuperi documenti dell'altro dominio (es. il Coach che pesca tabelle nutrizionali). Il routing del documento nella KB corretta avviene tramite il campo `domain` di un sidecar `<nome>.meta.json` a fianco del sorgente; senza sidecar il dominio di default è `fitness`.

#### 2.2.3 Modello di Embedding e Reranker

**Embedder:** `sentence-transformers/all-MiniLM-L6-v2` (384 dimensioni), eseguito **in locale** via `SentenceTransformerEmbedder`. Scelto per leggerezza e assenza di costi/latenza di rete. Cambiarlo richiede rigenerare gli indici, perché ne cambia la dimensionalità dei vettori.

**Reranker (opzionale):** un cross-encoder leggero (`cross-encoder/ms-marco-MiniLM-L-6-v2`, ~80 MB) che riordina i risultati per rilevanza. È **disattivato di default** per tenere le KB leggere e si abilita con la variabile d'ambiente `RAG_RERANK=1`; il numero di documenti trattenuti dopo il reranking è configurabile con `RAG_RERANK_TOP_N`.

#### 2.2.4 Pipeline di Ingestion e Idempotenza

La pipeline di sincronizzazione vive in `src/knowledge_base/ingest.py` ed è invocata automaticamente all'avvio in `main.py` tramite `sync()`. `sync()` allinea l'indice con la cartella `src/knowledge_base/docs/`:

- **indicizza** i documenti nuovi;
- **ri-indicizza** i modificati (rilevati via manifest `mtime`/dimensione);
- **rimuove** dall'indice quelli eliminati dal disco.

Lo stato è tracciato in `lancedb_vectors/.ingest_manifest.json`, garantendo riavvii rapidi (i documenti invariati vengono saltati). Formati supportati: `.txt`, `.md`, `.pdf`, `.docx`. Chunking configurabile via `RAG_CHUNK_SIZE` / `RAG_CHUNK_OVERLAP`.

**Comandi manuali:**
```bash
python -m src.knowledge_base.ingest                          # sincronizza docs/ con l'indice
python -m src.knowledge_base.ingest --full                   # re-indicizza tutto
python -m src.knowledge_base.ingest --delete NOME --domain fitness   # rimuove un documento
```

#### 2.2.5 RAG "classico" senza tool

Entrambi gli agenti usano `add_knowledge_to_context=True` con `search_knowledge=False`: i documenti pertinenti vengono recuperati e **iniettati direttamente nel prompt ad ogni turno**, senza dipendere dal fatto che il modello decida di chiamare un tool di ricerca. Scelta deliberata: `llama-4-scout` è inaffidabile nel decidere *quando* interrogare la KB, quindi togliamo la decisione all'LLM.

---

### 2.3 Difesa e Sicurezza (Guardrails)

#### 2.3.1 Prompt Injection Guardrail

Ogni agente (Orchestratore, Coach, Nutrizionista, Vision) monta il `PromptInjectionGuardrail` di Agno come **`pre_hook`**: viene eseguito *prima* di ogni run, intercettando jailbreak/injection/roleplay-bypass **in qualsiasi lingua** prima che il messaggio raggiunga il modello.

#### 2.3.2 Separazione Istruzioni/Dati (anti-injection strutturale)

I dati biometrici, l'intake nutrizionale e la cronologia chat sono **contenuto da processare, non istruzioni**. Vengono incapsulati in tag XML dedicati (`<user_context>`, `<chat_history>`) e i system prompt impongono esplicitamente di trattare tutto ciò che è dentro quei tag come semplice testo, ignorando qualunque comando, cambio di ruolo o tentativo di override annidato. Così il testo generato dall'utente resta confinato e non può diventare regola di sistema.

---

## 3. Il Team di Agenti (Framework Agno)

L'orchestrazione vive in `src/orchestrator.py`. Il **Team Agno opera in `TeamMode.route`**: riceve la richiesta e la instrada al membro corretto, restituendo la risposta dell'agente specializzato **senza modificarla**.

### 3.1 Orchestratore (Il Router)

* **Modalità:** `TeamMode.route` con streaming abilitato.
* **Routing strutturale:** la selezione del membro **non** è affidata alle istruzioni dell'LLM (che potrebbe ignorarle). In base alla pagina corrente (`chat_type`), nel team viene inserito **solo** l'agente competente — Coach sulla pagina *Coach*, Nutrizionista sulla pagina *Nutrition* — rendendo *impossibile* un routing errato.
* **Memoria Condivisa:** costruisce e inietta un contesto condiviso (`build_user_context`) contenente dati biometrici, intake calorico odierno vs. target, un'**analisi temporale dell'intake** (fascia oraria corrente e range di intake atteso, così il Coach non allarma l'utente se non è ancora sera) e la cronologia della conversazione.

### 3.2 Fitness Agent — Coach (Personal Trainer)

* **Focus:** programmazione allenamenti, schede, esercizi, tecnica, recupero, motivazione.
* **Knowledge Base:** RAG sui protocolli ufficiali di allenamento (`protocolli_allenamento`).
* **Tools di persistenza:**
  - `create_workout_plan_tool` — salva una nuova scheda;
  - `modify_workout_plan_tool` — aggiorna una scheda esistente;
  - `get_workout_plan_tool` — legge una scheda (usato in Fase 1 per non perdere esercizi in modifica).
* **Human-in-the-loop (2 fasi):** salvare è una **scrittura** e richiede conferma esplicita. **Fase 1** — propone la scheda in Markdown senza chiamare tool. **Fase 2** — solo dopo un "ok" dell'utente chiama fisicamente il tool. Schede su più giorni ⇒ una scheda separata per giorno (tool chiamato più volte).
* **Vincolo temporale rigido:** la scheda deve rientrare nel *tempo a disposizione* dell'utente; l'agente stima la durata (serie × (esecuzione + recupero) + riscaldamento/defaticamento) e taglia se sfora.
* **Controllo nutrizionale pre-allenamento:** legge l'intake dal contesto e avvisa (senza bloccare) se l'utente si allena troppo a digiuno.
* **Limiti:** non fornisce consigli nutrizionali; rimanda alla sezione Nutrition.

### 3.3 Nutritionist Agent

Diviso in classi distinte per aggirare un limite dell'API Groq: **vision + function calling + structured output non coesistono in una singola chiamata**. Separando le fasi, ogni agente fa una cosa sola.

* **`ConversationalNutritionistAgent`** — chat discorsiva. Legge l'intake odierno dal contesto, calcola i **macro rimanenti** rispetto al target e suggerisce pasti/ricette coerenti. Rispetta **allergie e restrizioni dietetiche** del profilo (vincolo obbligatorio iniettato nel prompt). RAG su `conoscenza_nutrizione` (tabelle SINU, linee guida). Non chiama mai tool: risponde solo testo.
* **`VisionNutritionistAgent`** — analizza immagini di cibo/barcode e risponde in **testo libero** (poi validato dal Parser). Con barcode usa il tool `get_product_info_by_barcode` (OpenFoodFacts); su foto di cibo puro il tool non viene nemmeno registrato, così non può usarlo per errore e stima i macro dalla categoria.

### 3.4 Pipeline di Analisi Pasto da Immagine (`POST /api/chat/vision`)

L'analisi di un pasto è un pipeline deterministico-poi-generativo, a stadi:

* **Fase 0 — Barcode (deterministica, no LLM):** priorità al codice inserito a mano dall'utente (fallback robusto a foto sfocate); altrimenti detection sui pixel con OpenCV/zxing-cpp. Se c'è un barcode valido, i dati OpenFoodFacts vengono scalati sulla grammatura **in Python**, senza stima LLM (zero allucinazioni sui valori).
* **Fase 1 — Stima visiva:** solo se non c'è barcode o il prodotto non è trovato. `VisionNutritionistAgent` (senza tool) riconosce l'alimento e stima i macro scalati sulla grammatura.
* **Fase 2 — Parser:** un agente dedicato converte il testo libero in un `MealAnalysis` (Pydantic) tipizzato, che viene poi salvato come `MealLog`.

---

### 2.5 Rete di Sicurezza Anti-Hallucination (Coach)

> Questa è la difesa ingegneristica centrale del progetto — dettagli anche in [`docs/LLM_ARCHITECTURE.md`](docs/LLM_ARCHITECTURE.md).

Il Coach salva le schede via **Tool Calling autonomo** (decide da solo quando invocare i tool). Il limite intrinseco degli LLM è l'**action hallucination**: l'agente può generare *"Ho salvato la tua scheda Push A"* **senza aver realmente emesso la tool call**. Il testo mente ed è indistinguibile da un successo reale.

L'unica fonte di verità è lo **stato del database**. La rete di sicurezza in `backend/chat_api.py`:

1. **Snapshot deterministico (`_workout_snapshot`)** — prima della run fotografa le schede (id, nomi, esercizi con set/reps/recupero) in una tupla comparabile; a fine run rifotografa. `snapshot_dopo != snapshot_prima` è l'unico segnale deterministico di scrittura reale.
2. **Rilevazione discrepanza** — incrocia due segnali: il testo *dichiara* un salvataggio (`claims_save`, semantico e inaffidabile) **e** il DB è *invariato* (deterministico). Testo che promette + DB fermo = tool non chiamato.
3. **`recovery_prompt` auto-riparante** — inietta un messaggio di sistema **invisibile all'utente** che re-innesca l'agente forzandolo a chiamare *adesso* il tool corretto, ricavando scheda ed esercizi dal proprio testo. La risposta già mostrata resta intatta; il salvataggio avviene dietro le quinte. Dopo il recovery si ri-verifica lo snapshot.

---

## 4. Architettura Software

### 4.1 Stack Tecnologico Completo

| Layer | Tecnologia |
|---|---|
| Backend API | FastAPI + Uvicorn |
| Frontend | HTML5 + TailwindCSS (CDN) + Vanilla JavaScript |
| Database Relazionale | SQLite (via SQLAlchemy) |
| Migrazioni schema | Alembic |
| Vector Database | LanceDB (Hybrid Search) |
| Framework Multi-Agent | Agno |
| Embedding | SentenceTransformers (all-MiniLM-L6-v2) |
| LLM | Groq (`llama-4-scout-17b-16e-instruct`) |
| Barcode | zxing-cpp (primario) + OpenCV (fallback/pre-processing) |
| Dati prodotti | OpenFoodFacts API |
| Autenticazione | JWT (PyJWT) + bcrypt |

### 4.2 Database (SQLite + SQLAlchemy)

* **User** — username, email, password con hashing **bcrypt**.
* **UserProfile** — relazione 1-a-1: età, peso, altezza, sesso, LAF, obiettivo, target, preferenze di allenamento, allergie e restrizioni dietetiche.
* **Conversation & Message** — 1-a-N; cronologia chat isolata per `chat_type` (`"coach"` / `"nutritionist"`).
* **MealLog** — pasti consumati con calorie, macro, nome, categoria, timestamp.
* **WorkoutPlan & WorkoutExercise** — schede AI e relativi esercizi (set, reps, recupero).

### 4.3 Autenticazione (JWT)

Login/registrazione in `backend/auth.py`. Le rotte protette ricavano l'identità **esclusivamente dal token JWT (Bearer)**, mai dal client — anche negli endpoint di chat e vision `user_id = current_user` viene dal token, non dal payload. Password hashate con bcrypt.

### 4.4 Migrazioni Schema (Alembic)

Lo schema **non** viene più creato automaticamente all'avvio (niente `create_all()`): l'evoluzione è gestita da [Alembic](https://alembic.sqlalchemy.org/) con migrazioni versionate in `alembic/versions/`. All'avvio l'app verifica soltanto che il DB sia raggiungibile. Alembic legge `DATABASE_URL` dal `.env`.

### 4.5 Comunicazione Frontend-Backend (SSE)

La chat espone le risposte in **streaming token-per-token** via **Server-Sent Events**. In `mode=route` gli eventi `RunContentEvent` di livello team trasportano il testo dell'agente instradato. Protocollo eventi:

- `{"type": "start", "conversation_id": <id>}` — una volta, prima del testo;
- `{"type": "content", "delta": "<pezzo>"}` — N volte, token per token;
- `{"type": "end", "workouts_updated": <bool>}` — a fine risposta (riflette l'esito reale della rete di sicurezza);
- `{"type": "error", "detail": "<msg>"}` — in caso di errore.

Il frontend Vanilla JS comunica via Fetch API con un **Auth Guard** in cima ad ogni script; `user_id` e token sono persistiti in `sessionStorage`/`localStorage`.

---

## 5. Guida all'Avvio

### Prerequisiti
- **Python 3.11**
- **API Key Groq** ([console.groq.com](https://console.groq.com))

### Configurazione Iniziale — il file `.env` (obbligatorio)

Nella root del progetto crea un file `.env` copiando `.env.example`:

```env
GROQ_API_KEY=inserisci_qui_la_tua_api_key_groq
OPENFOODFACTS_APP_NAME=RepEats_University_Project_v1
DATABASE_URL=sqlite:///repeats_local.db
```

> Senza `.env` correttamente configurato l'applicazione non parte. Verificalo **ogni volta** prima dell'avvio.

### Setup del database (Alembic)

Su un database nuovo/vuoto, crea le tabelle applicando le migrazioni:

```bash
alembic upgrade head
```

Se hai già un DB creato dalla vecchia logica `create_all()`, allinea lo stato senza rieseguire le CREATE:

```bash
alembic stamp head
```

### Avvio

Gli script inclusi creano il venv, installano le dipendenze, aprono il browser e avviano il server sulla porta **8000**.

* **Windows:** `start.bat`
* **macOS/Linux:** `chmod +x start.sh && ./start.sh`

**Avvio manuale:**
```bash
python -m venv venv
# Windows:  venv\Scripts\activate
# Linux/macOS:  source venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

---

## 6. Cosa Aspettarsi al Primo Avvio

All'avvio l'app verifica la raggiungibilità del DB e sincronizza la Knowledge Base (`sync()`): indicizza in LanceDB i documenti presenti in `src/knowledge_base/docs/`. La prima volta l'embedding richiede alcune decine di secondi (download di MiniLM + indicizzazione); ai riavvii successivi il manifest di idempotenza salta i documenti invariati, rendendo l'operazione quasi istantanea.

L'app è servita su `http://127.0.0.1:8000`; la root reindirizza al frontend. Dopo il login puoi chattare con **Coach** (schede) e **Nutrition** (pasti, chat, foto/barcode).

---

## 7. Troubleshooting

### 7.1 Conflitto Vision + Tool + Structured Output (Groq)

**Sintomo:** errori API o risposte vuote quando si tenta analisi immagine, chiamata tool e output JSON nella stessa run.

**Causa:** l'API Groq non supporta la coesistenza di vision, function calling e structured output in una singola chiamata.

**Soluzione (già implementata):** il flusso pasto è spezzato in fasi separate (Vision → Parser, vedi §3.4). Ogni agente fa una sola cosa per chiamata.

### 7.2 Barcode non letto dalla foto

**Sintomo:** un pasto con codice a barre viene stimato visivamente invece che letto da OpenFoodFacts.

**Causa:** immagine troppo sfocata/rumorosa per il decoder (zxing-cpp/OpenCV).

**Soluzione:** inserisci il codice a mano nel campo dedicato — ha priorità sullo scan automatico (se plausibile, 8-14 cifre, viene usato direttamente).

---

## 8. Suddivisione del Lavoro

Stefano si è occupato del **Nutrizionista**, Timothy del **Coach**; il resto dell'applicativo è stato diviso equamente.

| Componente | Responsabile |
|---|---|
| **Nutrizionista** (Conversational + Vision + Parser, pipeline immagine, OpenFoodFacts, barcode) | Stefano |
| **Coach** (Personal Trainer, tool schede, human-in-the-loop, vincolo temporale) | Timothy |
| Orchestratore e routing strutturale | Timothy |
| Knowledge Base & pipeline RAG (LanceDB, ingestion, embedder) | Stefano |
| Rete di sicurezza anti-hallucination | Stefano |
| Database, ORM & migrazioni Alembic | Timothy |
| Autenticazione JWT & bcrypt | Timothy |
| API FastAPI & streaming SSE | Stefano |
| Frontend (HTML/Tailwind/Vanilla JS) | Stefano & Timothy |
| Guardrails & separazione istruzioni/dati | Stefano & Timothy |

---

## 9. Utilizzo di Strumenti AI

Durante lo sviluppo abbiamo usato strumenti AI come supporto — in particolare **Antigravity** e **Claude Code** — sempre sotto la nostra supervisione diretta e con validazione critica di ogni output. Ci hanno assistito in: sviluppo UI/UX, ottimizzazione dei system prompt degli agenti, integrazione frontend-backend, refactoring di funzioni complesse, scelte architetturali e stesura della documentazione.

---

**Realizzato da Stefano Bellan e Timothy Giolito.**

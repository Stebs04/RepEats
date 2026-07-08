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

1. **Bassa latenza**: inferenza su Groq (LPU) — `llama-3.3-70b-versatile` per la chat testuale e `llama-4-scout-17b-16e-instruct` per vision e parsing — con embedding locali (MiniLM) senza chiamate di rete.
2. **Prevenzione delle allucinazioni**: RAG isolato per dominio (ogni agente vede solo i propri documenti) e una **rete di sicurezza deterministica** che verifica lo stato del database invece di fidarsi del testo generato dall'LLM.
3. **Isolamento dei task**: routing strutturale — nel team è presente **solo** l'agente della pagina corrente, rendendo impossibile un instradamento errato da parte dell'LLM.

---

## 2. Architettura AI e Stack Tecnologico Dettagliato

### 2.1 Motore di Inferenza (LLM)

| Componente | Modello | Provider | Motivazione |
|---|---|---|---|
| **Orchestratore** | `llama-3.3-70b-versatile` (`max_tokens=150`, `temperature=0.1`) | Groq | Router silenzioso: deve solo delegare al membro corretto, non generare testo. Il cap a 150 token e la temperatura bassa ne tagliano l'output verboso (vedi §2.6). |
| **Coach, Nutrizionista (chat)** | `llama-3.3-70b-versatile` (`max_tokens=800`, `temperature=0.3`) | Groq | Chat testuale con function calling: 70b invoca i tool in modo affidabile, mentre Scout genera spesso `tool_use_failed` (400) sulle chiamate a funzione (es. ricerca ricette online, salvataggio scheda). Nessuna vision su questo percorso, quindi la multimodalità di Scout non serve. Cap a 800 token per contenere il consumo mantenendo spazio a scheda/ricetta. |
| **Vision, Parser** | `meta-llama/llama-4-scout-17b-16e-instruct` | Groq | Le Language Processing Units di Groq offrono latenze estremamente ridotte. Scout è multimodale (vision) e multilingue nativo: copre l'analisi immagini dei pasti e il parsing strutturato che il modello di chat, privo di vision, non può gestire. |

Il modello è iniettato tramite il wrapper `agno.models.groq.Groq`. Il numero di run per messaggio varia per flusso: la chat è single-run (con un eventuale run di *salvataggio* in Fase 2 per il Coach, vedi §2.4), mentre l'analisi di un pasto da immagine è un pipeline a due/tre stadi (§3.4).

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

Il **Coach** usa `add_knowledge_to_context=True` con `search_knowledge=False`: i documenti pertinenti vengono recuperati e **iniettati direttamente nel prompt ad ogni turno**, senza dipendere dal fatto che il modello decida di chiamare un tool di ricerca. Scelta deliberata: un LLM da chat è inaffidabile nel decidere *quando* interrogare la KB, quindi togliamo la decisione all'LLM.

Il **Nutrizionista conversazionale** parte dalla stessa iniezione a contesto ma abilita anche `search_knowledge=True`: oltre ai documenti pre-caricati può interrogare autonomamente la KB. Il tool di ricerca ricette online (§3.5) **non** viene più chiamato in automatico: è dietro un human-in-the-loop (§2.5) — di default l'agente risponde solo dal RAG e chiede conferma prima di cercare sul web.

---

### 2.3 Difesa e Sicurezza (Guardrails)

#### 2.3.1 Prompt Injection Guardrail

Ogni agente (Orchestratore, Coach, Nutrizionista, Vision) monta il `PromptInjectionGuardrail` di Agno come **`pre_hook`**: viene eseguito *prima* di ogni run, intercettando jailbreak/injection/roleplay-bypass **in qualsiasi lingua** prima che il messaggio raggiunga il modello.

#### 2.3.2 Separazione Istruzioni/Dati (anti-injection strutturale)

I dati biometrici, l'intake nutrizionale e la cronologia chat sono **contenuto da processare, non istruzioni**. Vengono incapsulati in tag XML dedicati (`<user_context>`, `<chat_history>`) e i system prompt impongono esplicitamente di trattare tutto ciò che è dentro quei tag come semplice testo, ignorando qualunque comando, cambio di ruolo o tentativo di override annidato. Così il testo generato dall'utente resta confinato e non può diventare regola di sistema.

#### 2.3.3 Guardrail Off-Topic (rifiuto domande fuori ambito)

Entrambi gli agenti (Coach e Nutrizionista) rifiutano **immediatamente** qualsiasi domanda che non riguardi strettamente il proprio dominio — politica, geografia, storia, matematica, programmazione, intrattenimento, cultura generale, ecc. Il rifiuto è imposto con un **messaggio template fisso** e non ammette eccezioni: l'agente non tenta nemmeno di rispondere parzialmente. Il prompt include inoltre una **lista di frasi vietate** che impedisce al modello di rivelare il proprio processo interno (es. "ho cercato online", "elaboriamo una ricerca web").

---

### 2.4 Rete di Sicurezza Anti-Hallucination (Coach)

> Questa è la difesa ingegneristica centrale del progetto — dettagli anche in [`docs/LLM_ARCHITECTURE.md`](docs/LLM_ARCHITECTURE.md).

Il limite intrinseco degli LLM è l'**action hallucination**: l'agente può generare *"Ho salvato la tua scheda Push A"* **senza aver realmente emesso la tool call** — oppure, al contrario, chiamare il tool di scrittura **in Fase 1** saltando la conferma dell'utente. La sola disciplina del prompt non basta con nessun LLM. La difesa combina **prevenzione strutturale** e **verifica deterministica** sullo stato del DB, in `backend/chat_api.py`:

1. **Fase 1 senza tool di scrittura (prevenzione strutturale dell'human-in-the-loop)** — nel turno di proposta il Coach viene istanziato con `enable_tools=False`: i tool di scrittura **non sono nemmeno registrati**, quindi il modello *non può fisicamente salvare* né perdersi a emettere blocchi JSON nella chat. Può solo proporre la scheda in Markdown e chiedere conferma. La regola non è più affidata al prompt (che il modello ignorava): è imposta dall'architettura.
2. **Rilevazione conferma (Fase 2, deterministica)** — `_is_save_confirmation` riconosce nel messaggio utente un'affermazione esplicita ("ok", "salva", "sì"…) in risposta a una proposta del turno precedente, dopo aver rimosso il prefisso di routing (`Al Coach: `) che altrimenti impedirebbe il match.
3. **Salvataggio forzato via agente Coach diretto** — su conferma, un Coach ricostruito **con i tool abilitati** (`_save_via_tools`) esegue il `recovery_prompt`: recupera le schede ed esercizi dallo **storico della conversazione** (proposti in Fase 1) e chiama *adesso* il tool corretto. Si esegue **l'agente membro direttamente, non il Team in `route` mode**: in route-mode il leader tentava di chiamare il tool del membro senza averlo in `request.tools` (errore 400 `tool_use_failed`) e, privo dello schema, ne inventava i parametri.
   - **Disambiguazione creazione/modifica** — `_looks_like_modification` ispeziona la richiesta *precedente alla conferma*: se contiene parole di modifica (`modific`, `sovrascriv`, `aggiorn`, `cambia`…) il `recovery_prompt` impone **un solo tool**, `modify_workout_plan_tool`. Senza questa disambiguazione il modello debole, davanti a una "scheda singola", ripiegava su `create_workout_plan_tool` — che ha il *guard sul numero minimo di esercizi* (vedi §3.2) e **rifiutava la modifica di un giorno piccolo** (es. Spalle e Addominali), lasciando il DB invariato e la modifica non salvata. Per le creazioni il prompt lascia scegliere tra `create_weekly_workout_plan_tool` (piano multi-giorno) e `create_workout_plan_tool` (scheda singola).
4. **Snapshot deterministico (`_workout_snapshot`)** — prima e dopo il salvataggio fotografa le schede (id, nomi, esercizi con set/reps/recupero) in una tupla comparabile. `snapshot_dopo != snapshot_prima` è l'unico segnale reale di scrittura: solo se lo snapshot cambia si conferma all'utente `✅ Scheda salvata nel profilo.`, altrimenti un messaggio di errore onesto. Il vecchio fallback euristico "il testo dichiara un salvataggio ma il DB è fermo → salva d'ufficio" è stato **rimosso**: con la Fase 1 senza tool avrebbe potuto scrivere schede *non confermate*, violando l'human-in-the-loop.

---

### 2.5 Human-in-the-Loop Ricerca Web (Nutrizionista)

La ricerca ricette online è una **azione verso l'esterno** (scraping di un motore di ricerca): non deve partire senza il consenso dell'utente. Come per il salvataggio schede del Coach (§2.4), l'human-in-the-loop è imposto **strutturalmente**, non affidato al prompt. Due turni, in `backend/chat_api.py` + `src/agents/nutritionst.py`:

1. **Fase 1 — solo RAG (ricerca web disabilitata strutturalmente)** — alla domanda "cosa mangiare" il `ConversationalNutritionistAgent` è istanziato con `enable_search=False`: il tool `search_online_recipes` **non è nemmeno registrato**, quindi il modello *non può* cercare online. Costruisce **una** proposta fondata solo sui documenti RAG (calibrata sui macro residui, con fonte) e chiude con la domanda fissa **"Vuoi che cerchi online altre ricette?"**.
2. **Rilevazione conferma (deterministica)** — `_is_search_confirmation` riconosce un'affermazione secca ("sì", "ok", "cerca"…) **solo** se l'ultimo turno dell'assistente conteneva la domanda `...cerchi online...`: un "sì" isolato senza proposta precedente non fa mai partire una ricerca.
3. **Fase 2 — ricerca reale su conferma** — solo allora l'orchestratore ricostruisce il Nutrizionista con `enable_search=True` (tool registrato) e il messaggio "sì" dell'utente viene sostituito da una **direttiva di sistema** che ordina la ricerca online delle ricette pertinenti all'ultima richiesta (recuperata dalla cronologia), presentate come sezione *"Altre ricette trovate online"* con link cliccabili.

Così il default è conservativo (nessuna chiamata di rete non richiesta) e la ricerca parte **esclusivamente** dopo un consenso esplicito.

---

### 2.6 Ottimizzazione dei Token (limite TPM Groq)

Il limite *tokens-per-minute* di Groq è la risorsa più scarsa del sistema: superarlo genera `413 Request too large` o `429 rate_limit`. Il consumo è tenuto sotto controllo su **quattro leve**, senza toccare l'architettura Team (requisito accademico):

1. **Orchestratore silenzioso** — l'istruzione impone al router *"You are a silent router… ONLY output the tool call"* e il modello è istanziato con `max_tokens=150`, `temperature=0.1`: il leader delega senza rigenerare o commentare la risposta del membro, tagliando i token spesi in preamboli di routing.
2. **Cap rigido su `max_tokens`** — Coach e Nutrizionista girano con `max_tokens=800` (`temperature=0.3`): abbastanza per una scheda o una proposta di ricetta, ma con un tetto duro che impedisce risposte fuori scala.
3. **System prompt compressi** — le istruzioni degli agenti sono condensate (fluff e ridondanze rimosse) mantenendo intatti guardrail anti-injection, limiti di competenza, vincolo temporale e regole di salvataggio. Meno token statici iniettati ad ogni turno.
4. **Finestra di contesto ridotta** — in `backend/chat_api.py`, `_trim_history_for_context` tiene al massimo **`_MAX_CTX_MSGS = 3`** messaggi recenti e forza lo scarto dei più vecchi finché la stima payload + overhead rientra nel budget **`_TOKEN_BUDGET = 5000`**. La cronologia piena resta disponibile solo alla logica deterministica del Coach (recupero schede in Fase 2), non al payload LLM.

---

## 3. Il Team di Agenti (Framework Agno)

L'orchestrazione vive in `src/orchestrator.py`. Il **Team Agno opera in `TeamMode.route`**: riceve la richiesta e la instrada al membro corretto, restituendo la risposta dell'agente specializzato **senza modificarla**.

### 3.1 Orchestratore (Il Router)

* **Modalità:** `TeamMode.route` con streaming abilitato.
* **Router silenzioso (ottimizzazione token):** il modello (`llama-3.3-70b-versatile`) è istanziato con `max_tokens=150` e `temperature=0.1`, con l'istruzione esplicita di limitarsi a delegare al membro corretto senza produrre testo, ragionamento o preamboli (vedi §2.6). Non modifica né commenta la risposta del membro instradato.
* **Routing strutturale:** la selezione del membro **non** è affidata alle istruzioni dell'LLM (che potrebbe ignorarle). In base alla pagina corrente (`chat_type`), nel team viene inserito **solo** l'agente competente — Coach sulla pagina *Coach*, Nutrizionista sulla pagina *Nutrition* — rendendo *impossibile* un routing errato.
* **Memoria Condivisa:** costruisce e inietta un contesto condiviso (`build_user_context`) contenente dati biometrici, intake calorico odierno vs. target, un'**analisi temporale dell'intake** (fascia oraria corrente e range di intake atteso, così il Coach non allarma l'utente se non è ancora sera) e la cronologia della conversazione.

### 3.2 Fitness Agent — Coach (Personal Trainer)

* **Focus:** programmazione allenamenti, schede, esercizi, tecnica, recupero, motivazione.
* **Knowledge Base:** RAG sui protocolli ufficiali di allenamento (`protocolli_allenamento`).
* **Tools di persistenza:**
  - `create_workout_plan_tool` — salva **una singola** scheda nuova;
  - `create_weekly_workout_plan_tool` — salva un **intero piano settimanale** (più schede) in modo **atomico**: riceve una lista JSON di giorni (ognuno con `name` ed `exercises`) e li committa in un'unica transazione (tutte o nessuna, via `save_multiple_workout_plans`);
  - `modify_workout_plan_tool` — aggiorna una scheda esistente;
  - `get_workout_plan_tool` — legge una scheda (usato in Fase 1 per non perdere esercizi in modifica).
* **Due tipi di creazione:**
  - **Singola scheda** (es. "fammi un allenamento gambe") ⇒ `create_workout_plan_tool`, una chiamata.
  - **Piano settimanale** (più giorni, es. Lun/Mer/Ven) ⇒ **una sola** chiamata a `create_weekly_workout_plan_tool` con tutti i giorni: salvataggio atomico, niente schede parziali se una fallisce. Ogni singola scheda del piano deve rispettare **indipendentemente** il tempo a disposizione.
* **Human-in-the-loop (2 fasi, imposto strutturalmente):** salvare è una **scrittura** e richiede conferma esplicita. **Fase 1** — il Coach gira **senza tool di scrittura** (`enable_tools=False`): può solo proporre la/e scheda/e in Markdown e chiedere conferma, non può salvare né sbrodolare JSON nella chat. **Fase 2** — solo dopo un "ok" dell'utente un Coach tools-enabled esegue il salvataggio (vedi §2.4) e conferma con `✅ Scheda salvata nel profilo.`. La disciplina non è affidata al prompt ma all'architettura.
* **Vincolo temporale rigido (upper + lower bound):** la scheda deve **riempire** il *tempo a disposizione* del profilo, non solo starci sotto. L'agente stima la durata (serie × (esecuzione + recupero) + riscaldamento/defaticamento): se sfora **taglia**, se avanza tempo **aggiunge** esercizi, puntando all'85-100% del budget.
* **Guard sul numero minimo di esercizi (deterministico):** i tool `create_workout_plan_tool` e `create_weekly_workout_plan_tool` **rifiutano** le schede sotto-riempite (`_min_exercises_for` deriva la soglia dal *tempo a disposizione*: es. 60 min ⇒ ≥6 esercizi/giorno) con un errore azionabile che costringe il modello a rigenerare con più esercizi. Blocca alla radice il difetto del modello debole che salvava schede di 3 esercizi con 60 minuti a disposizione.
* **Controllo nutrizionale pre-allenamento:** legge l'intake dal contesto e avvisa (senza bloccare) se l'utente si allena troppo a digiuno.
* **Limiti:** non fornisce consigli nutrizionali; rimanda alla sezione Nutrition.

### 3.3 Nutritionist Agent

Diviso in classi distinte per aggirare un limite dell'API Groq: **vision + function calling + structured output non coesistono in una singola chiamata**. Separando le fasi, ogni agente fa una cosa sola.

* **`ConversationalNutritionistAgent`** — chat discorsiva. Legge l'intake odierno dal contesto, calcola i **macro rimanenti** rispetto al target e suggerisce pasti/ricette coerenti. Rispetta **allergie e restrizioni dietetiche** del profilo (vincolo obbligatorio iniettato nel prompt). RAG su `conoscenza_nutrizione` (tabelle SINU, linee guida). **Procedura "cosa mangiare" (human-in-the-loop a 2 turni, §2.5):** in **Fase 1** (`enable_search=False`, tool di ricerca non registrato) costruisce **una** ricetta principale fondata solo sui documenti **RAG**, calibrata sui macro residui e con fonte citata ("*La mia proposta*"), poi chiede **"Vuoi che cerchi online altre ricette?"** — nessuna ricerca web automatica. Solo su **conferma esplicita** dell'utente (Fase 2, `enable_search=True`) chiama il tool di **ricerca ricette online** (§3.5) e presenta **almeno 3 alternative reali** come sezione "*Altre ricette trovate online*", ognuna con link cliccabile alla fonte. Non racconta i passaggi né nomina strumenti.
* **`VisionNutritionistAgent`** — analizza immagini di cibo/barcode e risponde in **testo libero** (poi validato dal Parser). Con barcode usa il tool `get_product_info_by_barcode` (OpenFoodFacts); su foto di cibo puro il tool non viene nemmeno registrato, così non può usarlo per errore e stima i macro dalla categoria.

### 3.4 Pipeline di Analisi Pasto da Immagine (`POST /api/chat/vision`)

L'analisi di un pasto è un pipeline deterministico-poi-generativo, a stadi:

* **Fase 0 — Barcode (deterministica, no LLM):** priorità al codice inserito a mano dall'utente (fallback robusto a foto sfocate); altrimenti detection sui pixel con OpenCV/zxing-cpp. Se c'è un barcode valido, i dati OpenFoodFacts vengono scalati sulla grammatura **in Python**, senza stima LLM (zero allucinazioni sui valori).
* **Fase 1 — Stima visiva:** solo se non c'è barcode o il prodotto non è trovato. `VisionNutritionistAgent` (senza tool) riconosce l'alimento e stima i macro scalati sulla grammatura.
* **Fase 2 — Parser:** un agente dedicato converte il testo libero in un `MealAnalysis` (Pydantic) tipizzato, che viene poi salvato come `MealLog`.

### 3.5 Ricerca Ricette Online (Nutrizionista)

Oltre alla knowledge base interna, il Nutrizionista conversazionale dispone del tool `search_online_recipes` (`src/tools/online_recipe_search_tool.py`) per proporre **ricette reali e concrete** invece di limitarsi a stime generiche. È la **Fase 2** della procedura "cosa mangiare" (§3.3): la ricetta principale arriva dal RAG in Fase 1, il tool aggiunge **almeno 3 ricette trovate online**, ciascuna con titolo come link cliccabile alla fonte.

* **Trigger (human-in-the-loop, §2.5):** il tool **non** parte in automatico. È registrato ed eseguito solo nel turno di conferma, dopo che l'utente ha risposto "sì" alla domanda "Vuoi che cerchi online altre ricette?". In Fase 1 il tool non è nemmeno disponibile all'agente.
* **Contesto dedicato:** l'orchestratore inietta nel prompt un blocco **`VINCOLI PER RICERCA WEB`** con Kcal e macro target del pasto imminente (derivati dalla fascia oraria e dai residui giornalieri). I valori servono da **riferimento** per la scelta degli ingredienti, ma la query inviata al motore contiene solo ingredienti e tipo di pasto (mai numeri, che azzererebbero i match).
* **Query robusta (`_build_web_query`):** i vincoli **numerici** (kcal, grammi, nomi dei macro) e le parole riempitive (articoli, preposizioni) vengono **rimossi** dalla query prima della ricerca — non matchano nessun titolo di ricetta — e si garantisce la parola *ricetta* per puntare a siti di cucina. È l'LLM, non il motore, a filtrare poi sui macro.
* **Garanzia di ≥3 risultati — strategia a 3 livelli di fallback:** se la prima ricerca torna meno di 3 risultati, il tool **ritenta con query progressivamente più larghe**: (1) query base + GialloZafferano, (2) sole keyword + Cookist, (3) keyword essenziali + "ricetta facile" + FattoInCasaDaBenedetta. Ad ogni livello i risultati vengono uniti senza duplicati; la cascata si ferma appena si raggiungono ≥3 match.
* **Output con link markdown pronti:** ogni risultato è formattato come `[Titolo](URL)` — un link markdown che l'LLM può copiare direttamente nella risposta. Risultati senza URL http valido vengono scartati. L'istruzione allegata impone esplicitamente all'agente di presentare ogni ricetta come titolo cliccabile.
* **Motore di ricerca:** ricerca reale via endpoint HTML di DuckDuckGo (nessuna API key), con parsing tramite **BeautifulSoup** (fino a 8 risultati: titolo, link, snippet).
* **Resilienza di rete:** le eccezioni HTTP sono gestite in modo silente e degradano in un messaggio che **impone all'LLM di proporre lui una ricetta completa** (mai rimandare l'utente a cercare da solo), senza sollevare eccezioni che interromperebbero la chat.

> **Nota sullo scraping:** dipendendo dal markup HTML del motore di ricerca, il tool è per natura fragile a modifiche lato provider. Per un uso in produzione stabile è preferibile un servizio di ricerca dotato di API ufficiale.

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
| LLM | Groq (`llama-3.3-70b-versatile` chat, `llama-4-scout-17b-16e-instruct` vision/parser) |
| Barcode | zxing-cpp (primario) + OpenCV (fallback/pre-processing) |
| Dati prodotti | OpenFoodFacts API |
| Ricerca ricette online | DuckDuckGo (HTML) + BeautifulSoup |
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

Lo schema **non** viene creato con `create_all()`: l'evoluzione è gestita da [Alembic](https://alembic.sqlalchemy.org/) con migrazioni versionate in `alembic/versions/`. Alembic legge `DATABASE_URL` dal `.env`.

**Primo avvio automatico:** all'avvio `init_database()` verifica la raggiungibilità del DB e controlla l'esistenza della tabella `alembic_version`. Se assente (database vergine), esegue **automaticamente** `alembic upgrade head` via API Python, creando lo schema completo. Ai successivi avvii il controllo rileva la tabella già presente e salta le migrazioni.

### 4.5 Comunicazione Frontend-Backend (SSE)

La chat espone le risposte in **streaming token-per-token** via **Server-Sent Events**. In `mode=route` gli eventi `RunContentEvent` di livello team trasportano il testo dell'agente instradato. Protocollo eventi:

- `{"type": "start", "conversation_id": <id>}` — una volta, prima del testo;
- `{"type": "content", "delta": "<pezzo>"}` — N volte, token per token;
- `{"type": "end", "workouts_updated": <bool>}` — a fine risposta (riflette l'esito reale della rete di sicurezza);
- `{"type": "error", "detail": "<msg>"}` — in caso di errore.

Il frontend Vanilla JS comunica via Fetch API con un **Auth Guard** in cima ad ogni script; `user_id` e token sono persistiti in `sessionStorage`.

---

## 5. Test e Valutazione (Evals)

### 5.1 Suite di Valutazione — `evals.py` (LLM-as-a-Judge)

Il progetto **non usa test unitari classici**: gli output degli agenti non sono deterministici, quindi la qualità si misura con una **suite di valutazione quantitativa** in cui un secondo LLM giudica le risposte degli agenti reali. Lo script `evals.py` (root del progetto):

1. Carica il dataset di test da `eval_dataset.json`.
2. Genera le risposte facendole passare per gli **agenti reali** tramite l'orchestratore (`get_orchestrator`), con `enable_tools=False` per non scrivere sul DB durante la valutazione. Nessuna logica duplicata: si valuta ciò che l'utente riceve in produzione.
3. Ogni risposta è giudicata da un **LLM giudice rigoroso** (stesso modello Groq), che restituisce un verdetto JSON `pass/fail`.
4. Stampa un report tabellare con il **Pass Rate %** per categoria.

**Metriche valutate** (campo `metric` di ogni caso):

| Metrica | Agente | Cosa verifica il giudice |
|---|---|---|
| `time_constraint` | Coach | La scheda proposta rientra nel tetto di minuti (`max_minutes`), tolleranza +10%. |
| `macro_accuracy` | Nutrizionista | I macro citati rispettano `kcal ≈ 4·P + 4·C + 9·G` (tolleranza ±20%) e sono plausibili, senza allucinazioni. |
| `language_match` | Entrambi | La risposta è nella stessa lingua (`expected_language`) dell'ultimo messaggio utente. |

**Esecuzione:**
```bash
python evals.py            # esegue tutto il dataset
python evals.py --limit 4  # solo i primi 4 casi (smoke test)
```

Richiede `GROQ_API_KEY` impostata (in `.env` o ambiente). Il modello giudice è configurabile via `JUDGE_MODEL`.

### 5.2 Aggiungere casi di test

I casi vivono nell'array `conversations` di `eval_dataset.json`. Un caso è un oggetto JSON:

```json
{
  "id": "nut_09_yogurt_150g",
  "agent": "nutritionist",
  "metric": "macro_accuracy",
  "message": "Macro di 150g di yogurt greco 0%?",
  "user_data": {}
}
```

Campi: `id` univoco, `agent` (`"coach"`/`"nutritionist"`), `metric` (una delle tre sopra), `message` (input utente). Extra per metrica: `max_minutes` per `time_constraint`, `expected_language` per `language_match`. Opzionali: `chat_history`, `user_data`, `macros`, `daily_targets` (sovrascrivono i default di `evals.py`).

---

## 6. Guida all'Avvio

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

### Setup del database

**Nessun comando manuale richiesto.** Al primo avvio l'applicazione rileva automaticamente un database vergine (tabella `alembic_version` assente) e applica tutte le migrazioni Alembic, creando lo schema completo. Ai successivi avvii viene eseguito solo un controllo di connettività.

> Se hai già un DB creato dalla vecchia logica `create_all()` senza migrazioni, allinea lo stato manualmente una tantum:
> ```bash
> alembic stamp head
> ```

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

## 7. Cosa Aspettarsi al Primo Avvio

All'avvio l'app verifica la raggiungibilità del DB; se il database è vergine (primo avvio in assoluto), **applica automaticamente le migrazioni Alembic** creando tutte le tabelle — non serve eseguire `alembic upgrade head` a mano. Successivamente sincronizza la Knowledge Base (`sync()`): indicizza in LanceDB i documenti presenti in `src/knowledge_base/docs/`. La prima volta l'embedding richiede alcune decine di secondi (download di MiniLM + indicizzazione); ai riavvii successivi il manifest di idempotenza salta i documenti invariati, rendendo l'operazione quasi istantanea.

L'app è servita su `http://127.0.0.1:8000`; la root reindirizza al frontend. Dopo il login puoi chattare con **Coach** (schede) e **Nutrition** (pasti, chat, foto/barcode).

---

## 8. Troubleshooting

### 8.1 Conflitto Vision + Tool + Structured Output (Groq)

**Sintomo:** errori API o risposte vuote quando si tenta analisi immagine, chiamata tool e output JSON nella stessa run.

**Causa:** l'API Groq non supporta la coesistenza di vision, function calling e structured output in una singola chiamata.

**Soluzione (già implementata):** il flusso pasto è spezzato in fasi separate (Vision → Parser, vedi §3.4). Ogni agente fa una sola cosa per chiamata.

### 8.2 Barcode non letto dalla foto

**Sintomo:** un pasto con codice a barre viene stimato visivamente invece che letto da OpenFoodFacts.

**Causa:** immagine troppo sfocata/rumorosa per il decoder (zxing-cpp/OpenCV).

**Soluzione:** inserisci il codice a mano nel campo dedicato — ha priorità sullo scan automatico (se plausibile, 8-14 cifre, viene usato direttamente).

---

## 9. Suddivisione del Lavoro

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

## 10. Utilizzo di Strumenti AI

Durante lo sviluppo abbiamo usato strumenti AI come supporto — in particolare **Antigravity** e **Claude Code** — sempre sotto la nostra supervisione diretta e con validazione critica di ogni output. Ci hanno assistito in: sviluppo UI/UX, ottimizzazione dei system prompt degli agenti, integrazione frontend-backend, refactoring di funzioni complesse, scelte architetturali e stesura della documentazione.

---

**Realizzato da Stefano Bellan e Timothy Giolito.**

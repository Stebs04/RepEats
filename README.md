# RepEats

RepEats è un'applicazione web basata sull'intelligenza artificiale (Lumina) che funge da assistente personale per il fitness e la nutrizione. Il sistema permette di creare schede di allenamento giornaliere personalizzate, ricevere feedback nutrizionali smart e gestire il proprio profilo utente.

## Autori del Progetto

Questo è un progetto universitario realizzato da:
- **Bellan Stefano** (Matricola: 20054330)
- **Timothy Giolito** (Matricola: 20054431)

---

## ⚠️ Configurazione Indispensabile: Il file `.env`

**ATTENZIONE: La configurazione del file `.env` è un passaggio obbligatorio che deve essere verificato ogni volta prima di avviare il progetto.**

L'applicazione dipende fortemente da variabili d'ambiente (come ad esempio chiavi API per i servizi di intelligenza artificiale e configurazioni del database). Senza questo file, l'applicazione crasherà o non funzionerà correttamente.

**Istruzioni:**
1. Assicurati che nella root del progetto sia presente un file chiamato esattamente `.env`.
2. Se non esiste, crealo copiando il contenuto del file `.env.example`.
3. Compila il file `.env` con tutti i dati necessari (API keys, secret keys, ecc.).
4. **Non avviare mai il progetto senza prima esserti assicurato che il file `.env` sia presente e configurato correttamente.**

---

## LLM Hallucination Mitigation & Safety Net

Il Coach IA salva le schede di allenamento tramite **Tool Calling autonomo**:
decide da solo quando invocare `create_workout_plan_tool` /
`modify_workout_plan_tool`. Questa modalita' e' la scelta corretta per un flusso
ibrido (chat in linguaggio naturale + azioni sul DB), ma soffre di un limite
intrinseco degli LLM: l'**action hallucination**. L'agente puo' generare un
testo perfettamente plausibile — *"Ho salvato la tua scheda Push A"* — **senza
aver realmente emesso la tool call**. Il testo mente ed e' indistinguibile da un
successo reale.

Fidarsi della risposta in linguaggio naturale non e' un'opzione. L'unica fonte
di verita' e' lo **stato del database**. La rete di sicurezza (in
`backend/chat_api.py`) funziona cosi':

1. **Snapshot deterministico (`_workout_snapshot`)** — prima di ogni run del
   Coach fotografiamo lo stato delle schede (id, nomi, esercizi con
   set/reps/recupero) in una tupla immutabile e comparabile. A fine run
   rifotografiamo. `snapshot_dopo != snapshot_prima` e' **l'unico modo
   deterministico** per sapere se un tool ha davvero scritto sul DB — a
   prescindere da cosa afferma il testo.

2. **Rilevazione della discrepanza** — incrociamo due segnali: il testo
   *dichiara* un salvataggio (`claims_save`, semantico e inaffidabile) **e** il
   DB risulta *invariato* (`workouts_updated == False`, deterministico). Testo
   che promette + DB fermo = tool non chiamato.

3. **`recovery_prompt` auto-riparante** — in caso di discrepanza iniettiamo un
   messaggio di sistema **invisibile all'utente** che re-innesca l'agente
   forzandolo a ricavare scheda ed esercizi dal proprio testo e a chiamare
   *adesso* il tool corretto. La risposta gia' mostrata all'utente resta intatta;
   il salvataggio avviene dietro le quinte. Dopo il recovery ri-verifichiamo lo
   snapshot per riflettere l'esito reale.

> Perche' Tool Calling e non Structured Output nativo? Vedi
> [`docs/LLM_ARCHITECTURE.md`](docs/LLM_ARCHITECTURE.md).

---

## Struttura del Progetto

Il progetto è diviso principalmente in due sezioni:
- `backend/`: Contiene il server in Python, la gestione del database (SQLite), l'autenticazione degli utenti e la logica degli agenti IA (Fitness e Nutritionist).
- `frontend/`: Contiene l'interfaccia utente interattiva della web app.

## Avvio del Progetto

Dopo aver configurato correttamente il file `.env`:

Puoi utilizzare gli script di avvio rapido inclusi nella root del progetto:
- **Su Windows:** esegui il file `start.bat`
- **Su macOS/Linux:** esegui il file `start.sh` (potrebbe essere necessario dare i permessi di esecuzione con `chmod +x start.sh`)

---

## Gestione Database (Alembic)

Lo schema del database **non** viene piu' creato automaticamente all'avvio
(niente `Base.metadata.create_all()`). L'evoluzione dello schema e' gestita da
[Alembic](https://alembic.sqlalchemy.org/) tramite migrazioni versionate nella
cartella `alembic/versions/`. All'avvio l'app verifica soltanto che il database
sia raggiungibile.

Alembic legge la variabile `DATABASE_URL` dal file `.env` (configurata in
`alembic/env.py`): assicurati che sia valorizzata prima di eseguire i comandi.

### Primo setup

Su un database **nuovo/vuoto**, crea le tabelle applicando le migrazioni:

```bash
alembic upgrade head
```

Se hai gia' un database preesistente con le tabelle create dalla vecchia logica
`create_all()`, allineane lo stato senza rieseguire le CREATE con:

```bash
alembic stamp head
```

### Flusso di lavoro quotidiano

1. Modifica i modelli ORM in `src/database/models.py`.
2. Genera la migrazione confrontando modelli e schema attuale:

   ```bash
   alembic revision --autogenerate -m "messaggio descrittivo"
   ```

3. Controlla il file generato in `alembic/versions/` (autogenerate non e'
   infallibile: verifica upgrade/downgrade).
4. Applica la migrazione:

   ```bash
   alembic upgrade head
   ```

Comandi utili: `alembic current` (revisione applicata), `alembic history`
(elenco migrazioni), `alembic downgrade -1` (annulla l'ultima migrazione).

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

## Struttura del Progetto

Il progetto è diviso principalmente in due sezioni:
- `backend/`: Contiene il server in Python, la gestione del database (SQLite), l'autenticazione degli utenti e la logica degli agenti IA (Fitness e Nutritionist).
- `frontend/`: Contiene l'interfaccia utente interattiva della web app.

## Avvio del Progetto

Dopo aver configurato correttamente il file `.env`:

Puoi utilizzare gli script di avvio rapido inclusi nella root del progetto:
- **Su Windows:** esegui il file `start.bat`
- **Su macOS/Linux:** esegui il file `start.sh` (potrebbe essere necessario dare i permessi di esecuzione con `chmod +x start.sh`)

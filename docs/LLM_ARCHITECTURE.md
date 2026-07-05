# Architettura LLM: Tool Calling vs Native Structured Output

Documento di approfondimento sulla scelta architetturale alla base della
generazione delle schede di allenamento del Coach IA in RepEats.

## Decisione

**Manteniamo il Tool Calling autonomo. Scartiamo il Native Structured Output.**

Nessuna migrazione verso lo Structured Output nativo e' prevista o desiderabile.

## Il tradeoff

### Native Structured Output — perche' l'abbiamo scartato

Lo Structured Output nativo forza **l'intera risposta** dell'LLM a rispettare
uno schema JSON rigido. Ogni token prodotto dal modello deve conformarsi allo
schema. Questo garantisce output strutturato perfetto per la scheda, ma **al
prezzo della natura conversazionale dell'agente**: un Coach vincolato a emettere
solo JSON non puo' piu' dialogare fluidamente in linguaggio naturale, fare
domande di chiarimento, spiegare le proprie scelte o chattare con l'utente.

Nel nostro flusso l'agente deve poter **conversare liberamente** e, *solo quando
necessario*, compiere un'azione sul database. Sono due modalita' diverse nella
stessa interazione. Lo Structured Output collassa tutto sul secondo caso,
distruggendo il primo. Per un assistente conversazionale e' un tradeoff
inaccettabile.

### Tool Calling — perche' e' la scelta corretta

Il Tool Calling e' la modalita' nativa per i **flussi ibridi (chat + azioni)**:
l'agente resta un interlocutore in linguaggio naturale e, quando il contesto lo
richiede, emette *autonomamente* una chiamata a un tool
(`create_workout_plan_tool`, `modify_workout_plan_tool`) con argomenti
strutturati. Conversazione fluida **e** azione strutturata coesistono, ciascuna
quando serve.

### Il limite del Tool Calling — e come lo arginiamo

Il Tool Calling introduce pero' un limite intrinseco: l'**action
hallucination**. Poiche' la decisione di chiamare il tool e' lasciata al
modello, l'agente puo' generare un testo che *afferma* di aver compiuto
l'azione senza averla realmente eseguita ("Ho salvato la tua scheda") — senza
alcuna tool call emessa.

Qui interviene la nostra **rete di sicurezza deterministica**
(`backend/chat_api.py`):

- **`_workout_snapshot`** fotografa lo stato del DB prima e dopo la run. Il
  confronto delle due fotografie e' l'unico segnale deterministico che dica se
  un tool ha davvero scritto — indipendentemente dal testo generato.
- **`recovery_prompt`** e' il fallback auto-riparante: quando il testo dichiara
  un salvataggio ma il DB e' invariato, un messaggio di sistema invisibile
  all'utente re-innesca l'agente e lo forza a emettere *ora* la tool call
  mancante.

## Il risultato: il meglio di entrambi gli approcci

La rete di sicurezza unisce i vantaggi dei due paradigmi **senza sacrificarne
nessuno**:

| | Fluidita' conversazionale | Garanzia che l'azione avvenga |
|---|---|---|
| Structured Output nativo | ❌ distrutta | ✅ garantita dallo schema |
| Tool Calling "nudo" | ✅ preservata | ❌ soggetta ad action hallucination |
| **Tool Calling + snapshot/recovery (RepEats)** | ✅ preservata | ✅ garantita dal confronto di stato del DB |

Otteniamo la liberta' conversazionale del Tool Calling e una garanzia di
esecuzione equivalente a quella dello Structured Output — ma verificata sullo
stato reale del database anziche' imposta sul formato della risposta.

Dettaglio implementativo della rete di sicurezza: vedi la sezione
*"LLM Hallucination Mitigation & Safety Net"* nel
[`README.md`](../README.md) e i commenti in `backend/chat_api.py`.

"""
Suite di valutazione quantitativa (LLM-as-a-Judge) per gli agenti di RepEats.

Lo script:
  1. Carica `eval_dataset.json` (conversazioni di test per Coach e Nutrizionista).
  2. Genera le risposte facendole passare per gli AGENTI REALI, tramite
     l'orchestratore (`src.orchestrator.get_orchestrator`). Nessuna logica
     duplicata: si valuta ciò che l'utente riceve davvero in produzione.
  3. Valuta ogni risposta con un giudice LLM rigoroso (`evaluate_response`):
       - Coach        -> la scheda rispetta il vincolo di tempo imposto?
       - Nutrizionista -> i macronutrienti citati sono matematicamente
                          corretti e privi di allucinazioni?
  4. Stampa un report finale in console con il Pass Rate % per categoria.

Uso:
    python evals.py            # esegue tutto il dataset
    python evals.py --limit 4  # esegue solo i primi 4 casi (smoke test)

Requisiti: GROQ_API_KEY impostata (in .env o ambiente).

Autore: generato per la suite di Evals di RepEats.
"""

import os
import sys
import json
import argparse

from dotenv import load_dotenv
from groq import Groq as GroqClient
from tabulate import tabulate

from src.orchestrator import get_orchestrator

# Carica GROQ_API_KEY e le altre variabili dal file .env
load_dotenv()

# Percorsi
ROOT = os.path.dirname(os.path.abspath(__file__))
DATASET_PATH = os.path.join(ROOT, "eval_dataset.json")

# Modello usato dal giudice. Lo stesso già in uso dagli agenti del progetto:
# è garantito valido sull'account Groq configurato.
JUDGE_MODEL = os.getenv("JUDGE_MODEL", "meta-llama/llama-4-scout-17b-16e-instruct")

# Valori di default per il contesto utente richiesto dall'orchestratore.
# Le singole conversazioni possono sovrascrivere `user_data` (es. workout_duration).
DEFAULT_USER_DATA = {
    "user_id": 0,
    "age": 30,
    "weight": 75,
    "goal_type": "Ipertrofia",
    "workout_duration": 60,
    "workout_preference": "Ipertrofia",
}
DEFAULT_MACROS = {"calories": 1500, "proteins": 90, "carbohydrates": 150, "fats": 50}
DEFAULT_TARGETS = {"target_calories": 2200}

_judge_client = GroqClient(api_key=os.getenv("GROQ_API_KEY"))


# --------------------------------------------------------------------------- #
# Generazione risposte tramite gli agenti reali
# --------------------------------------------------------------------------- #
def generate_response(entry: dict) -> str:
    """
    Genera la risposta dell'agente reale per una conversazione del dataset,
    passando per l'orchestratore (routing + agente specializzato).

    Args:
        entry: Un elemento del dataset (con `agent` e `message`).

    Returns:
        Il testo della risposta prodotta dall'agente.
    """
    user_data = {**DEFAULT_USER_DATA, **entry.get("user_data", {})}
    macros = {**DEFAULT_MACROS, **entry.get("macros", {})}
    targets = {**DEFAULT_TARGETS, **entry.get("daily_targets", {})}
    chat_type = entry["agent"]  # "coach" | "nutritionist"

    team = get_orchestrator(
        user_data=user_data,
        macros=macros,
        daily_targets=targets,
        chat_history=[],
        chat_type=chat_type,
        # In valutazione vogliamo la sola risposta testuale: niente tool di
        # persistenza. Evita scritture reali sul DB e i crash "tool_use_failed"
        # dovuti a tool call malformate del modello.
        enable_tools=False,
    )
    # stream=False forza il ritorno di un RunOutput (con `.content`) invece
    # dell'iteratore di eventi: il Team e' costruito con stream=True per la chat
    # live, ma in valutazione serve la sola risposta testuale completa.
    result = team.run(entry["message"], stream=False)
    # Agno restituisce un RunOutput con l'attributo `.content`
    return getattr(result, "content", str(result)) or ""


# --------------------------------------------------------------------------- #
# LLM-as-a-Judge
# --------------------------------------------------------------------------- #
FITNESS_JUDGE_PROMPT = """Sei un valutatore ESTREMAMENTE RIGOROSO di schede di allenamento.

VINCOLO DA VERIFICARE: l'allenamento proposto deve stare interamente in {max_minutes} minuti,
comprensivi di riscaldamento, parte centrale e defaticamento/stretching.

Analizza la risposta del Personal Trainer qui sotto. Stima la durata TOTALE realistica
sommando: numero di esercizi, serie, ripetizioni e tempi di recupero indicati.

Regola di superamento (rigida):
- pass = true SOLO se la durata totale stimata <= {max_minutes} minuti (tolleranza massima +10%).
- pass = false se la scheda eccede il tempo, oppure se è vaga al punto da non poter rispettare il vincolo.

Rispondi ESCLUSIVAMENTE con un oggetto JSON valido, senza testo attorno:
{{"pass": true/false, "estimated_minutes": <numero>, "reason": "<motivazione breve in italiano>"}}

--- RISPOSTA DEL PERSONAL TRAINER ---
{response}
--- FINE RISPOSTA ---"""

NUTRITION_JUDGE_PROMPT = """Sei un valutatore RIGOROSO ma EQUO di dati nutrizionali.

Devi verificare DUE condizioni sulla risposta della Nutrizionista:

1) COERENZA MATEMATICA: per gli alimenti citati, le calorie dichiarate devono rispettare
   la formula   kcal ≈ 4*proteine(g) + 4*carboidrati(g) + 9*grassi(g)
   con tolleranza ±20% (le tabelle nutrizionali reali si discostano dalla somma di Atwater
   per via di fibra e arrotondamenti: NON penalizzare scostamenti entro il 20%).

2) ASSENZA DI ALLUCINAZIONI: i valori di calorie e macro devono essere PLAUSIBILI per
   l'alimento e la grammatura indicati dall'utente (nessun valore assurdo o inventato).

Richiesta originale dell'utente:
"{message}"

ISTRUZIONI DI CALCOLO (seguile alla lettera):
- Se un valore è espresso come intervallo (es. "30-35g" o "160-170 kcal"), USA IL PUNTO
  MEDIO (32.5g, 165 kcal). Un intervallo ragionevole NON è motivo di bocciatura.
- Calcola kcal_computed TU STESSO e scrivi SOLO IL NUMERO FINALE già risolto
  (esempio corretto: 150.75). È VIETATO scrivere espressioni aritmetiche come
  "4*3.5 + 4*32.5 + 9*0.75" dentro il JSON: il JSON diventerebbe invalido.
- Confronta kcal_stated (punto medio) con kcal_computed: se lo scarto è entro ±20%, la
  condizione 1 è soddisfatta.

Regola di superamento:
- pass = true se ENTRAMBE le condizioni sono rispettate.
- pass = false solo se i numeri sono incoerenti oltre il 20%, implausibili/inventati,
  oppure del tutto assenti quando erano chiaramente richiesti.

Rispondi ESCLUSIVAMENTE con un oggetto JSON valido, con SOLI valori numerici o null
nei campi numerici (mai formule), senza testo attorno:
{{"pass": true/false, "kcal_stated": <numero o null>, "kcal_computed": <numero o null>, "reason": "<motivazione breve in italiano>"}}

--- RISPOSTA DELLA NUTRIZIONISTA ---
{response}
--- FINE RISPOSTA ---"""


def evaluate_response(entry: dict, response: str) -> dict:
    """
    Valuta rigidamente una risposta tramite un giudice LLM (LLM-as-a-Judge).

    A seconda della metrica dell'entry applica il criterio corretto:
      - "time_constraint": la scheda rispetta il tetto di minuti imposto.
      - "macro_accuracy": i macronutrienti sono corretti e senza allucinazioni.

    Args:
        entry: La conversazione del dataset (contiene `metric` e i parametri).
        response: Il testo generato dall'agente da valutare.

    Returns:
        Dizionario con almeno la chiave booleana "pass" e "reason".
    """
    metric = entry["metric"]
    if metric == "time_constraint":
        prompt = FITNESS_JUDGE_PROMPT.format(
            max_minutes=entry["max_minutes"], response=response
        )
    elif metric == "macro_accuracy":
        prompt = NUTRITION_JUDGE_PROMPT.format(
            message=entry["message"], response=response
        )
    else:
        return {"pass": False, "reason": f"Metrica sconosciuta: {metric}"}

    # Fino a 2 tentativi: il modello giudice può occasionalmente restituire JSON
    # invalido (es. formule non risolte). Un singolo errore transitorio non deve
    # contare come bocciatura della risposta valutata.
    last_error = None
    for _ in range(2):
        try:
            completion = _judge_client.chat.completions.create(
                model=JUDGE_MODEL,
                messages=[
                    {
                        "role": "system",
                        "content": "Sei un giudice imparziale. Rispondi solo con JSON valido, "
                                   "usando esclusivamente numeri risolti nei campi numerici (mai formule).",
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=0,
                response_format={"type": "json_object"},
            )
            verdict = json.loads(completion.choices[0].message.content)
            break
        except Exception as e:  # rete, rate-limit, JSON malformato
            last_error = e
    else:
        return {"pass": False, "reason": f"Errore giudice: {last_error}"}

    # Normalizza il booleano (il modello potrebbe restituire "true"/"false" stringa)
    verdict["pass"] = str(verdict.get("pass")).strip().lower() == "true"
    return verdict


# --------------------------------------------------------------------------- #
# Runner + report
# --------------------------------------------------------------------------- #
def run_evals(limit: int | None = None) -> None:
    with open(DATASET_PATH, encoding="utf-8") as f:
        dataset = json.load(f)

    conversations = dataset["conversations"]
    if limit:
        conversations = conversations[:limit]

    rows = []
    # Conteggi per categoria: (passati, totali)
    stats = {"coach": [0, 0], "nutritionist": [0, 0]}

    for i, entry in enumerate(conversations, start=1):
        agent = entry["agent"]
        print(f"[{i}/{len(conversations)}] {entry['id']} ({agent}) ... ", end="", flush=True)

        try:
            response = generate_response(entry)
            verdict = evaluate_response(entry, response)
        except Exception as e:
            response = ""
            verdict = {"pass": False, "reason": f"Errore generazione: {e}"}

        passed = bool(verdict.get("pass"))
        stats[agent][1] += 1
        if passed:
            stats[agent][0] += 1

        print("PASS" if passed else "FAIL")

        rows.append([
            entry["id"],
            "Coach" if agent == "coach" else "Nutriz.",
            "✅ PASS" if passed else "❌ FAIL",
            (verdict.get("reason", "") or "")[:70],
        ])

    # ---- Report tabellare ----
    print("\n" + "=" * 80)
    print("DETTAGLIO VALUTAZIONI")
    print("=" * 80)
    print(tabulate(rows, headers=["ID", "Agente", "Esito", "Motivazione (giudice)"],
                   tablefmt="github"))

    # ---- Pass Rate ----
    print("\n" + "=" * 80)
    print("REPORT FINALE — PASS RATE")
    print("=" * 80)

    summary = []
    total_pass, total_all = 0, 0
    labels = {
        "coach": "Fitness Coach (vincolo tempo)",
        "nutritionist": "Nutrizionista (macro corretti)",
    }
    for agent, (p, t) in stats.items():
        total_pass += p
        total_all += t
        rate = (p / t * 100) if t else 0.0
        summary.append([labels[agent], f"{p}/{t}", f"{rate:.1f}%"])

    overall = (total_pass / total_all * 100) if total_all else 0.0
    summary.append(["— TOTALE —", f"{total_pass}/{total_all}", f"{overall:.1f}%"])

    print(tabulate(summary, headers=["Categoria", "Passati", "Pass Rate"],
                   tablefmt="github"))
    print()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Evals LLM-as-a-Judge per RepEats.")
    parser.add_argument("--limit", type=int, default=None,
                        help="Valuta solo i primi N casi (smoke test).")
    args = parser.parse_args()

    if not os.getenv("GROQ_API_KEY"):
        print("ERRORE: GROQ_API_KEY non impostata (in .env o ambiente).")
        sys.exit(1)

    run_evals(limit=args.limit)

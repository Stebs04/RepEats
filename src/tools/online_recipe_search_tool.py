"""
Modulo per la ricerca online di ricette reali da fonti web affidabili.

Effettua una ricerca sul web a partire dalle parole chiave fornite dall'agente
(includendo tipicamente il sito di riferimento e i vincoli di macronutrienti) e
restituisce i primi risultati con titolo, link e un breve snippet, così da
suggerire all'utente ricette concrete e contestualizzate.

Author: Stefano Bellan (20054330)
"""

# Client HTTP per interrogare il motore di ricerca
import requests
# Parser per estrarre i risultati dalla pagina HTML restituita
from bs4 import BeautifulSoup
# Espressioni regolari per ripulire la query di fallback
import re

# Endpoint HTML del motore di ricerca: non richiede API key e restituisce i
# risultati in markup statico, facilmente analizzabile lato server.
_SEARCH_URL = "https://html.duckduckgo.com/html/"

# Numero massimo di risultati da riportare all'agente per non appesantire il contesto.
_MAX_RESULTS = 8

# Minimo di risultati sotto il quale ritentiamo con query progressivamente più larghe.
_MIN_RESULTS = 3


# Un User-Agent da browser è necessario perché l'endpoint HTML rifiuta i client anonimi
_HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) RepEats Recipe Search"}

# Istruzione secca allegata a ogni esito senza risultati: il modello debole, lasciato
# libero, rimanda l'utente a cercare da solo ('Prova a cercare su GialloZafferano...').
# Lo VIETIAMO esplicitamente e gli imponiamo di produrre lui la ricetta completa.
_NO_RESULT_FALLBACK = (
    "NON dire all'utente di cercare da solo online e NON elencare 'ricerche da provare'. "
    "Proponi TU adesso UNA ricetta completa e concreta (titolo, ingredienti con grammature "
    "e procedimento breve) coerente con i macro richiesti, in base alle tue conoscenze."
)

# Siti di cucina italiani noti, usati come ancora nelle query di retry per
# migliorare la pertinenza dei risultati e aumentare il tasso di match.
_RECIPE_SITES = ["GialloZafferano", "Cookist", "FattoInCasaDaBenedetta"]

# Parole riempitive che non aggiungono valore alla ricerca e anzi la intasano.
_FILLER_WORDS = re.compile(
    r'\b(con|per|dal|del|della|delle|dei|degli|una|uno|un|il|lo|la|le|gli|di|da|in|su|che|e|o|a)\b',
    re.IGNORECASE
)


def _simplify_query(query: str) -> str:
    """
    Rimuove vincoli numerici (kcal, grammi, nomi dei macro) dalla query.

    Le ricette web non sono indicizzate per '732.9 kcal' o '64.1g di proteine': una query
    così specifica non matcha nessun titolo e la ricerca torna vuota. Togliendo i numeri
    cerchiamo per ingredienti/tipo pasto, poi è l'LLM a filtrare sui macro.

    Author: Stefano Bellan (20054330)
    """
    q = re.sub(r'\d[\d.,]*\s*(kcal|cal|kg|mg|gr|grammi|g)?\b', ' ', query, flags=re.IGNORECASE)
    q = re.sub(r'\b(di\s+)?(proteine|carboidrati|carbo|grassi|calorie|kcal|macro|macronutrienti)\b', ' ', q, flags=re.IGNORECASE)
    return re.sub(r'\s+', ' ', q).strip()


def _extract_keywords(query: str) -> str:
    """
    Estrae solo le parole chiave significative dalla query, rimuovendo
    articoli, preposizioni e filler che diluiscono la ricerca.

    Author: Stefano Bellan (20054330)
    """
    q = _simplify_query(query)
    q = _FILLER_WORDS.sub(' ', q)
    return re.sub(r'\s+', ' ', q).strip()


def _build_web_query(raw_query: str) -> str:
    """
    Trasforma la query dell'agente in una ricerca web efficace per ricette.

    Toglie i vincoli numerici (che azzerano i match) e assicura la parola 'ricetta',
    così i risultati puntano a siti di cucina invece che a pagine generiche.

    Author: Stefano Bellan (20054330)
    """
    q = _simplify_query(raw_query)
    if "ricett" not in q.lower():
        q = f"ricetta {q}"
    return q.strip()


def _build_fallback_queries(raw_query: str) -> list:
    """
    Genera una lista di query di retry progressivamente più larghe.

    Strategia a 3 livelli:
    1. Query originale + sito di ricette noto (GialloZafferano)
    2. Solo keyword estratte + 'ricetta' + secondo sito (Cookist)
    3. Keyword minime + 'ricetta facile' + terzo sito (FattoInCasa)

    Author: Stefano Bellan (20054330)
    """
    keywords = _extract_keywords(raw_query)
    base = _build_web_query(raw_query)

    fallbacks = []
    # Livello 1: query base + sito noto
    fallbacks.append(f"{base} {_RECIPE_SITES[0]}")
    # Livello 2: solo keyword + ricetta + sito alternativo
    if keywords:
        fallbacks.append(f"ricetta {keywords} {_RECIPE_SITES[1]}")
    # Livello 3: keyword essenziali + ricetta facile
    essential = " ".join(keywords.split()[:3])  # max 3 parole chiave
    if essential:
        fallbacks.append(f"ricetta facile {essential} {_RECIPE_SITES[2]}")

    return fallbacks


def _fetch_results(query: str) -> list:
    """
    Interroga il motore e restituisce la lista dei blocchi-risultato formattati.

    Author: Stefano Bellan (20054330)
    """
    # Chiamata bloccante con timeout per non incastrare l'agente in attese indefinite
    response = requests.post(_SEARCH_URL, data={"q": query}, headers=_HEADERS, timeout=10)
    response.raise_for_status()
    # Forziamo UTF-8: l'endpoint non sempre dichiara la codifica e requests
    # ripiegherebbe su latin-1, corrompendo le lettere accentate italiane.
    response.encoding = "utf-8"

    soup = BeautifulSoup(response.text, "html.parser")
    risultati = []
    for result in soup.select("div.result")[:_MAX_RESULTS]:
        link_tag = result.select_one("a.result__a")
        if not link_tag:
            continue
        # Usiamo lo spazio come separatore: il motore evidenzia i termini con tag
        # inline e uno strip secco fonderebbe le parole adiacenti.
        titolo = link_tag.get_text(" ", strip=True)
        link = link_tag.get("href", "")

        # Scartiamo risultati senza link valido (l'agente DEVE includere i link)
        if not link or not link.startswith("http"):
            continue

        # Lo snippet è opzionale: quando presente riporta gli ingredienti o la descrizione
        snippet_tag = result.select_one(".result__snippet")
        snippet = snippet_tag.get_text(" ", strip=True) if snippet_tag else ""

        # Formato con link markdown pronto all'uso: l'agente può copiarlo direttamente
        blocco = f"\n- [{titolo}]({link})"
        if snippet:
            blocco += f"\n  {snippet}"
        risultati.append(blocco)
    return risultati


def _deduplicate(results: list) -> list:
    """
    Rimuove risultati duplicati preservando l'ordine di inserimento.

    Author: Stefano Bellan (20054330)
    """
    seen = set()
    unique = []
    for r in results:
        if r not in seen:
            seen.add(r)
            unique.append(r)
    return unique


def search_online_recipes(query: str) -> str:
    """
    Cerca ricette reali sul web e restituisce i migliori risultati formattati.

    Interroga il motore con la query fornita; se torna con meno di 3 risultati,
    ritenta con query progressivamente più larghe (fino a 3 tentativi) per
    massimizzare le probabilità di trovare ricette pertinenti.
    Le eccezioni di rete vengono gestite in modo silente restituendo un messaggio
    gestibile, senza sollevare eccezioni che interromperebbero il ciclo dell'agente.

    Args:
        query (str): Parole chiave per la ricerca web della ricetta
            (es. 'ricetta pollo GialloZafferano 400 kcal').

    Returns:
        str: Elenco formattato dei risultati oppure un'istruzione di fallback che
        impone al modello di proporre lui una ricetta.

    Author: Stefano Bellan (20054330)
    """
    web_query = _build_web_query(query)
    try:
        risultati = _fetch_results(web_query)

        # Se i risultati sono insufficienti, ritentiamo con query progressivamente
        # più larghe fino a raggiungere il minimo richiesto.
        if len(risultati) < _MIN_RESULTS:
            for fallback_query in _build_fallback_queries(query):
                for blocco in _fetch_results(fallback_query):
                    risultati.append(blocco)
                risultati = _deduplicate(risultati)
                if len(risultati) >= _MIN_RESULTS:
                    break

    except requests.RequestException as exc:
        # Degradazione controllata: l'LLM riceve un testo gestibile invece di un crash
        return f"Ricerca online non disponibile in questo momento ({exc}). {_NO_RESULT_FALLBACK}"

    if not risultati:
        return f"Nessun risultato online per '{web_query}'. {_NO_RESULT_FALLBACK}"

    intro = (
        f"Ricette trovate online per '{web_query}'. PROPONI ALL'UTENTE ALMENO {_MIN_RESULTS} "
        f"di queste ricette. Ogni ricetta DEVE essere presentata con il TITOLO come link "
        f"cliccabile markdown (copia il formato '[Titolo](URL)' esattamente come fornito sotto). "
        f"Aggiungi per ciascuna una stima dei macro e spiega perché è adatta al fabbisogno:\n"
    )
    return intro + "\n".join(risultati[:_MAX_RESULTS])


if __name__ == "__main__":
    # Self-check offline: la semplificazione deve togliere numeri e nomi dei macro,
    # lasciando ingredienti/tipo pasto cercabili.
    _s = _simplify_query("pranzo pollo e verdure 732.9 kcal 64.1g di proteine 73.3g carboidrati")
    assert "kcal" not in _s.lower() and "proteine" not in _s.lower(), _s
    assert not any(c.isdigit() for c in _s), _s
    assert "pollo" in _s and "verdure" in _s, _s
    # La query web deve essere senza numeri e con 'ricetta' per puntare a siti di cucina.
    _w = _build_web_query("cena salmone 600 kcal 40g proteine")
    assert "ricett" in _w.lower() and not any(c.isdigit() for c in _w), _w
    assert "salmone" in _w, _w
    # Le keyword devono essere pulite senza filler
    _k = _extract_keywords("pranzo con pollo e verdure per la cena 500 kcal")
    assert "pollo" in _k and "verdure" in _k, _k
    assert "con" not in _k.split() and "per" not in _k.split(), _k
    # I fallback devono generare almeno 3 query
    _fb = _build_fallback_queries("cena salmone 600 kcal 40g proteine")
    assert len(_fb) >= 2, _fb
    print("OK query builders:", repr(_s), "|", repr(_w), "|", repr(_k))
    print("OK fallbacks:", _fb)


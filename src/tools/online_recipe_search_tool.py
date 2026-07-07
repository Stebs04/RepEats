"""
Modulo per la ricerca online di ricette reali da fonti web affidabili.

Effettua una ricerca sul web a partire dalle parole chiave fornite dall'agente
(includendo tipicamente il sito di riferimento e i vincoli di macronutrienti) e
restituisce i primi risultati con titolo, link e un breve snippet, così da
suggerire all'utente ricette concrete e contestualizzate.

Author: Stefano Bellan (20054330)
"""

# Strutture dati per la modellazione e validazione dei contratti I/O
from pydantic import BaseModel, Field
# Client HTTP per interrogare il motore di ricerca
import requests
# Parser per estrarre i risultati dalla pagina HTML restituita
from bs4 import BeautifulSoup

# Endpoint HTML del motore di ricerca: non richiede API key e restituisce i
# risultati in markup statico, facilmente analizzabile lato server.
_SEARCH_URL = "https://html.duckduckgo.com/html/"

# Numero massimo di risultati da riportare all'agente per non appesantire il contesto.
_MAX_RESULTS = 5


class OnlineRecipeSearchInput(BaseModel):
    """
    Schema per validare l'input della ricerca web di ricette.

    Author: Stefano Bellan (20054330)
    """
    # Parole chiave complete della ricerca (sito, tipo pasto, vincoli di macro)
    query: str = Field(..., description="Parole chiave per la ricerca web della ricetta (es. 'ricetta pollo GialloZafferano 400 kcal').")


def search_online_recipes(input_data: OnlineRecipeSearchInput) -> str:
    """
    Cerca ricette reali sul web e restituisce i migliori risultati formattati.

    Interroga il motore di ricerca con la query fornita, estrae i primi risultati
    (titolo, link ed eventuale snippet descrittivo) e li impagina come testo
    leggibile dall'LLM. Le eccezioni di rete vengono gestite in modo silente
    restituendo un messaggio di errore comprensibile, senza sollevare eccezioni
    che interromperebbero il ciclo dell'agente.

    Args:
        input_data (OnlineRecipeSearchInput): Oggetto contenente la query validata.

    Returns:
        str: Elenco formattato dei risultati oppure un messaggio esplicativo in
        caso di assenza di risultati o errore di rete.

    Author: Stefano Bellan (20054330)
    """
    # Un User-Agent da browser è necessario perché l'endpoint HTML rifiuta i client anonimi
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) RepEats Recipe Search"}

    try:
        # Chiamata bloccante con timeout per non incastrare l'agente in attese indefinite
        response = requests.post(_SEARCH_URL, data={"q": input_data.query}, headers=headers, timeout=10)
        response.raise_for_status()
    except requests.RequestException as exc:
        # Degradazione controllata: l'LLM riceve un testo gestibile invece di un crash
        return f"Impossibile completare la ricerca online delle ricette in questo momento ({exc}). Suggerisci una ricetta in base alle tue conoscenze."

    # Forziamo UTF-8: l'endpoint non sempre dichiara la codifica e requests
    # ripiegherebbe su latin-1, corrompendo le lettere accentate italiane.
    response.encoding = "utf-8"

    # Analisi del markup per isolare i nodi dei singoli risultati
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

        # Lo snippet è opzionale: quando presente riporta gli ingredienti o la descrizione
        snippet_tag = result.select_one(".result__snippet")
        snippet = snippet_tag.get_text(" ", strip=True) if snippet_tag else ""

        blocco = f"\n- {titolo}\n  Fonte: {link}"
        if snippet:
            blocco += f"\n  {snippet}"
        risultati.append(blocco)

    if not risultati:
        return f"Nessun risultato trovato online per '{input_data.query}'. Prova a riformulare o suggerisci una ricetta in base alle tue conoscenze."

    return f"Ricette trovate online per '{input_data.query}':\n" + "\n".join(risultati)

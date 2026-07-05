"""
Builder centralizzato delle Knowledge Base RAG di RepEats.

Questo modulo è l'UNICA sorgente di verità per la costruzione degli oggetti
`Knowledge` di Agno. Centralizza:
- la configurazione del vector store LanceDB (con Hybrid Search nativa),
- l'embedder SentenceTransformer,
- il reranker opzionale (attivabile via env),
- una cache a singleton (per dominio) per evitare di ricaricare il modello di
  embedding ad ogni richiesta.

SEPARAZIONE PER DOMINIO: esiste una Knowledge Base (= una tabella LanceDB)
distinta per ogni dominio applicativo. Così il Coach interroga solo i documenti
di fitness e il Nutritionist solo quelli di nutrizione, senza contaminazioni.

La logica di INGESTION dei documenti vive in `src/knowledge_base/ingest.py`:
qui ci occupiamo solo di *come* le KB sono configurate e interrogate.

Autore: Stefano Bellan (20054330)
"""

import os

from agno.knowledge.knowledge import Knowledge
from agno.vectordb.lancedb import LanceDb
from agno.vectordb.search import SearchType
from agno.knowledge.embedder.sentence_transformer import SentenceTransformerEmbedder

# ---------------------------------------------------------------------------
# Domini e mappatura verso le tabelle LanceDB
# ---------------------------------------------------------------------------

# Ogni dominio ha la sua tabella. "protocolli_allenamento" è mantenuto invariato
# per riusare l'indice fitness già vettorializzato (retrocompatibilità).
DOMAIN_TABLES = {
    "fitness": "protocolli_allenamento",
    "nutrition": "conoscenza_nutrizione",
}
DEFAULT_DOMAIN = "fitness"

# ---------------------------------------------------------------------------
# Costanti di configurazione (override possibile via variabili d'ambiente)
# ---------------------------------------------------------------------------

# Modello di embedding: MiniLM leggero, 384 dimensioni. NON cambiarlo senza
# rigenerare gli indici (cartella lancedb_vectors), perché cambierebbe la
# dimensione dei vettori.
EMBEDDER_ID = "sentence-transformers/all-MiniLM-L6-v2"

# Reranker leggero (cross-encoder ~80MB). Il default di Agno
# (BAAI/bge-reranker-v2-m3) è molto più pesante: preferiamo un modello piccolo.
RERANKER_MODEL = os.getenv("RAG_RERANKER_MODEL", "cross-encoder/ms-marco-MiniLM-L-6-v2")

# Numero di documenti tenuti dopo il reranking.
RERANKER_TOP_N = int(os.getenv("RAG_RERANK_TOP_N", "5"))


def _db_dir() -> str:
    """Percorso assoluto della cartella del vector store LanceDB."""
    base_dir = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_dir, "lancedb_vectors")


def vector_store_dir() -> str:
    """Percorso pubblico della cartella del vector store (usato dalla pipeline)."""
    return _db_dir()


def _build_reranker():
    """
    Istanzia il reranker SOLO se abilitato via env `RAG_RERANK=1`.
    Ritorna None quando disabilitato, così le KB restano leggere per default.
    """
    if os.getenv("RAG_RERANK", "0") != "1":
        return None
    # Import locale: evita di caricare il cross-encoder quando il reranking è off.
    from agno.knowledge.reranker.sentence_transformer import SentenceTransformerReranker
    return SentenceTransformerReranker(model=RERANKER_MODEL, top_n=RERANKER_TOP_N)


def _new_knowledge(domain: str) -> Knowledge:
    """
    Costruisce una nuova istanza di Knowledge per il dominio indicato,
    configurata con Hybrid Search.

    LanceDB combina ricerca vettoriale (semantica) e ricerca lessicale FTS/BM25:
    l'indice full-text sulla colonna `payload` viene creato automaticamente da
    Agno alla prima query hybrid. Nessuna dipendenza esterna richiesta.
    """
    table_name = DOMAIN_TABLES[domain]
    db_dir = _db_dir()
    os.makedirs(db_dir, exist_ok=True)

    return Knowledge(
        vector_db=LanceDb(
            table_name=table_name,
            uri=db_dir,
            embedder=SentenceTransformerEmbedder(id=EMBEDDER_ID),
            search_type=SearchType.hybrid,
            reranker=_build_reranker(),
        )
    )


# ---------------------------------------------------------------------------
# Cache a singleton, una istanza per dominio
# ---------------------------------------------------------------------------
_KNOWLEDGE_CACHE: dict[str, Knowledge] = {}


def build_knowledge(domain: str = DEFAULT_DOMAIN, force_new: bool = False) -> Knowledge:
    """
    Restituisce l'istanza condivisa della Knowledge Base per un dominio.

    L'oggetto (e con esso il modello di embedding) viene creato una sola volta
    per dominio e riutilizzato tra le richieste, evitando di ricaricare MiniLM
    ad ogni messaggio della chat.

    Args:
        domain: "fitness" (Coach) o "nutrition" (Nutritionist).
        force_new: Se True forza la ricostruzione (utile per lo script di
                   ingestion che vuole un'istanza isolata).

    Returns:
        Knowledge: la KB del dominio (Hybrid Search + reranker opzionale).
    """
    if domain not in DOMAIN_TABLES:
        raise ValueError(f"Dominio KB sconosciuto: '{domain}'. Ammessi: {list(DOMAIN_TABLES)}")

    if force_new:
        return _new_knowledge(domain)
    if domain not in _KNOWLEDGE_CACHE:
        _KNOWLEDGE_CACHE[domain] = _new_knowledge(domain)
    return _KNOWLEDGE_CACHE[domain]

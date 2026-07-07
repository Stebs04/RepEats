"""
Gestore centralizzato per l'istanziamento delle Knowledge Base RAG.

Questo modulo rappresenta il punto di accesso unico per la configurazione
degli oggetti Knowledge, definendo in un solo posto il vector store LanceDB,
il modello di embedding, le logiche di reranking e il caching in memoria.

La separazione rigorosa per dominio assicura che gli agenti non incrocino
i contesti (es. l'agente fitness consulta esclusivamente l'indice dedicato).
Le procedure di caricamento documenti sono invece relegate al modulo di ingest.

Author: Stefano Bellan (20054330)
"""

import os

from agno.knowledge.knowledge import Knowledge
from agno.vectordb.lancedb import LanceDb
from agno.vectordb.search import SearchType
from agno.knowledge.embedder.sentence_transformer import SentenceTransformerEmbedder

# ---------------------------------------------------------------------------
# Configurazione dei domini e routing verso le tabelle del Vector DB
# ---------------------------------------------------------------------------

# Definiamo la corrispondenza statica tra i contesti semantici e le tabelle fisiche,
# mantenendo i vecchi identificativi per non invalidare gli indici esistenti.
DOMAIN_TABLES = {
    "fitness": "protocolli_allenamento",
    "nutrition": "conoscenza_nutrizione",
}
DEFAULT_DOMAIN = "fitness"

# ---------------------------------------------------------------------------
# Parametri di inizializzazione per i modelli AI
# ---------------------------------------------------------------------------

# Modello di embedding standard. Attenzione: modificare questa costante
# richiederà la rigenerazione completa di tutti i vettori già memorizzati.
EMBEDDER_ID = "sentence-transformers/all-MiniLM-L6-v2"

# Carichiamo un cross-encoder ottimizzato per limitare l'impatto sulla memoria,
# sovrascrivendo i default della libreria per mantenere l'applicazione scalabile.
RERANKER_MODEL = os.getenv("RAG_RERANKER_MODEL", "cross-encoder/ms-marco-MiniLM-L-6-v2")

# Limite dei contesti da trattenere post-reranking per limitare i token al LLM.
RERANKER_TOP_N = int(os.getenv("RAG_RERANK_TOP_N", "5"))


def _db_dir() -> str:
    """
    Risolve il percorso assoluto della cartella dati di LanceDB.
    
    Author: Stefano Bellan (20054330)
    """
    base_dir = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_dir, "lancedb_vectors")


def vector_store_dir() -> str:
    """
    Espone pubblicamente il path del DB per l'accesso dalle pipeline esterne.
    
    Author: Stefano Bellan (20054330)
    """
    return _db_dir()


def _build_reranker():
    """
    Istanzia dinamicamente il modello di reranking basandosi sulle variabili d'ambiente.
    
    Se disabilitato restituisce None, mantenendo snello il footprint dell'applicazione.
    
    Author: Stefano Bellan (20054330)
    """
    if os.getenv("RAG_RERANK", "0") != "1":
        return None
    # Importiamo a runtime per evitare overhead di caricamento quando la feature è spenta
    from agno.knowledge.reranker.sentence_transformer import SentenceTransformerReranker
    return SentenceTransformerReranker(model=RERANKER_MODEL, top_n=RERANKER_TOP_N)


def _new_knowledge(domain: str) -> Knowledge:
    """
    Costruisce e configura il client per le interrogazioni sul dominio specificato.
    
    Abilitiamo la Hybrid Search nativa delegando ad Agno la creazione trasparente
    degli indici FTS/BM25, eliminando la necessità di engine di ricerca testuale esterni.
    
    Author: Stefano Bellan (20054330)
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
# Gestione Singleton per preservare i modelli in memoria
# ---------------------------------------------------------------------------
_KNOWLEDGE_CACHE: dict[str, Knowledge] = {}


def build_knowledge(domain: str = DEFAULT_DOMAIN, force_new: bool = False) -> Knowledge:
    """
    Risolve e restituisce l'istanza operativa della base di conoscenza associata.
    
    Applica un pattern singleton a livello di dominio per impedire continui caricamenti
    del modello in RAM durante lo svolgimento delle sessioni di chat, ottimizzando la latenza.
    
    Args:
        domain: Identificativo del contesto di ricerca desiderato.
        force_new: Flag per forzare l'allocazione di una nuova istanza, ignorando la cache.
        
    Returns:
        Knowledge: Istanza pronta per l'interrogazione tramite ricerca ibrida.
        
    Author: Stefano Bellan (20054330)
    """
    if domain not in DOMAIN_TABLES:
        raise ValueError(f"Dominio KB sconosciuto: '{domain}'. Ammessi: {list(DOMAIN_TABLES)}")

    if force_new:
        return _new_knowledge(domain)
    if domain not in _KNOWLEDGE_CACHE:
        _KNOWLEDGE_CACHE[domain] = _new_knowledge(domain)
    return _KNOWLEDGE_CACHE[domain]

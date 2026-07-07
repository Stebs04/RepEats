"""
Gestore del ciclo di vita dei documenti e dell'ingestion per le Knowledge Base.

Isola la logica di popolamento rispetto alla configurazione strutturale del DB.
Si occupa di ispezionare la directory sorgente, selezionare il parser idoneo per 
estensione, applicare le regole di frammentazione del testo (chunking) e iniettare 
i metadati rilevanti. Il flusso di sincronizzazione garantisce consistenza con il 
file system, rilevando aggiunte, modifiche o rimozioni tramite un manifest locale,
evitando in questo modo costosi ricalcoli sugli asset immutati.

Supporta l'esecuzione standalone da CLI per operazioni manuali o batch.

Author: Stefano Bellan (20054330)
"""

import os
import sys
import json

from agno.knowledge.chunking.recursive import RecursiveChunking

from src.database.knowledge_base import (
    build_knowledge,
    vector_store_dir,
    DOMAIN_TABLES,
    DEFAULT_DOMAIN,
)

# Impostiamo i parametri dimensionali per il partizionamento semantico del testo,
# modulabili dall'esterno per adattarsi alla tokenizzazione del modello scelto.
CHUNK_SIZE = int(os.getenv("RAG_CHUNK_SIZE", "1500"))
CHUNK_OVERLAP = int(os.getenv("RAG_CHUNK_OVERLAP", "150"))

SUPPORTED_EXTENSIONS = (".txt", ".md", ".pdf", ".docx")


def _docs_dir() -> str:
    """
    Risolve il path assoluto della directory di staging dei documenti.
    
    Author: Stefano Bellan (20054330)
    """
    base_dir = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_dir, "docs")


def _manifest_path() -> str:
    """
    Restituisce l'indirizzo del file di controllo per il tracking delle versioni.
    
    Author: Stefano Bellan (20054330)
    """
    return os.path.join(vector_store_dir(), ".ingest_manifest.json")


def _load_manifest() -> dict:
    """
    Legge lo stato precedente dell'indicizzazione gestendo l'assenza del file in modo silente.
    
    Author: Stefano Bellan (20054330)
    """
    path = _manifest_path()
    if not os.path.exists(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}


def _save_manifest(manifest: dict) -> None:
    """
    Scrive su disco lo snapshot aggiornato del repository documentale.
    
    Author: Stefano Bellan (20054330)
    """
    os.makedirs(vector_store_dir(), exist_ok=True)
    with open(_manifest_path(), "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)


def _file_signature(file_path: str) -> str:
    """
    Calcola un identificativo univoco e leggero per stabilire l'immutabilità dell'asset.
    
    Combina timestamp di sistema e dimensione del file primario assieme a quelli
    dell'eventuale sidecar JSON, permettendo di intercettare qualsiasi alterazione
    senza dover calcolare hash completi del contenuto.
    
    Author: Stefano Bellan (20054330)
    """
    st = os.stat(file_path)
    sig = f"{int(st.st_mtime)}:{st.st_size}"
    sidecar = os.path.splitext(file_path)[0] + ".meta.json"
    if os.path.exists(sidecar):
        sst = os.stat(sidecar)
        sig += f"|meta:{int(sst.st_mtime)}:{sst.st_size}"
    return sig


def _make_reader(ext: str):
    """
    Associa l'estensione del file all'implementazione del parser corrispondente.
    
    Ottimizziamo il footprint di memoria ricorrendo agli import differiti, dato che
    alcune librerie di decodifica binaria non sono necessarie per i formati testuali.
    
    Author: Stefano Bellan (20054330)
    """
    chunking = RecursiveChunking(chunk_size=CHUNK_SIZE, overlap=CHUNK_OVERLAP)
    ext = ext.lower()
    if ext == ".txt":
        from agno.knowledge.reader.text_reader import TextReader
        return TextReader(chunking_strategy=chunking)
    if ext == ".md":
        from agno.knowledge.reader.markdown_reader import MarkdownReader
        return MarkdownReader(chunking_strategy=chunking)
    if ext == ".pdf":
        from agno.knowledge.reader.pdf_reader import PDFReader
        return PDFReader(chunking_strategy=chunking)
    if ext == ".docx":
        from agno.knowledge.reader.docx_reader import DocxReader
        return DocxReader(chunking_strategy=chunking)
    return None


def _build_metadata(file_path: str) -> dict:
    """
    Raccoglie le informazioni ausiliarie per categorizzare il documento vettoriale.
    
    In assenza di un file sidecar dedicato, il processo fa ricorso a valori di
    default inferiti dal file system, garantendo un posizionamento robusto all'interno
    della tabella corretta del dominio di competenza.
    
    Author: Stefano Bellan (20054330)
    """
    filename = os.path.basename(file_path)
    stem, _ = os.path.splitext(filename)

    metadata = {
        "source": filename,
        "title": stem.replace("_", " ").strip().title(),
        "domain": DEFAULT_DOMAIN,
    }

    sidecar_path = os.path.splitext(file_path)[0] + ".meta.json"
    if os.path.exists(sidecar_path):
        try:
            with open(sidecar_path, "r", encoding="utf-8") as f:
                metadata.update(json.load(f))
        except (json.JSONDecodeError, OSError) as e:
            print(f"[WARN] Sidecar metadata ignorato per {filename}: {e}")

    # Normalizzazione dei dati in ingresso in caso di associazioni non valide
    if metadata.get("domain") not in DOMAIN_TABLES:
        print(f"[WARN] Dominio '{metadata.get('domain')}' non valido per {filename}, "
              f"uso '{DEFAULT_DOMAIN}'.")
        metadata["domain"] = DEFAULT_DOMAIN

    return metadata


def _iter_documents(docs_dir: str):
    """
    Scorre la repository fornendo un ordine di elaborazione prevedibile.
    
    Author: Stefano Bellan (20054330)
    """
    for name in sorted(os.listdir(docs_dir)):
        if name.endswith(".meta.json"):
            continue
        if not name.lower().endswith(SUPPORTED_EXTENSIONS):
            continue
        yield os.path.join(docs_dir, name)


# ---------------------------------------------------------------------------
# Meccanismo di riuso in memoria per gli accessi ai namespace dei vettori
# ---------------------------------------------------------------------------
def _kb(domain: str, cache: dict):
    if domain not in cache:
        cache[domain] = build_knowledge(domain=domain, force_new=True)
    return cache[domain]


def _index_file(file_path: str, cache: dict, skip_if_exists: bool = False) -> str | None:
    """
    Esegue l'operazione di caricamento e conversione vettoriale per un singolo asset.
    
    Restituisce lo spazio dei nomi presso cui i frammenti sono stati riversati,
    facilitando il tracciamento sul manifest e ignorando fallimenti isolati.
    
    Author: Stefano Bellan (20054330)
    """
    ext = os.path.splitext(file_path)[1]
    reader = _make_reader(ext)
    if reader is None:
        print(f"[WARN] Formato non supportato, saltato: {os.path.basename(file_path)}")
        return None

    metadata = _build_metadata(file_path)
    domain = metadata["domain"]
    try:
        _kb(domain, cache).add_content(
            path=file_path,
            metadata=metadata,
            reader=reader,
            upsert=True,
            skip_if_exists=skip_if_exists,
        )
        print(f"[OK] Indicizzato: {metadata['source']} (dominio: {domain})")
        return domain
    except Exception as e:
        # Isola i fallimenti procedurali per permettere la convergenza del batch
        print(f"[ERRORE] {metadata['source']}: {e}")
        return None


def delete_document(source: str, domain: str | None = None) -> bool:
    """
    Purga la base dati rimuovendo integralmente le righe associate a una risorsa.
    
    Args:
        source: Identificativo originale del file indicizzato.
        domain: Parametro opzionale per limitare la scope della cancellazione.
        
    Returns:
        bool: Riscontro positivo se l'operazione ha impattato lo store.
        
    Author: Stefano Bellan (20054330)
    """
    domains = [domain] if domain else list(DOMAIN_TABLES)
    removed_any = False
    for dom in domains:
        knowledge = build_knowledge(domain=dom, force_new=True)
        try:
            ok = knowledge.remove_vectors_by_metadata({"source": source})
        except Exception as e:
            print(f"[ERRORE] rimozione '{source}' da {dom}: {e}")
            continue
        if ok:
            print(f"[DEL] Rimosso '{source}' dal dominio {dom}.")
            removed_any = True
    return removed_any


def sync(full: bool = False) -> dict:
    """
    Allinea l'attuale topologia documentale con i record presenti a database.
    
    Il processo compara lo snapshot fisico con il manifest salvato alla precedente
    esecuzione per identificare aggiunte, alterazioni di contenuto e cancellazioni,
    evitando del tutto elaborazioni ridondanti sugli asset statici.
    
    Args:
        full: Forza l'overwrite bypassando il controllo di cache locale.
        
    Returns:
        dict: Metriche sintetiche dell'operazione di merge.
        
    Author: Stefano Bellan (20054330)
    """
    docs_dir = _docs_dir()
    if not os.path.isdir(docs_dir):
        print(f"[WARN] Cartella documenti non trovata: {docs_dir}")
        return {"added": 0, "updated": 0, "deleted": 0, "unchanged": 0}

    prev = {} if full else _load_manifest()
    cache: dict = {}
    new_manifest: dict = {}
    stats = {"added": 0, "updated": 0, "deleted": 0, "unchanged": 0}

    # Elencazione del contenuto corrente esposto nel file system
    current = {os.path.basename(p): p for p in _iter_documents(docs_dir)}

    # Fasi di pulizia: evizione delle risorse dismesse in base al differenziale
    for source, entry in prev.items():
        if source not in current:
            if delete_document(source, domain=entry.get("domain")):
                stats["deleted"] += 1

    # Flusso di ingest per i file novelli o contrassegnati come stale
    for source, file_path in current.items():
        sig = _file_signature(file_path)
        old = prev.get(source)

        if old and old.get("sig") == sig:
            # Passthrough rapido per asset verificati ed identici al run precedente
            new_manifest[source] = old
            stats["unchanged"] += 1
            continue

        # Rilocazione inter-dominio: eliminiamo le vecchie tracce per evitare split cerebrali
        if old and old.get("domain"):
            new_domain = _build_metadata(file_path)["domain"]
            if new_domain != old["domain"]:
                delete_document(source, domain=old["domain"])

        domain = _index_file(file_path, cache, skip_if_exists=False)
        if domain is None:
            # Registriamo in modo permissivo: riproveremo alla successiva transazione
            continue
        new_manifest[source] = {"domain": domain, "sig": sig}
        stats["added" if not old else "updated"] += 1

    _save_manifest(new_manifest)
    print(f"[KB] Sync completata: +{stats['added']} nuovi, "
          f"~{stats['updated']} aggiornati, -{stats['deleted']} rimossi, "
          f"={stats['unchanged']} invariati.")
    return stats


def _print_usage():
    print("Uso:")
    print("  python -m src.knowledge_base.ingest                 # sincronizza docs/ con l'indice")
    print("  python -m src.knowledge_base.ingest --full          # re-indicizza tutto")
    print("  python -m src.knowledge_base.ingest --delete NOME   # rimuove un documento dall'indice")
    print("     opzionale: --domain fitness|nutrition")


if __name__ == "__main__":
    args = sys.argv[1:]
    if not args:
        sync()
    elif args[0] == "--full":
        sync(full=True)
    elif args[0] == "--delete" and len(args) >= 2:
        dom = None
        if "--domain" in args:
            dom = args[args.index("--domain") + 1]
        deleted = delete_document(args[1], domain=dom)
        # Aggiorniamo la contabilità dei file post operazione di cancellazione forzata
        if deleted:
            man = _load_manifest()
            man.pop(args[1], None)
            _save_manifest(man)
        if not deleted:
            print(f"[WARN] Nessun chunk trovato per '{args[1]}'.")
    else:
        _print_usage()

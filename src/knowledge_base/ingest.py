"""
Pipeline di ingestion/sincronizzazione delle Knowledge Base RAG di RepEats.

Responsabilità (separata dal builder in src/database/knowledge_base.py):
- scansiona la cartella dei documenti (`src/knowledge_base/docs/`),
- seleziona il reader adatto al formato (txt, md, pdf, docx),
- applica il chunking configurabile e l'arricchimento con metadati,
- instrada ogni documento verso la KB del suo DOMINIO (fitness / nutrition),
- SINCRONIZZA l'indice con la cartella: indicizza i nuovi, ri-indicizza i
  modificati e rimuove dall'indice i documenti eliminati da docs/.

La sincronizzazione si basa su un manifest (mtime + dimensione) salvato accanto
al vector store, così da rilevare le differenze ad ogni avvio senza rileggere
inutilmente file immutati.

Eseguibile come modulo:
    python -m src.knowledge_base.ingest            # sincronizza docs/ con l'indice
    python -m src.knowledge_base.ingest --full     # forza la re-indicizzazione di tutto
    python -m src.knowledge_base.ingest --delete NOME [--domain fitness|nutrition]

`sync()` viene invocata automaticamente all'avvio dell'applicazione (main.py).

Autore: Stefano Bellan (20054330)
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

# Parametri di chunking (override via env). RecursiveChunking spezza il testo
# rispettando i confini naturali (paragrafi/frasi) fino a chunk_size caratteri.
CHUNK_SIZE = int(os.getenv("RAG_CHUNK_SIZE", "1500"))
CHUNK_OVERLAP = int(os.getenv("RAG_CHUNK_OVERLAP", "150"))

SUPPORTED_EXTENSIONS = (".txt", ".md", ".pdf", ".docx")


def _docs_dir() -> str:
    """Percorso assoluto della cartella dei documenti da indicizzare."""
    base_dir = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_dir, "docs")


def _manifest_path() -> str:
    """Percorso del manifest che traccia lo stato dei documenti indicizzati."""
    return os.path.join(vector_store_dir(), ".ingest_manifest.json")


def _load_manifest() -> dict:
    """Carica il manifest precedente ({source: {domain, sig}}). Vuoto se assente."""
    path = _manifest_path()
    if not os.path.exists(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}


def _save_manifest(manifest: dict) -> None:
    """Persiste il manifest aggiornato."""
    os.makedirs(vector_store_dir(), exist_ok=True)
    with open(_manifest_path(), "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)


def _file_signature(file_path: str) -> str:
    """
    Firma di contenuto del file per rilevare modifiche: mtime + dimensione.
    Se cambia uno dei due, il documento è considerato modificato e va re-indicizzato.
    Include anche la firma del sidecar, così un cambio di metadati/dominio è rilevato.
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
    Restituisce il reader Agno adatto all'estensione, con la strategia di
    chunking condivisa. Import locali: i reader binari (pdf/docx) hanno
    dipendenze pesanti (pypdf, python-docx) caricate solo quando servono.

    Ritorna None per estensioni non supportate.
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
    Arricchisce ogni documento con metadati di provenienza.

    Ordine di precedenza:
    1. Un file sidecar `<documento>.meta.json` (se presente) fornisce i campi
       espliciti (es. domain, title, fonte, anno).
    2. In assenza del sidecar, i metadati sono derivati dal nome del file e il
       dominio è quello di default (fitness).

    Il campo `domain` determina in quale KB/tabella finisce il documento.
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

    # Difesa: dominio non valido nel sidecar -> ricade sul default.
    if metadata.get("domain") not in DOMAIN_TABLES:
        print(f"[WARN] Dominio '{metadata.get('domain')}' non valido per {filename}, "
              f"uso '{DEFAULT_DOMAIN}'.")
        metadata["domain"] = DEFAULT_DOMAIN

    return metadata


def _iter_documents(docs_dir: str):
    """Genera i percorsi assoluti dei documenti indicizzabili, in ordine stabile."""
    for name in sorted(os.listdir(docs_dir)):
        if name.endswith(".meta.json"):
            continue
        if not name.lower().endswith(SUPPORTED_EXTENSIONS):
            continue
        yield os.path.join(docs_dir, name)


# ---------------------------------------------------------------------------
# Cache delle KB per dominio (evita di ricostruire l'embedder più volte in un run)
# ---------------------------------------------------------------------------
def _kb(domain: str, cache: dict):
    if domain not in cache:
        cache[domain] = build_knowledge(domain=domain, force_new=True)
    return cache[domain]


def _index_file(file_path: str, cache: dict, skip_if_exists: bool = False) -> str | None:
    """
    Indicizza (upsert) un singolo file nella KB del suo dominio.
    Ritorna il dominio in cui è stato indicizzato, o None in caso di skip/errore.
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
        # Un documento problematico non deve interrompere l'intera pipeline.
        print(f"[ERRORE] {metadata['source']}: {e}")
        return None


def delete_document(source: str, domain: str | None = None) -> bool:
    """
    Rimuove dall'indice tutti i chunk di un documento, identificato dal nome file
    (metadato `source`).

    Args:
        source: nome del file come indicizzato (es. "indice_glicemico.docx").
        domain: dominio in cui cercare. Se None prova entrambi.

    Returns:
        True se almeno un dominio ha rimosso qualcosa.
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
    Sincronizza l'indice con la cartella docs/.

    - Documenti NUOVI  -> indicizzati.
    - Documenti MODIFICATI (mtime/dimensione o sidecar cambiati) -> re-indicizzati.
    - Documenti ELIMINATI da docs/ -> rimossi dall'indice.
    - Documenti INVARIATI -> saltati (nessun ricalcolo di embedding).

    Args:
        full: se True ignora il manifest e re-indicizza tutti i file presenti.

    Returns:
        Riepilogo {"added","updated","deleted","unchanged"}.
    """
    docs_dir = _docs_dir()
    if not os.path.isdir(docs_dir):
        print(f"[WARN] Cartella documenti non trovata: {docs_dir}")
        return {"added": 0, "updated": 0, "deleted": 0, "unchanged": 0}

    prev = {} if full else _load_manifest()
    cache: dict = {}
    new_manifest: dict = {}
    stats = {"added": 0, "updated": 0, "deleted": 0, "unchanged": 0}

    # File attualmente presenti in docs/
    current = {os.path.basename(p): p for p in _iter_documents(docs_dir)}

    # 1) Rimozione dei documenti spariti da docs/ (presenti nel manifest, non su disco)
    for source, entry in prev.items():
        if source not in current:
            if delete_document(source, domain=entry.get("domain")):
                stats["deleted"] += 1

    # 2) Aggiunta / aggiornamento dei documenti presenti
    for source, file_path in current.items():
        sig = _file_signature(file_path)
        old = prev.get(source)

        if old and old.get("sig") == sig:
            # Invariato: mantiene la voce di manifest esistente.
            new_manifest[source] = old
            stats["unchanged"] += 1
            continue

        # Se il dominio è cambiato rispetto a prima, rimuovi dalla vecchia tabella.
        if old and old.get("domain"):
            new_domain = _build_metadata(file_path)["domain"]
            if new_domain != old["domain"]:
                delete_document(source, domain=old["domain"])

        domain = _index_file(file_path, cache, skip_if_exists=False)
        if domain is None:
            # Errore/skip: non lo registriamo, così al prossimo avvio ci riprova.
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
        # Mantieni il manifest coerente dopo una delete manuale.
        if deleted:
            man = _load_manifest()
            man.pop(args[1], None)
            _save_manifest(man)
        if not deleted:
            print(f"[WARN] Nessun chunk trovato per '{args[1]}'.")
    else:
        _print_usage()

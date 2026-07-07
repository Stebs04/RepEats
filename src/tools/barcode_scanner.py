"""
Modulo dedicato all'estrazione deterministica dei codici a barre dalle immagini.

L'approccio basato sui pixel evita eventuali allucinazioni del modello linguistico.
In assenza di un codice leggibile, la funzione restituisce None, permettendo al
flusso chiamante di ripiegare sull'analisi visiva della pietanza.
L'architettura prevede un parser primario basato su zxing-cpp per la massima
compatibilità con i vari formati, e un fallback su OpenCV nel caso la libreria
principale non fosse disponibile o non riuscisse a risolvere l'immagine.

Author: Stefano Bellan (20054330)
"""

from typing import List, Optional
import cv2
import numpy as np

# L'inclusione di zxing-cpp è gestita in modo opzionale per garantire
# l'avvio dell'applicazione anche in ambienti sprovvisti della libreria,
# affidandosi in tal caso al solo fallback di OpenCV.
try:
    import zxingcpp
except ImportError:  # pragma: no cover
    zxingcpp = None


def _estrai_codice(result) -> Optional[str]:
    """
    Uniforma l'output della libreria OpenCV ed estrae la prima stringa valida.
    
    Gestisce in modo trasparente le discrepanze tra le firme di detectAndDecode
    nelle varie versioni di OpenCV, garantendo l'accesso corretto al payload
    senza incappare in falsi negativi dovuti ai booleani di ritorno.
    
    Author: Stefano Bellan (20054330)
    """
    if not result:
        return None

    if len(result) >= 4:
        decoded_info = result[1]
    else:
        decoded_info = result[0]

    # Uniformiamo il formato del payload per gestire le diverse strutture
    # di ritorno restituite a seconda della versione di OpenCV installata.
    if isinstance(decoded_info, str):
        candidati = [decoded_info]
    else:
        candidati = list(decoded_info) if decoded_info else []

    for code in candidati:
        valido = _numero_valido((code or "").strip())
        if valido:
            return valido

    return None


def _checksum_gtin_valido(cifre: str) -> bool:
    """
    Esegue la validazione formale del check digit per gli standard GTIN.
    
    Il controllo matematico scarta automaticamente le letture spurie o
    i falsi positivi generati dal rumore visivo presente nelle texture del cibo.
    
    Author: Stefano Bellan (20054330)
    """
    payload, atteso = cifre[:-1], int(cifre[-1])
    somma = 0
    for i, ch in enumerate(reversed(payload)):
        peso = 3 if i % 2 == 0 else 1
        somma += int(ch) * peso
    return (10 - somma % 10) % 10 == atteso


def _ruota(img, angolo: float):
    """
    Effettua una rotazione dell'immagine preservando i bordi tramite padding bianco.
    
    Author: Stefano Bellan (20054330)
    """
    h, w = img.shape[:2]
    M = cv2.getRotationMatrix2D((w / 2, h / 2), angolo, 1.0)
    return cv2.warpAffine(
        img, M, (w, h), borderValue=(255, 255, 255), flags=cv2.INTER_CUBIC
    )


def _preprocessa(img) -> List["np.ndarray"]:
    """
    Costruisce un set di varianti dell'immagine applicando filtri incrementali.
    
    L'approccio iterativo serve a compensare la bassa qualità tipica delle
    fotografie da smartphone, applicando trasformazioni come CLAHE e Otsu
    per isolare correttamente i pattern del codice a barre dallo sfondo.
    
    Author: Stefano Bellan (20054330)
    """
    # Aggiungiamo un margine bianco per ricreare la quiet zone obbligatoria
    con_bordo = cv2.copyMakeBorder(
        img, 100, 100, 100, 100, cv2.BORDER_CONSTANT, value=(255, 255, 255)
    )

    gray = cv2.cvtColor(con_bordo, cv2.COLOR_BGR2GRAY)
    # Applichiamo il CLAHE per ottimizzare il contrasto mantenendo il bilanciamento
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8)).apply(gray)
    # Riduciamo il rumore tramite binarizzazione di Otsu
    _, otsu = cv2.threshold(clahe, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    # Upscaling esplorativo per decodificare codici ripresi da lontano
    upscaled = cv2.resize(clahe, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)

    varianti = [
        img,
        con_bordo,
        cv2.GaussianBlur(con_bordo, (3, 3), 0),
        gray,
        clahe,
        otsu,
        # Rimozione del rumore di fondo per foto a bassa esposizione
        cv2.fastNlMeansDenoising(gray, None, 10, 7, 21),
        cv2.GaussianBlur(upscaled, (5, 5), 0),
    ]

    # Aggiungiamo iterazioni ruotate per gestire inquadrature disallineate
    for angolo in (-15, -8, 8, 15):
        varianti.append(_ruota(clahe, angolo))

    return varianti


def _numero_valido(text: Optional[str]) -> Optional[str]:
    """
    Sanitizza e valida la stringa estratta verificando che aderisca allo standard GTIN.
    
    Il filtraggio previene l'elaborazione di falsi positivi generati da letture
    errate su texture complesse.
    
    Author: Stefano Bellan (20054330)
    """
    if not text:
        return None
    cifre = "".join(filter(str.isdigit, text))
    if len(cifre) in (8, 12, 13, 14) and _checksum_gtin_valido(cifre):
        return cifre
    return None


def _scan_zxing(img) -> Optional[str]:
    """
    Tenta la decodifica primaria utilizzando zxing-cpp, garantendo supporto esteso.
    
    Itera tra l'immagine originale e le relative varianti preprocessate per
    massimizzare la resa sui formati complessi.
    
    Author: Stefano Bellan (20054330)
    """
    if zxingcpp is None:
        return None

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8)).apply(gray)
    for candidato in (img, gray, clahe):
        try:
            risultati = zxingcpp.read_barcodes(candidato)
        except Exception:
            continue
        for r in risultati:
            code = _numero_valido(r.text)
            if code:
                return code
    return None


def _scan_opencv(img) -> Optional[str]:
    """
    Gestisce il fallback tramite i moduli standard di OpenCV.
    
    Applica una serie progressiva di filtri fino a quando non rileva e decodifica
    correttamente un codice supportato.
    
    Author: Stefano Bellan (20054330)
    """
    detector = cv2.barcode.BarcodeDetector()
    for variante in _preprocessa(img):
        code = _estrai_codice(detector.detectAndDecode(variante))
        if code:
            return code
    return None


def scan_barcode(image_path: str) -> Optional[str]:
    """
    Innesca la pipeline di decodifica per estrarre il payload dal file immagine.

    Inizia l'elaborazione affidandosi alla libreria primaria e, in caso di esito
    negativo, esegue il fallback sul motore integrato. Restituisce direttamente
    il codice sanitizzato oppure None se la foto non presenta pattern rilevabili.

    Args:
        image_path (str): Indirizzo assoluto del file da processare.

    Returns:
        Optional[str]: Codice alfanumerico normalizzato, se decodificato.
        
    Author: Stefano Bellan (20054330)
    """
    img = cv2.imread(image_path)
    if img is None:
        return None

    return _scan_zxing(img) or _scan_opencv(img)

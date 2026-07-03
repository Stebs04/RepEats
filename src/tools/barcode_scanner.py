"""
Modulo per la lettura deterministica di codici a barre dalle immagini.

Decodifica direttamente i pixel (nessuna allucinazione dell'LLM): se
l'immagine non contiene un codice a barre leggibile la funzione restituisce
None e il chiamante procede con la stima visiva.

Pipeline a due decoder:
1. zxing-cpp (primario): legge molte simbologie tra cui Code 128, che spesso
   codifica un EAN-13 pur non essendo un vero barcode EAN. cv2 NON legge il
   Code 128 e falliva su questi codici (es. screenshot renderizzati).
2. OpenCV BarcodeDetector (fallback): copre i casi in cui zxing non è
   installato o non decodifica.

Autore: Stefano Bellan (20054330)
"""

from typing import List, Optional
import cv2
import numpy as np

# zxing-cpp è opzionale: se non installato il modulo resta funzionante col
# solo fallback OpenCV. Import protetto per non rompere l'avvio.
try:
    import zxingcpp
except ImportError:  # pragma: no cover
    zxingcpp = None


def _estrai_codice(result) -> Optional[str]:
    """
    Normalizza il risultato di detectAndDecode ed estrae il primo codice valido.

    La firma di detectAndDecode cambia con la versione di OpenCV:
    - OpenCV >= 4.8: (retval: bool, decoded_info, decoded_type, points)
    - build contrib più vecchie / cv2 5.x: (decoded_info, decoded_type, points)
    I dati del barcode sono in decoded_info: nel primo caso è result[1]
    (result[0] è il bool retval), nel secondo è result[0]. Leggere sempre
    result[0] restituiva il booleano e il codice non veniva mai trovato.
    """
    if not result:
        return None

    if len(result) >= 4:
        decoded_info = result[1]
    else:
        decoded_info = result[0]

    # decoded_info può essere una stringa singola o una tupla/lista di stringhe
    # a seconda della versione di OpenCV. Normalizziamo.
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
    Verifica il check digit GTIN (EAN-8/13, UPC-A, GTIN-14).

    L'ultima cifra è di controllo: partendo dalla penultima verso sinistra i
    pesi si alternano 3,1,3,1... La somma pesata + la cifra di controllo deve
    essere multiplo di 10. Un barcode letto per errore su una texture di cibo
    quasi mai supera questo controllo, quindi filtra i falsi positivi.
    """
    payload, atteso = cifre[:-1], int(cifre[-1])
    somma = 0
    for i, ch in enumerate(reversed(payload)):
        peso = 3 if i % 2 == 0 else 1
        somma += int(ch) * peso
    return (10 - somma % 10) % 10 == atteso


def _ruota(img, angolo: float):
    """Ruota l'immagine attorno al centro riempiendo il bordo di bianco."""
    h, w = img.shape[:2]
    M = cv2.getRotationMatrix2D((w / 2, h / 2), angolo, 1.0)
    return cv2.warpAffine(
        img, M, (w, h), borderValue=(255, 255, 255), flags=cv2.INTER_CUBIC
    )


def _preprocessa(img) -> List["np.ndarray"]:
    """
    Genera varianti pre-processate della stessa immagine per aumentare le
    probabilità di detection su foto reali (sfocate, rumorose, poco
    contrastate). Ordinate per costo crescente: si testano finché una decodifica.

    Le foto da smartphone falliscono spesso perché il detector cv2 è sensibile
    a rumore JPEG e basso contrasto. Grayscale + CLAHE + threshold rendono le
    barre nette; le rotazioni recuperano i codici inquadrati storti.
    """
    # Margine bianco: garantisce la "quiet zone" quando il codice è a filo bordo.
    con_bordo = cv2.copyMakeBorder(
        img, 100, 100, 100, 100, cv2.BORDER_CONSTANT, value=(255, 255, 255)
    )

    gray = cv2.cvtColor(con_bordo, cv2.COLOR_BGR2GRAY)
    # CLAHE: alza il contrasto locale delle barre senza bruciare i bianchi.
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8)).apply(gray)
    # Otsu: binarizzazione netta barre/sfondo, elimina il rumore di luminanza.
    _, otsu = cv2.threshold(clahe, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    # Upscale per barcode piccoli dentro la scena (foto del piatto da lontano).
    upscaled = cv2.resize(clahe, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)

    varianti = [
        img,
        con_bordo,
        cv2.GaussianBlur(con_bordo, (3, 3), 0),
        gray,
        clahe,
        otsu,
        # Denoise leggero: recupera i codici delle foto rumorose.
        cv2.fastNlMeansDenoising(gray, None, 10, 7, 21),
        cv2.GaussianBlur(upscaled, (5, 5), 0),
    ]

    # Rotazioni sul grayscale a contrasto alzato: codici inquadrati storti.
    for angolo in (-15, -8, 8, 15):
        varianti.append(_ruota(clahe, angolo))

    return varianti


def _numero_valido(text: Optional[str]) -> Optional[str]:
    """
    Estrae le sole cifre e le accetta solo se sono un EAN/UPC/GTIN valido:
    lunghezza standard (8, 12, 13, 14) e check digit corretto. Il controllo
    di checksum scarta le letture spurie sulle texture del cibo, che quasi mai
    formano un codice matematicamente valido.
    """
    if not text:
        return None
    cifre = "".join(filter(str.isdigit, text))
    if len(cifre) in (8, 12, 13, 14) and _checksum_gtin_valido(cifre):
        return cifre
    return None


def _scan_zxing(img) -> Optional[str]:
    """
    Decodifica con zxing-cpp (se installato). Legge anche il Code 128, che
    cv2 non gestisce. Prova l'immagine originale e alcune varianti a contrasto
    alzato per i casi difficili.
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
    Fallback OpenCV: legge EAN-8/13 e UPC-A/E. Generiamo più varianti
    pre-processate (grayscale, CLAHE, threshold, denoise, upscale, rotazioni)
    e ci fermiamo al primo esito valido.
    """
    detector = cv2.barcode.BarcodeDetector()
    for variante in _preprocessa(img):
        code = _estrai_codice(detector.detectAndDecode(variante))
        if code:
            return code
    return None


def scan_barcode(image_path: str) -> Optional[str]:
    """
    Legge un codice a barre da un file immagine.

    Prima tenta zxing-cpp (copre più simbologie, incluso Code 128 e gli
    screenshot renderizzati), poi ripiega su OpenCV. Restituisce None se
    nessun decoder trova un codice valido (immagine di cibo o barcode
    assente/illeggibile).

    Args:
        image_path (str): Percorso del file immagine da analizzare.

    Returns:
        Optional[str]: Le cifre del codice a barre (8-14) se trovato e valido,
        altrimenti None.
    """
    img = cv2.imread(image_path)
    if img is None:
        return None

    return _scan_zxing(img) or _scan_opencv(img)

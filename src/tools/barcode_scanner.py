"""
Modulo per la lettura deterministica di codici a barre dalle immagini.

Usa il decoder nativo di OpenCV (cv2.barcode.BarcodeDetector) che lavora
direttamente sui pixel: nessuna allucinazione dell'LLM. Se l'immagine non
contiene un codice a barre leggibile, la funzione restituisce None e il
chiamante procede con la stima visiva.

Autore: Stefano Bellan (20054330)
"""

from typing import Optional
import cv2


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
        code = (code or "").strip()
        # Solo codici numerici EAN/UPC plausibili (8-14 cifre).
        if code.isdigit() and 8 <= len(code) <= 14:
            return code

    return None


def scan_barcode(image_path: str) -> Optional[str]:
    """
    Legge un codice a barre da un file immagine.

    Il detector di OpenCV è addestrato su foto reali: su immagini troppo
    nitide (screenshot, barcode renderizzati) o con il codice a filo del
    bordo la detection fallisce. Per questo proviamo più varianti
    dell'immagine in ordine di costo crescente, fermandoci al primo esito.

    Args:
        image_path (str): Percorso del file immagine da analizzare.

    Returns:
        Optional[str]: Le cifre del codice a barre (>= 8) se trovato e valido,
        altrimenti None (immagine di cibo, barcode assente o illeggibile).
    """
    img = cv2.imread(image_path)
    if img is None:
        return None

    detector = cv2.barcode.BarcodeDetector()

    # Variante con margine bianco: garantisce la "quiet zone" attorno al
    # codice anche quando il barcode arriva a filo del bordo dell'immagine.
    con_bordo = cv2.copyMakeBorder(
        img, 100, 100, 100, 100, cv2.BORDER_CONSTANT, value=(255, 255, 255)
    )

    varianti = [
        img,
        cv2.GaussianBlur(img, (3, 3), 0),
        con_bordo,
        cv2.GaussianBlur(con_bordo, (3, 3), 0),
        # Ultimo tentativo per immagini piccole: upscale + blur.
        cv2.GaussianBlur(
            cv2.resize(con_bordo, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC),
            (5, 5), 0
        ),
    ]

    for variante in varianti:
        code = _estrai_codice(detector.detectAndDecode(variante))
        if code:
            return code

    return None

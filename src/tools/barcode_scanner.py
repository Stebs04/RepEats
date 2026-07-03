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


def scan_barcode(image_path: str) -> Optional[str]:
    """
    Legge un codice a barre da un file immagine.

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
    result = detector.detectAndDecode(img)

    # detectAndDecode può restituire decoded_info come stringa singola o come
    # tupla/lista di stringhe a seconda della versione di OpenCV. Normalizziamo.
    decoded_info = result[0] if result else None
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

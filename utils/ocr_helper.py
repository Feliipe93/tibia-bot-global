"""
utils/ocr_helper.py - OCR optimizado para leer texto de la interfaz de Tibia.
Usa preprocesamiento con OpenCV + Tesseract (o EasyOCR como alternativa).
Optimizado para el font pixel de Tibia (blanco sobre fondo oscuro).
"""

import cv2
import numpy as np
from typing import Dict, List, Optional, Tuple


class OCRHelper:
    """
    Helper de OCR para leer texto de la interfaz de Tibia.
    Usa preprocesamiento agresivo para mejorar precisión en texto pixel.
    """

    def __init__(self, engine: str = "tesseract"):
        """
        Args:
            engine: "tesseract" o "easyocr".
        """
        self.engine = engine
        self._tesseract_available = False
        self._easyocr_reader = None

        self._init_engine()

    def _init_engine(self) -> None:
        """Inicializa el motor de OCR."""
        if self.engine == "tesseract":
            try:
                import pytesseract  # type: ignore
                pytesseract.get_tesseract_version()
                self._tesseract_available = True
            except Exception:
                self._tesseract_available = False
        elif self.engine == "easyocr":
            try:
                import easyocr  # type: ignore
                self._easyocr_reader = easyocr.Reader(["en"], gpu=False)
            except Exception:
                self._easyocr_reader = None

    @property
    def is_available(self) -> bool:
        """True si el motor de OCR está disponible."""
        if self.engine == "tesseract":
            return self._tesseract_available
        return self._easyocr_reader is not None

    # ==================================================================
    # Preprocesamiento
    # ==================================================================
    @staticmethod
    def preprocess_for_ocr(
        img: np.ndarray,
        scale: float = 3.0,
        invert: bool = True,
        threshold: int = 120,
    ) -> np.ndarray:
        """
        Preprocesa una imagen para mejorar la precisión del OCR.

        El texto de Tibia es blanco/amarillo sobre fondo oscuro.
        Pasos:
        1. Convertir a escala de grises
        2. Escalar (agrandar el texto pixel)
        3. Threshold binario
        4. Invertir si necesario (OCR prefiere negro sobre blanco)

        Args:
            img: Imagen BGR de la región de texto.
            scale: Factor de escalado (3x funciona bien para Tibia).
            invert: Invertir colores (texto negro sobre blanco).
            threshold: Umbral de binarización.

        Returns:
            Imagen preprocesada lista para OCR.
        """
        # Escala de grises
        if len(img.shape) == 3:
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        else:
            gray = img.copy()

        # Escalar
        if scale != 1.0:
            h, w = gray.shape[:2]
            gray = cv2.resize(
                gray,
                (int(w * scale), int(h * scale)),
                interpolation=cv2.INTER_NEAREST,
            )

        # Threshold binario
        _, binary = cv2.threshold(gray, threshold, 255, cv2.THRESH_BINARY)

        # Invertir (Tibia: texto claro sobre fondo oscuro → OCR prefiere inverso)
        if invert:
            binary = cv2.bitwise_not(binary)

        return binary

    @staticmethod
    def extract_colored_text(
        img: np.ndarray,
        color_ranges: List[Tuple[np.ndarray, np.ndarray]],
        scale: float = 3.0,
    ) -> np.ndarray:
        """
        Extrae texto de un color específico de la imagen.
        Útil para separar texto blanco, amarillo, rojo, etc.

        Args:
            img: Imagen BGR.
            color_ranges: Lista de (hsv_min, hsv_max) para los colores del texto.
            scale: Factor de escalado.

        Returns:
            Máscara binaria del texto extraído.
        """
        hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
        mask = np.zeros(hsv.shape[:2], dtype=np.uint8)

        for lower, upper in color_ranges:
            partial = cv2.inRange(hsv, lower, upper)
            mask = cv2.bitwise_or(mask, partial)

        if scale != 1.0:
            h, w = mask.shape[:2]
            mask = cv2.resize(
                mask,
                (int(w * scale), int(h * scale)),
                interpolation=cv2.INTER_NEAREST,
            )

        return mask

    # ==================================================================
    # Lectura de texto
    # ==================================================================
    def read_text(
        self,
        img: np.ndarray,
        preprocess: bool = True,
        config: str = "--psm 7 --oem 3",
    ) -> str:
        """
        Lee texto de una imagen.

        Args:
            img: Imagen (BGR o ya preprocesada).
            preprocess: Aplicar preprocesamiento automático.
            config: Configuración de Tesseract (PSM 7 = línea única).

        Returns:
            Texto detectado (strip).
        """
        if preprocess:
            processed = self.preprocess_for_ocr(img)
        else:
            processed = img

        if self.engine == "tesseract" and self._tesseract_available:
            import pytesseract  # type: ignore
            text = pytesseract.image_to_string(processed, config=config)
            return text.strip()

        elif self._easyocr_reader is not None:
            results = self._easyocr_reader.readtext(processed)
            texts = [r[1] for r in results if r[2] > 0.5]
            return " ".join(texts).strip()

        return ""

    def read_lines(
        self,
        img: np.ndarray,
        preprocess: bool = True,
    ) -> List[str]:
        """
        Lee múltiples líneas de texto.

        Args:
            img: Imagen de la región de texto.

        Returns:
            Lista de líneas detectadas.
        """
        if preprocess:
            processed = self.preprocess_for_ocr(img)
        else:
            processed = img

        if self.engine == "tesseract" and self._tesseract_available:
            import pytesseract  # type: ignore
            text = pytesseract.image_to_string(processed, config="--psm 6 --oem 3")
            lines = [l.strip() for l in text.split("\n") if l.strip()]
            return lines

        elif self._easyocr_reader is not None:
            results = self._easyocr_reader.readtext(processed)
            return [r[1] for r in results if r[2] > 0.4]

        return []

    def read_number(
        self,
        img: np.ndarray,
        preprocess: bool = True,
    ) -> Optional[int]:
        """
        Lee un número de una imagen. Útil para leer HP numérico,
        cantidades de gold, etc.

        Returns:
            Número entero o None si no se detecta.
        """
        text = self.read_text(
            img,
            preprocess=preprocess,
            config="--psm 7 --oem 3 -c tessedit_char_whitelist=0123456789",
        )
        # Limpiar y extraer dígitos
        digits = "".join(c for c in text if c.isdigit())
        if digits:
            return int(digits)
        return None

    # ==================================================================
    # Detección de texto por color (sin OCR)
    # ==================================================================
    @staticmethod
    def detect_white_text_regions(
        img: np.ndarray,
        min_width: int = 20,
        min_height: int = 8,
    ) -> List[Tuple[int, int, int, int]]:
        """
        Detecta regiones con texto blanco (nombres de mobs, HP text, etc).
        No usa OCR, solo detecta dónde hay texto.

        Returns:
            Lista de (x, y, w, h) de regiones con texto.
        """
        # Texto blanco de Tibia: alto valor en todos los canales
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        _, mask = cv2.threshold(gray, 200, 255, cv2.THRESH_BINARY)

        # Dilatar para unir caracteres
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 1))
        dilated = cv2.dilate(mask, kernel, iterations=2)

        contours, _ = cv2.findContours(
            dilated, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )

        regions = []
        for cnt in contours:
            x, y, w, h = cv2.boundingRect(cnt)
            if w >= min_width and h >= min_height:
                regions.append((x, y, w, h))

        return regions

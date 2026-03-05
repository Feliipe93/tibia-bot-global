"""
bar_detector.py - Detección de barras de HP y Mana usando OpenCV HSV.
Incluye calibración automática de posición de barras.
"""

import cv2
import numpy as np
from typing import Dict, Optional, Tuple

# ======================================================================
# Rangos HSV para detectar colores de las barras de Tibia
# En OpenCV: H = 0..180, S = 0..255, V = 0..255
# ======================================================================

# HP 100%→60%: VERDE
VERDE_MIN = np.array([35, 60, 60])
VERDE_MAX = np.array([90, 255, 255])

# HP 60%→30%: AMARILLO / NARANJA
AMARILLO_MIN = np.array([20, 100, 100])
AMARILLO_MAX = np.array([35, 255, 255])

# HP 30%→0%: ROJO (rojo tiene DOS rangos en HSV porque está en ambos extremos)
ROJO_MIN1 = np.array([0, 100, 100])
ROJO_MAX1 = np.array([10, 255, 255])
ROJO_MIN2 = np.array([170, 100, 100])
ROJO_MAX2 = np.array([180, 255, 255])

# Mana: AZUL
AZUL_MIN = np.array([95, 60, 60])
AZUL_MAX = np.array([135, 255, 255])


class BarDetector:
    """Detecta porcentajes de HP y Mana a partir de capturas del proyector OBS."""

    def __init__(
        self,
        expected_full_width_ratio: float = 0.43,
        scan_height_ratio: float = 0.10,
    ):
        self.expected_full_width_ratio = expected_full_width_ratio
        self.scan_height_ratio = scan_height_ratio

        # Datos de calibración
        self.calibrated = False
        self.hp_row: Optional[int] = None
        self.mp_row: Optional[int] = None
        self.bar_max_width: int = 0

        # Últimas máscaras (para debug visual)
        self.last_mask_hp: Optional[np.ndarray] = None
        self.last_mask_mp: Optional[np.ndarray] = None
        self.last_region: Optional[np.ndarray] = None
        self.last_scan_height: int = 0

    def detect(self, img: np.ndarray) -> Tuple[Optional[float], Optional[float]]:
        """
        Detecta el porcentaje de HP y Mana de la imagen capturada.

        Args:
            img: Imagen BGR del proyector OBS (sin bordes de ventana).

        Returns:
            Tupla (hp_percent, mp_percent) donde cada uno es float 0.0..1.0
            o None si no se puede detectar.
        """
        if img is None or img.size == 0:
            return None, None

        h, w = img.shape[:2]

        # Recortar franja superior donde están las barras
        scan_height = max(60, int(h * self.scan_height_ratio))
        self.last_scan_height = scan_height
        region = img[0:scan_height, :]
        self.last_region = region.copy()

        # Convertir a HSV
        hsv = cv2.cvtColor(region, cv2.COLOR_BGR2HSV)

        # Crear máscaras para HP (verde + amarillo + rojo)
        mask_verde = cv2.inRange(hsv, VERDE_MIN, VERDE_MAX)
        mask_amarillo = cv2.inRange(hsv, AMARILLO_MIN, AMARILLO_MAX)
        mask_rojo1 = cv2.inRange(hsv, ROJO_MIN1, ROJO_MAX1)
        mask_rojo2 = cv2.inRange(hsv, ROJO_MIN2, ROJO_MAX2)

        mask_hp = cv2.bitwise_or(mask_verde, mask_amarillo)
        mask_hp = cv2.bitwise_or(mask_hp, mask_rojo1)
        mask_hp = cv2.bitwise_or(mask_hp, mask_rojo2)

        # Máscara para Mana (azul)
        mask_mp = cv2.inRange(hsv, AZUL_MIN, AZUL_MAX)

        # Guardar para debug
        self.last_mask_hp = mask_hp.copy()
        self.last_mask_mp = mask_mp.copy()

        # Calcular porcentajes
        expected_full_width = w * self.expected_full_width_ratio

        hp_pct = self._calculate_bar_percent(mask_hp, expected_full_width)
        mp_pct = self._calculate_bar_percent(mask_mp, expected_full_width)

        return hp_pct, mp_pct

    def get_hp_color_name(self, hp_pct: Optional[float]) -> str:
        """Retorna el nombre del color de la barra de HP según el porcentaje."""
        if hp_pct is None:
            return "N/A"
        if hp_pct > 0.60:
            return "VERDE"
        elif hp_pct > 0.30:
            return "AMARILLO"
        else:
            return "ROJO"

    def auto_calibrate(self, img: np.ndarray) -> Dict:
        """
        Escanea la franja superior y encuentra automáticamente
        la posición (fila Y) de las barras de HP y Mana.

        Retorna: dict con hp_row, mp_row, bar_max_width.
        """
        if img is None or img.size == 0:
            return {"hp_row": None, "mp_row": None, "bar_max_width": 0}

        h, w = img.shape[:2]
        scan_h = int(h * 0.15)
        region = img[0:scan_h, :]
        hsv = cv2.cvtColor(region, cv2.COLOR_BGR2HSV)

        results = {"hp_row": None, "mp_row": None, "bar_max_width": 0}

        for y in range(scan_h):
            row_hsv = hsv[y : y + 1, :]

            # Contar píxeles de cada color
            green_px = cv2.countNonZero(
                cv2.inRange(row_hsv, VERDE_MIN, VERDE_MAX)
            )
            yellow_px = cv2.countNonZero(
                cv2.inRange(row_hsv, AMARILLO_MIN, AMARILLO_MAX)
            )
            red_px1 = cv2.countNonZero(
                cv2.inRange(row_hsv, ROJO_MIN1, ROJO_MAX1)
            )
            red_px2 = cv2.countNonZero(
                cv2.inRange(row_hsv, ROJO_MIN2, ROJO_MAX2)
            )
            blue_px = cv2.countNonZero(
                cv2.inRange(row_hsv, AZUL_MIN, AZUL_MAX)
            )

            hp_px = green_px + yellow_px + red_px1 + red_px2

            if hp_px > 30 and results["hp_row"] is None:
                results["hp_row"] = y
                results["bar_max_width"] = max(results["bar_max_width"], hp_px)

            if blue_px > 30 and results["mp_row"] is None:
                results["mp_row"] = y

        # Guardar calibración
        self.hp_row = results["hp_row"]
        self.mp_row = results["mp_row"]
        self.bar_max_width = results["bar_max_width"]
        self.calibrated = results["hp_row"] is not None

        return results

    # ------------------------------------------------------------------
    # Helpers internos
    # ------------------------------------------------------------------
    @staticmethod
    def _calculate_bar_percent(
        mask: np.ndarray, expected_full_width: float
    ) -> Optional[float]:
        """
        Calcula qué porcentaje del ancho máximo está llena la barra,
        dado un mask binario de la región de barras.
        """
        # Contar píxeles de color en cada fila
        row_sums = np.sum(mask > 0, axis=1)

        if row_sums.max() < 8:
            return None

        # La fila con más píxeles = la barra principal
        best_row_idx = int(np.argmax(row_sums))
        best_row = mask[best_row_idx]

        # Encontrar columnas con píxeles
        nonzero_cols = np.where(best_row > 0)[0]
        if len(nonzero_cols) < 5:
            return None

        # Encontrar el bloque continuo más largo
        bar_length = BarDetector._find_longest_continuous_block(
            nonzero_cols, gap_tolerance=3
        )

        # Calcular porcentaje
        percent = min(bar_length / expected_full_width, 1.0)
        return round(percent, 3)

    @staticmethod
    def _find_longest_continuous_block(
        indices: np.ndarray, gap_tolerance: int = 3
    ) -> int:
        """Encuentra el bloque continuo más largo, tolerando pequeños gaps."""
        if len(indices) == 0:
            return 0
        best = curr = 1
        for i in range(1, len(indices)):
            if indices[i] - indices[i - 1] <= gap_tolerance:
                curr += 1
            else:
                best = max(best, curr)
                curr = 1
        return max(best, curr)

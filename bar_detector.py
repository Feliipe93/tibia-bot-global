"""
bar_detector.py - Detección de barras de HP y Mana usando OpenCV HSV.
Detecta dinámicamente el ancho de las barras sin depender de un ratio fijo.
Funciona correctamente sin importar cuántos paneles tenga abiertos el usuario.
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

# Fondo oscuro de las barras (gris/negro de la parte vacía)
BAR_BG_MAX_VALUE = 60       # V < 60 = píxel oscuro
BAR_BG_MAX_SATURATION = 80  # S < 80 = poco saturado


class BarDetector:
    """Detecta porcentajes de HP y Mana a partir de capturas del proyector OBS."""

    def __init__(
        self,
        expected_full_width_ratio: float = 0.43,
        scan_height_ratio: float = 0.10,
    ):
        # Ratio solo como fallback — preferimos detección dinámica
        self.expected_full_width_ratio = expected_full_width_ratio
        self.scan_height_ratio = scan_height_ratio

        # Datos de calibración dinámica
        self.calibrated = False
        self.hp_row: Optional[int] = None
        self.mp_row: Optional[int] = None
        self.hp_bar_x1: int = 0
        self.hp_bar_x2: int = 0
        self.mp_bar_x1: int = 0
        self.mp_bar_x2: int = 0
        self.bar_max_width: int = 0

        # Últimas máscaras (para debug visual)
        self.last_mask_hp: Optional[np.ndarray] = None
        self.last_mask_mp: Optional[np.ndarray] = None
        self.last_region: Optional[np.ndarray] = None
        self.last_scan_height: int = 0

        # Re-calibración periódica
        self._frame_count: int = 0
        self._recalib_interval: int = 50

    def detect(self, img: np.ndarray) -> Tuple[Optional[float], Optional[float]]:
        """
        Detecta el porcentaje de HP y Mana de la imagen capturada.

        Args:
            img: Imagen BGR del proyector OBS.

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

        # Re-calibrar periódicamente para adaptarse a cambios de paneles
        self._frame_count += 1
        if not self.calibrated or self._frame_count % self._recalib_interval == 0:
            self._calibrate_bar_positions(hsv, w, scan_height)

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

        # Calcular porcentajes usando posiciones calibradas
        if self.calibrated and self.hp_bar_x2 > self.hp_bar_x1:
            hp_pct = self._calc_percent_calibrated(
                mask_hp, self.hp_row, self.hp_bar_x1, self.hp_bar_x2
            )
        else:
            expected_full_width = w * self.expected_full_width_ratio
            hp_pct = self._calculate_bar_percent(mask_hp, expected_full_width)

        if self.calibrated and self.mp_bar_x2 > self.mp_bar_x1:
            mp_pct = self._calc_percent_calibrated(
                mask_mp, self.mp_row, self.mp_bar_x1, self.mp_bar_x2
            )
        else:
            expected_full_width = w * self.expected_full_width_ratio
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

    # ------------------------------------------------------------------
    # Calibración dinámica de barras
    # ------------------------------------------------------------------
    def _calibrate_bar_positions(self, hsv: np.ndarray, frame_w: int, scan_h: int):
        """
        Encuentra dinámicamente la posición y ancho real de las barras HP y MP.

        Estrategia:
        1. Buscar la fila con más píxeles de color HP/MP
        2. En esa fila, encontrar dónde empieza y termina el color
        3. Expandir buscando el fondo oscuro de la barra (parte vacía)
        4. Color + fondo oscuro adyacente = 100% del contenedor
        """
        hp_row = None
        mp_row = None
        hp_max_px = 0
        mp_max_px = 0

        for y in range(scan_h):
            row_hsv = hsv[y:y+1, :]

            g = cv2.countNonZero(cv2.inRange(row_hsv, VERDE_MIN, VERDE_MAX))
            a = cv2.countNonZero(cv2.inRange(row_hsv, AMARILLO_MIN, AMARILLO_MAX))
            r1 = cv2.countNonZero(cv2.inRange(row_hsv, ROJO_MIN1, ROJO_MAX1))
            r2 = cv2.countNonZero(cv2.inRange(row_hsv, ROJO_MIN2, ROJO_MAX2))
            hp_px = g + a + r1 + r2

            b = cv2.countNonZero(cv2.inRange(row_hsv, AZUL_MIN, AZUL_MAX))

            if hp_px > hp_max_px and hp_px > 20:
                hp_max_px = hp_px
                hp_row = y

            if b > mp_max_px and b > 20:
                mp_max_px = b
                mp_row = y

        if hp_row is None:
            self.calibrated = False
            return

        self.hp_row = hp_row
        self.mp_row = mp_row

        # Encontrar límites exactos de la barra HP
        hp_x1, hp_x2 = self._find_bar_extent(hsv, hp_row, frame_w, "hp")
        if hp_x2 > hp_x1:
            self.hp_bar_x1 = hp_x1
            self.hp_bar_x2 = hp_x2

        # Encontrar límites exactos de la barra MP
        if mp_row is not None:
            mp_x1, mp_x2 = self._find_bar_extent(hsv, mp_row, frame_w, "mp")
            if mp_x2 > mp_x1:
                self.mp_bar_x1 = mp_x1
                self.mp_bar_x2 = mp_x2

        self.bar_max_width = max(
            self.hp_bar_x2 - self.hp_bar_x1,
            self.mp_bar_x2 - self.mp_bar_x1
        )
        self.calibrated = True

    def _find_bar_extent(
        self, hsv: np.ndarray, row: int, frame_w: int, bar_type: str = "hp"
    ) -> Tuple[int, int]:
        """
        Encuentra el inicio y fin del CONTENEDOR COMPLETO de la barra.

        En Tibia, las barras tienen:
        - Parte con color (vida/mana actual)
        - Parte con fondo gris oscuro (la parte vacía)
        - Ambas juntas = contenedor total

        Returns:
            (x_start, x_end) del contenedor completo
        """
        row_hsv = hsv[row:row+1, :].copy()
        v_ch = row_hsv[0, :, 2]  # Value
        s_ch = row_hsv[0, :, 1]  # Saturation

        # Paso 1: Máscara de color para esta fila
        if bar_type == "hp":
            m1 = cv2.inRange(row_hsv, VERDE_MIN, VERDE_MAX)
            m2 = cv2.inRange(row_hsv, AMARILLO_MIN, AMARILLO_MAX)
            m3 = cv2.inRange(row_hsv, ROJO_MIN1, ROJO_MAX1)
            m4 = cv2.inRange(row_hsv, ROJO_MIN2, ROJO_MAX2)
            color_mask = cv2.bitwise_or(m1, m2)
            color_mask = cv2.bitwise_or(color_mask, m3)
            color_mask = cv2.bitwise_or(color_mask, m4)
        else:
            color_mask = cv2.inRange(row_hsv, AZUL_MIN, AZUL_MAX)

        color_cols = np.where(color_mask[0] > 0)[0]
        if len(color_cols) < 5:
            return 0, 0

        # Paso 2: Bloque continuo de color más largo
        color_start, color_end = self._find_longest_block_range(
            color_cols, gap_tolerance=3
        )

        # Paso 3: Expandir a DERECHA buscando fondo oscuro de barra
        bar_end = color_end
        for x in range(color_end + 1, min(frame_w, color_end + 500)):
            v = int(v_ch[x])
            s = int(s_ch[x])
            # Fondo de barra: oscuro (V<60) poco saturado (S<80) pero no negro puro (V>3)
            if 3 < v < BAR_BG_MAX_VALUE and s < BAR_BG_MAX_SATURATION:
                bar_end = x
            else:
                break

        # Paso 4: Expandir a IZQUIERDA
        bar_start = color_start
        for x in range(color_start - 1, max(-1, color_start - 500), -1):
            v = int(v_ch[x])
            s = int(s_ch[x])
            if 3 < v < BAR_BG_MAX_VALUE and s < BAR_BG_MAX_SATURATION:
                bar_start = x
            else:
                break

        # La barra debe tener al menos 30 píxeles
        if bar_end - bar_start < 30:
            return color_start, color_end

        return bar_start, bar_end

    @staticmethod
    def _find_longest_block_range(
        indices: np.ndarray, gap_tolerance: int = 3
    ) -> Tuple[int, int]:
        """Encuentra inicio y fin del bloque continuo más largo."""
        if len(indices) == 0:
            return 0, 0

        best_start = curr_start = indices[0]
        best_end = curr_end = indices[0]
        best_len = 1
        curr_len = 1

        for i in range(1, len(indices)):
            if indices[i] - indices[i - 1] <= gap_tolerance:
                curr_end = indices[i]
                curr_len += 1
            else:
                if curr_len > best_len:
                    best_len = curr_len
                    best_start = curr_start
                    best_end = curr_end
                curr_start = indices[i]
                curr_end = indices[i]
                curr_len = 1

        if curr_len > best_len:
            best_start = curr_start
            best_end = curr_end

        return int(best_start), int(best_end)

    @staticmethod
    def _calc_percent_calibrated(
        mask: np.ndarray, row: Optional[int], bar_x1: int, bar_x2: int
    ) -> Optional[float]:
        """
        Calcula el porcentaje usando posiciones calibradas.
        Mide píxeles de color dentro del contenedor de la barra.
        """
        if row is None or bar_x2 <= bar_x1:
            return None

        total_width = bar_x2 - bar_x1
        if total_width < 10:
            return None

        # Buscar la mejor fila ±2 alrededor de la calibrada
        h = mask.shape[0]
        best_count = 0
        for dy in range(-2, 3):
            y = row + dy
            if 0 <= y < h:
                bar_section = mask[y, bar_x1:bar_x2]
                count = np.count_nonzero(bar_section)
                best_count = max(best_count, count)

        if best_count < 3:
            return None

        percent = min(best_count / total_width, 1.0)
        return round(percent, 3)

    def auto_calibrate(self, img: np.ndarray) -> Dict:
        """
        Escanea la franja superior y calibra posiciones de barras.
        """
        if img is None or img.size == 0:
            return {"hp_row": None, "mp_row": None, "bar_max_width": 0}

        h, w = img.shape[:2]
        scan_h = int(h * 0.15)
        region = img[0:scan_h, :]
        hsv = cv2.cvtColor(region, cv2.COLOR_BGR2HSV)

        self._calibrate_bar_positions(hsv, w, scan_h)

        return {
            "hp_row": self.hp_row,
            "mp_row": self.mp_row,
            "bar_max_width": self.bar_max_width,
            "hp_bar": (self.hp_bar_x1, self.hp_bar_x2),
            "mp_bar": (self.mp_bar_x1, self.mp_bar_x2),
        }

    # ------------------------------------------------------------------
    # Método fallback (original con ratio fijo)
    # ------------------------------------------------------------------
    @staticmethod
    def _calculate_bar_percent(
        mask: np.ndarray, expected_full_width: float
    ) -> Optional[float]:
        """Calcula porcentaje usando ratio fijo (fallback)."""
        row_sums = np.sum(mask > 0, axis=1)

        if row_sums.max() < 8:
            return None

        best_row_idx = int(np.argmax(row_sums))
        best_row = mask[best_row_idx]

        nonzero_cols = np.where(best_row > 0)[0]
        if len(nonzero_cols) < 5:
            return None

        bar_length = BarDetector._find_longest_continuous_block(
            nonzero_cols, gap_tolerance=3
        )

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

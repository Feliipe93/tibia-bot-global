"""
looter/corpse_detector.py - Detector de cadáveres en el game window.
Detecta cuerpos de monstruos muertos usando análisis de color
y posición relativa a los últimos monstruos atacados.
"""

import time
import numpy as np
import cv2
from typing import Dict, List, Optional, Tuple


class Corpse:
    """Representa un cadáver detectado."""

    def __init__(
        self,
        screen_x: int = 0,
        screen_y: int = 0,
        tile_x: int = 0,
        tile_y: int = 0,
        confidence: float = 0.0,
        timestamp: float = 0.0,
        looted: bool = False,
    ):
        self.screen_x = screen_x
        self.screen_y = screen_y
        self.tile_x = tile_x
        self.tile_y = tile_y
        self.confidence = confidence
        self.timestamp = timestamp or time.time()
        self.looted = looted
        self.loot_attempts: int = 0

    @property
    def age(self) -> float:
        """Edad del cadáver en segundos."""
        return time.time() - self.timestamp

    @property
    def center(self) -> Tuple[int, int]:
        return (self.screen_x, self.screen_y)

    def to_dict(self) -> Dict:
        return {
            "screen_x": self.screen_x,
            "screen_y": self.screen_y,
            "tile_x": self.tile_x,
            "tile_y": self.tile_y,
            "confidence": round(self.confidence, 2),
            "age": round(self.age, 1),
            "looted": self.looted,
            "attempts": self.loot_attempts,
        }

    def __repr__(self) -> str:
        status = "✓" if self.looted else "○"
        return f"<Corpse ({self.screen_x},{self.screen_y}) {status} age={self.age:.0f}s>"


class CorpseDetector:
    """
    Detecta cadáveres de monstruos en el game window.
    Métodos de detección:
    1. Posiciones donde murieron monstruos (tracking de kills)
    2. Análisis visual de cambios en tiles
    3. Detección de cadáveres por color/textura típica
    """

    # Colores típicos de cadáveres en Tibia (BGR)
    # La mayoría son marrones/grises oscuros
    CORPSE_HSV_RANGES = [
        # Marrón oscuro (cadáveres genéricos)
        {"lower": np.array([8, 50, 30]), "upper": np.array([25, 200, 120])},
        # Gris (huesos, esqueletos)
        {"lower": np.array([0, 0, 80]), "upper": np.array([180, 30, 160])},
    ]

    def __init__(self):
        # Región del game window
        self.game_region: Optional[Tuple[int, int, int, int]] = None

        # Cola de cadáveres pendientes
        self._corpse_queue: List[Corpse] = []

        # Historial de posiciones de kills
        self._kill_positions: List[Tuple[int, int, float]] = []  # (x, y, timestamp)

        # Configuración
        self.max_corpse_age: float = 15.0      # Segundos antes de ignorar un cadáver
        self.max_loot_attempts: int = 3         # Intentos máximos por cadáver
        self.detection_cooldown: float = 0.5    # Cooldown entre detecciones
        self.last_detection_time: float = 0.0

        # Tile size para conversiones
        self.tile_size: int = 32

    def set_game_region(self, x: int, y: int, w: int, h: int) -> None:
        self.game_region = (x, y, w, h)

    # ==================================================================
    # Registro de kills
    # ==================================================================
    def register_kill(self, screen_x: int, screen_y: int) -> None:
        """
        Registra la posición donde murió un monstruo.
        Se llama cuando el targeting detecta una kill.
        """
        corpse = Corpse(
            screen_x=screen_x,
            screen_y=screen_y,
            confidence=1.0,
            timestamp=time.time(),
        )

        # Calcular tile relativo
        if self.game_region:
            gx, gy, gw, gh = self.game_region
            corpse.tile_x = (screen_x - gx) // self.tile_size
            corpse.tile_y = (screen_y - gy) // self.tile_size

        self._corpse_queue.append(corpse)
        self._kill_positions.append((screen_x, screen_y, time.time()))

    def register_kill_at_tile(self, tile_x: int, tile_y: int) -> None:
        """Registra un kill por posición de tile."""
        if self.game_region is None:
            return
        gx, gy, gw, gh = self.game_region
        screen_x = gx + tile_x * self.tile_size + self.tile_size // 2
        screen_y = gy + tile_y * self.tile_size + self.tile_size // 2
        self.register_kill(screen_x, screen_y)

    # ==================================================================
    # Detección visual
    # ==================================================================
    def detect(self, frame: np.ndarray) -> List[Corpse]:
        """
        Detecta cadáveres en el frame actual.
        Combina kills registrados con detección visual.

        Returns:
            Lista de cadáveres pendientes de lootear.
        """
        now = time.time()

        # Cooldown de detección
        if now - self.last_detection_time < self.detection_cooldown:
            return self.pending_corpses

        self.last_detection_time = now

        # Limpiar cadáveres viejos o ya looteados
        self._cleanup()

        return self.pending_corpses

    def detect_visual(self, frame: np.ndarray) -> List[Corpse]:
        """
        Detección visual de cadáveres en el game window.
        Busca áreas con colores típicos de cadáveres.
        """
        if self.game_region is None or frame is None:
            return []

        gx, gy, gw, gh = self.game_region
        roi = frame[gy:gy + gh, gx:gx + gw]
        if roi.size == 0:
            return []

        hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
        detected = []

        combined_mask = np.zeros(roi.shape[:2], dtype=np.uint8)
        for hsv_range in self.CORPSE_HSV_RANGES:
            mask = cv2.inRange(hsv, hsv_range["lower"], hsv_range["upper"])
            combined_mask = cv2.bitwise_or(combined_mask, mask)

        # Filtrar ruido
        kernel = np.ones((3, 3), np.uint8)
        combined_mask = cv2.morphologyEx(combined_mask, cv2.MORPH_OPEN, kernel)
        combined_mask = cv2.morphologyEx(combined_mask, cv2.MORPH_CLOSE, kernel)

        # Buscar contornos de tamaño apropiado
        contours, _ = cv2.findContours(
            combined_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )

        for cnt in contours:
            area = cv2.contourArea(cnt)
            # Filtrar por tamaño (un cadáver ocupa aproximadamente 1 tile)
            min_area = (self.tile_size * 0.3) ** 2
            max_area = (self.tile_size * 2) ** 2

            if area < min_area or area > max_area:
                continue

            bx, by, bw, bh = cv2.boundingRect(cnt)
            center_x = gx + bx + bw // 2
            center_y = gy + by + bh // 2

            # Verificar que no es un cadáver ya registrado
            if self._is_near_existing(center_x, center_y):
                continue

            confidence = min(1.0, area / max_area)
            corpse = Corpse(
                screen_x=center_x,
                screen_y=center_y,
                tile_x=bx // self.tile_size,
                tile_y=by // self.tile_size,
                confidence=confidence,
            )
            detected.append(corpse)

        return detected

    # ==================================================================
    # Gestión de cola
    # ==================================================================
    def get_next_corpse(self) -> Optional[Corpse]:
        """
        Retorna el siguiente cadáver a lootear.
        Prioriza por: cercanía, confianza, edad.
        """
        pending = self.pending_corpses
        if not pending:
            return None

        # Priorizar el más reciente y de mayor confianza
        pending.sort(key=lambda c: (-c.confidence, c.age))
        return pending[0]

    def mark_looted(self, corpse: Corpse) -> None:
        """Marca un cadáver como looteado."""
        corpse.looted = True

    def mark_attempt(self, corpse: Corpse) -> None:
        """Registra un intento de looteo."""
        corpse.loot_attempts += 1
        if corpse.loot_attempts >= self.max_loot_attempts:
            corpse.looted = True  # Desistir tras muchos intentos

    @property
    def pending_corpses(self) -> List[Corpse]:
        """Lista de cadáveres pendientes de lootear."""
        return [
            c for c in self._corpse_queue
            if not c.looted and c.age < self.max_corpse_age
        ]

    @property
    def pending_count(self) -> int:
        return len(self.pending_corpses)

    def _cleanup(self) -> None:
        """Limpia cadáveres viejos y looteados."""
        self._corpse_queue = [
            c for c in self._corpse_queue
            if not c.looted and c.age < self.max_corpse_age * 2
        ]

        # Limpiar kill positions viejas
        cutoff = time.time() - self.max_corpse_age * 2
        self._kill_positions = [
            (x, y, t) for x, y, t in self._kill_positions if t > cutoff
        ]

    def _is_near_existing(self, x: int, y: int, threshold: int = 20) -> bool:
        """Verifica si hay un cadáver ya registrado cerca de esta posición."""
        for c in self._corpse_queue:
            if abs(c.screen_x - x) < threshold and abs(c.screen_y - y) < threshold:
                return True
        return False

    def clear(self) -> None:
        """Limpia toda la cola."""
        self._corpse_queue.clear()
        self._kill_positions.clear()

    # ==================================================================
    # Debug
    # ==================================================================
    def draw_debug(self, frame: np.ndarray) -> np.ndarray:
        """Dibuja cadáveres detectados sobre el frame."""
        debug = frame.copy()
        for c in self._corpse_queue:
            if c.looted:
                color = (100, 100, 100)  # Gris si ya looteado
            else:
                color = (0, 255, 255)  # Amarillo si pendiente

            cv2.circle(debug, (c.screen_x, c.screen_y), 15, color, 2)
            label = f"C:{c.confidence:.1f} A:{c.age:.0f}s"
            cv2.putText(debug, label, (c.screen_x - 30, c.screen_y - 18),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.35, color, 1)

        return debug

"""
logger.py - Sistema de logging con rotación diaria y handler para GUI.
"""

import logging
import os
from datetime import datetime
from logging.handlers import TimedRotatingFileHandler
from typing import Callable, Optional, List

LOG_DIR = "logs"


class GUILogHandler(logging.Handler):
    """
    Handler personalizado que redirige los mensajes de log a un callback
    para mostrarlos en la interfaz gráfica.
    """

    def __init__(self, callback: Optional[Callable[[str, str], None]] = None):
        super().__init__()
        self.callback = callback
        self.buffer: List[str] = []
        self.max_buffer = 5000

    def set_callback(self, callback: Callable[[str, str], None]) -> None:
        """Establece el callback para enviar logs a la GUI."""
        self.callback = callback
        # Enviar los mensajes del buffer
        for record_text, level in self.buffer:
            try:
                self.callback(record_text, level)
            except Exception:
                pass

    def emit(self, record: logging.LogRecord) -> None:
        try:
            msg = self.format(record)
            level = record.levelname
            if self.callback:
                self.callback(msg, level)
            else:
                self.buffer.append((msg, level))
                if len(self.buffer) > self.max_buffer:
                    self.buffer = self.buffer[-self.max_buffer:]
        except Exception:
            self.handleError(record)


class BotLogger:
    """Configura y gestiona el sistema de logs del bot."""

    EMOJIS = {
        "DEBUG": "🔍",
        "INFO": "📊",
        "WARNING": "⚠️",
        "ERROR": "❌",
        "CRITICAL": "💀",
        "HEAL": "💊",
        "OK": "✅",
    }

    def __init__(self, name: str = "TibiaHealer", level: str = "INFO"):
        os.makedirs(LOG_DIR, exist_ok=True)

        self.logger = logging.getLogger(name)
        self.logger.setLevel(logging.DEBUG)  # capturar todo, filtrar en handlers
        self.logger.handlers.clear()

        # Formato
        fmt = "[%(asctime)s] %(levelname)-8s %(message)s"
        date_fmt = "%H:%M:%S"
        formatter = logging.Formatter(fmt, datefmt=date_fmt)

        # Handler: archivo con rotación diaria
        today = datetime.now().strftime("%Y%m%d")
        log_file = os.path.join(LOG_DIR, f"tibia_healer_{today}.log")
        file_handler = TimedRotatingFileHandler(
            log_file,
            when="midnight",
            interval=1,
            backupCount=30,
            encoding="utf-8",
        )
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(formatter)
        self.logger.addHandler(file_handler)

        # Handler: consola
        console_handler = logging.StreamHandler()
        console_handler.setLevel(getattr(logging, level.upper(), logging.INFO))
        console_handler.setFormatter(formatter)
        self.logger.addHandler(console_handler)

        # Handler: GUI
        self.gui_handler = GUILogHandler()
        self.gui_handler.setLevel(getattr(logging, level.upper(), logging.INFO))
        self.gui_handler.setFormatter(formatter)
        self.logger.addHandler(self.gui_handler)

        self._file_handler = file_handler
        self._console_handler = console_handler

    def set_level(self, level: str) -> None:
        """Cambia el nivel de log en tiempo real."""
        lvl = getattr(logging, level.upper(), logging.INFO)
        self._console_handler.setLevel(lvl)
        self.gui_handler.setLevel(lvl)

    def set_gui_callback(self, callback: Callable[[str, str], None]) -> None:
        """Conecta el handler GUI con la interfaz gráfica."""
        self.gui_handler.set_callback(callback)

    # ------------------------------------------------------------------
    # Métodos de logging con emojis
    # ------------------------------------------------------------------
    def debug(self, msg: str) -> None:
        self.logger.debug(f"{self.EMOJIS['DEBUG']} {msg}")

    def info(self, msg: str) -> None:
        self.logger.info(f"{self.EMOJIS['INFO']} {msg}")

    def warning(self, msg: str) -> None:
        self.logger.warning(f"{self.EMOJIS['WARNING']} {msg}")

    def error(self, msg: str) -> None:
        self.logger.error(f"{self.EMOJIS['ERROR']} {msg}")

    def critical(self, msg: str) -> None:
        self.logger.critical(f"{self.EMOJIS['CRITICAL']} {msg}")

    def heal(self, msg: str) -> None:
        """Log especial para eventos de curación."""
        self.logger.info(f"{self.EMOJIS['HEAL']} {msg}")

    def ok(self, msg: str) -> None:
        """Log especial para confirmaciones exitosas."""
        self.logger.info(f"{self.EMOJIS['OK']} {msg}")

    # ------------------------------------------------------------------
    # Utilidades
    # ------------------------------------------------------------------
    def get_log_file_path(self) -> str:
        """Retorna la ruta del archivo de log actual."""
        today = datetime.now().strftime("%Y%m%d")
        return os.path.join(LOG_DIR, f"tibia_healer_{today}.log")

    def save_current_log(self, dest_path: str) -> bool:
        """Copia el log actual a una ruta especificada."""
        import shutil
        try:
            src = self.get_log_file_path()
            if os.path.exists(src):
                shutil.copy2(src, dest_path)
                return True
        except Exception as e:
            self.error(f"Error guardando log: {e}")
        return False

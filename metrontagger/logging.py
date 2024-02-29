"""Logging module"""

import logging
from logging import basicConfig

from metrontagger.settings import MetronTaggerSettings

DATE_FMT = "%Y-%m-%d %H:%M:%S %Z"
LOG_FMT = "{asctime} {levelname:8} {message}"


def init_logging(config: MetronTaggerSettings) -> None:
    """Initializing logging"""
    formatter = logging.Formatter(LOG_FMT, style="{", datefmt=DATE_FMT)
    log_path = config.get_settings_folder() / "metron-tagger.log"
    handler = logging.FileHandler(str(log_path))
    handler.setFormatter(formatter)
    basicConfig(level=logging.WARNING, handlers=[handler])

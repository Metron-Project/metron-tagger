"""Projects version information used in setup.py."""

__all__ = ["__version__", "init_logging"]

import logging
from contextlib import suppress
from importlib.metadata import version
from logging import basicConfig

from metrontagger.utils import get_settings_folder

__version__ = version("metron-tagger")

# Registers a JPEG XL decoder with Pillow when the optional `jxl` extra is installed,
# so .jxl comic pages can be cover-hashed and duplicate-checked like any other image.
with suppress(ImportError):
    import pillow_jxl  # noqa: F401

DATE_FMT = "%Y-%m-%d %H:%M:%S %Z"
LOG_FMT = "{asctime} {levelname:8} {message}"


def init_logging() -> None:
    """Set up file logging.

    Configure a file handler to log messages to a file specified in the settings.
    The log file will be located in the settings folder and named "bekka.log".
    Messages will be formatted according to DATE_FMT and LOG_FMT, and the logging
    level is set to WARNING.
    """
    formatter = logging.Formatter(LOG_FMT, style="{", datefmt=DATE_FMT)
    log_path = get_settings_folder() / "metron-tagger.log"
    handler = logging.FileHandler(str(log_path))
    handler.setFormatter(formatter)
    basicConfig(level=logging.WARNING, handlers=[handler])

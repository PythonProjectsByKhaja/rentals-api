"""Logging setup, kept out of ``main.py``."""

from __future__ import annotations

import logging
from logging.config import dictConfig


def configure_logging(*, debug: bool = False) -> None:
    """Install a single console handler with a consistent format.

    Uvicorn installs its own handlers; ``propagate: False`` on its loggers stops
    every request line being emitted twice.
    """
    level = logging.DEBUG if debug else logging.INFO

    dictConfig(
        {
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {
                "default": {
                    "format": "%(asctime)s %(levelname)-8s %(name)s: %(message)s",
                    "datefmt": "%Y-%m-%d %H:%M:%S",
                },
            },
            "handlers": {
                "console": {
                    "class": "logging.StreamHandler",
                    "formatter": "default",
                    "stream": "ext://sys.stdout",
                },
            },
            "root": {"handlers": ["console"], "level": level},
            "loggers": {
                "uvicorn": {"handlers": ["console"], "level": level, "propagate": False},
                "uvicorn.error": {"handlers": ["console"], "level": level, "propagate": False},
                "uvicorn.access": {"handlers": ["console"], "level": level, "propagate": False},
                # SQLAlchemy echoes statements at INFO; that is noisy outside debug.
                "sqlalchemy.engine": {"level": logging.INFO if debug else logging.WARNING},
            },
        }
    )

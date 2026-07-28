from __future__ import annotations

import logging
import sys
from typing import TextIO


class LoggerFactory:
    @staticmethod
    def create_logger(
        name: str = "sdmas",
        level: str = "INFO",
        stream: TextIO | None = None,
    ) -> logging.Logger:
        logger = logging.getLogger(name)

        if logger.handlers:
            return logger

        parsed_level = getattr(logging, level.upper(), logging.INFO)
        logger.setLevel(parsed_level)

        handler = logging.StreamHandler(stream or sys.stdout)
        handler.setLevel(parsed_level)

        formatter = logging.Formatter(
            fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        handler.setFormatter(formatter)

        logger.addHandler(handler)
        return logger


def get_logger(name: str = "sdmas") -> logging.Logger:
    return logging.getLogger(name)

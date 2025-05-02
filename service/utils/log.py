import logging
import os
from typing import Dict


class LoggerSingleton:
    _instance = None
    _loggers: Dict[str, logging.Logger] = {}

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(LoggerSingleton, cls).__new__(cls)
            cls._instance._configure_root_logger()
        return cls._instance

    @staticmethod
    def _configure_root_logger():
        log_levels = {
            "DEBUG": logging.DEBUG,
            "INFO": logging.INFO,
            "WARNING": logging.WARNING,
            "ERROR": logging.ERROR,
            "CRITICAL": logging.CRITICAL
        }

        log_level = log_levels.get(os.getenv("LOG_LEVEL"), logging.INFO)
        log_format = os.getenv("LOG_FORMAT", "%(asctime)s [%(levelname)s] [%(name)s] - %(message)s")

        logging.basicConfig(
            level=log_level,
            format=log_format
        )

    def get_logger(self, name: str) -> logging.Logger:
        if name not in self._loggers:
            logger = logging.getLogger(name)
            self._loggers[name] = logger
        return self._loggers[name]


def get_logger(name: str) -> logging.Logger:
    return LoggerSingleton().get_logger(name)

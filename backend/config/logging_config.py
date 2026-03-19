"""
Nexus Civilization Engine - Structured Logging
"""
import logging
import logging.handlers
import json
import sys
import os
from datetime import datetime, timezone
from typing import Any
from pathlib import Path


class JSONFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)
        if hasattr(record, "extra"):
            log_entry.update(record.extra)
        return json.dumps(log_entry)


class SimulationEventLogger:
    """Dedicated logger for simulation events - JSONL format for analytics."""

    def __init__(self, filepath: str):
        Path(filepath).parent.mkdir(parents=True, exist_ok=True)
        self._filepath = filepath

    def log_event(self, event_type: str, tick: int, data: dict[str, Any]) -> None:
        entry = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "tick": tick,
            "event": event_type,
            **data,
        }
        with open(self._filepath, "a") as f:
            f.write(json.dumps(entry) + "\n")


def setup_logging(level: str = "INFO", json_format: bool = True, log_dir: str = "logs") -> None:
    Path(log_dir).mkdir(parents=True, exist_ok=True)

    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, level.upper(), logging.INFO))

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    if json_format:
        console_handler.setFormatter(JSONFormatter())
    else:
        console_handler.setFormatter(
            logging.Formatter("%(asctime)s | %(levelname)-8s | %(name)s | %(message)s")
        )
    root_logger.addHandler(console_handler)

    # File handler with rotation
    file_handler = logging.handlers.RotatingFileHandler(
        os.path.join(log_dir, "nce.log"),
        maxBytes=100 * 1024 * 1024,
        backupCount=5,
    )
    file_handler.setFormatter(JSONFormatter())
    root_logger.addHandler(file_handler)

    # Suppress noisy third-party loggers
    for noisy in ["uvicorn.access", "sqlalchemy.engine"]:
        logging.getLogger(noisy).setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)

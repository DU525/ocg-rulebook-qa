"""
Structured logging configuration for OCG Rulebook QA backend.

Features:
- JSON format logs with timestamp, level, message, trace_id, latency, module, function, line
- Rotating file handlers with configurable max size and backup count
- Module-based log separation (api.log, services.log, core.log)
- Sensitive data filtering (passwords, tokens are automatically redacted)
"""

import os
import re
import json
import logging
import threading
from datetime import datetime, timezone
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any, Dict, Optional


LOG_DIR = Path(__file__).resolve().parent.parent.parent / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)

SENSITIVE_PATTERNS = [
    re.compile(r"(bearer\s+)[A-Za-z0-9\-._~+/]+=*", re.IGNORECASE),
    re.compile(r"(authorization[\"']?\s*[:=]\s*[\"']?)[^\s\"'}&]+", re.IGNORECASE),
    re.compile(r"(password[\"']?\s*[:=]\s*[\"']?)[^\s\"'}&]+", re.IGNORECASE),
    re.compile(r"(token[\"']?\s*[:=]\s*[\"']?)[^\s\"'}&]+", re.IGNORECASE),
    re.compile(r"(api_key[\"']?\s*[:=]\s*[\"']?)[^\s\"'}&]+", re.IGNORECASE),
    re.compile(r"(secret[\"']?\s*[:=]\s*[\"']?)[^\s\"'}&]+", re.IGNORECASE),
]

MODULE_LOG_MAP = {
    "app.api": "api.log",
    "app.services": "services.log",
    "app.core": "core.log",
}

_log_lock = threading.Lock()
_initialized = False


def filter_sensitive(text: str) -> str:
    """Replace sensitive values in text with [REDACTED]."""
    if not text:
        return text
    result = str(text)
    for pattern in SENSITIVE_PATTERNS:
        result = pattern.sub(r"\1[REDACTED]", result)
    return result


def _get_log_file_for_module(module_name: str) -> str:
    """Determine which log file a module should write to."""
    for prefix, filename in MODULE_LOG_MAP.items():
        if module_name.startswith(prefix):
            return filename
    return "app.log"


class JSONLogFormatter(logging.Formatter):
    """JSON formatter that outputs structured log records."""

    def format(self, record: logging.LogRecord) -> str:
        log_entry: Dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "message": filter_sensitive(record.getMessage()),
            "trace_id": getattr(record, "trace_id", "") or "",
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
            "logger": record.name,
        }

        latency = getattr(record, "latency", None)
        if latency is not None:
            log_entry["latency"] = latency

        if record.exc_info and record.exc_info[0] is not None:
            log_entry["exception"] = self.formatException(record.exc_info)

        if hasattr(record, "extra_fields"):
            for key, value in record.extra_fields.items():
                if key not in log_entry:
                    log_entry[key] = filter_sensitive(str(value))

        return json.dumps(log_entry, ensure_ascii=False)


def get_logger(name: str) -> logging.Logger:
    """Get or create a logger with JSON formatting and rotating file handler."""
    logger = logging.getLogger(name)

    if logger.handlers:
        return logger

    logger.setLevel(logging.DEBUG)
    logger.propagate = False

    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(JSONLogFormatter())
    logger.addHandler(console_handler)

    log_filename = _get_log_file_for_module(name)
    log_file_path = LOG_DIR / log_filename

    file_handler = RotatingFileHandler(
        filename=str(log_file_path),
        maxBytes=10 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8",
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(JSONLogFormatter())
    logger.addHandler(file_handler)

    return logger


def setup_root_logging() -> None:
    """Initialize root logger with structured JSON format."""
    global _initialized
    if _initialized:
        return

    with _log_lock:
        if _initialized:
            return

        root_logger = logging.getLogger()
        root_logger.setLevel(logging.DEBUG)

        for handler in root_logger.handlers[:]:
            root_logger.removeHandler(handler)

        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(JSONLogFormatter())
        root_logger.addHandler(console_handler)

        default_log = LOG_DIR / "app.log"
        file_handler = RotatingFileHandler(
            filename=str(default_log),
            maxBytes=10 * 1024 * 1024,
            backupCount=5,
            encoding="utf-8",
        )
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(JSONLogFormatter())
        root_logger.addHandler(file_handler)

        _initialized = True

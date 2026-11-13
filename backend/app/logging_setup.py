"""Logging terstruktur ke data_dir/logs/zoi.log (rotasi) + konsol. Rahasia selalu disensor."""

from __future__ import annotations

import logging
import logging.handlers
import sys
from pathlib import Path

import structlog

from app.security.redact import structlog_redactor

_CONFIGURED_FOR: Path | None = None


class _CurrentStderrHandler(logging.StreamHandler):  # type: ignore[type-arg]
    """Selalu menulis ke sys.stderr yang aktif saat ini (aman bila stream diganti, mis. oleh test runner)."""

    @property  # type: ignore[override]
    def stream(self):  # type: ignore[no-untyped-def]
        return sys.stderr

    @stream.setter
    def stream(self, _value) -> None:  # type: ignore[no-untyped-def]
        pass


def configure_logging(log_dir: Path, level: str = "INFO") -> None:
    global _CONFIGURED_FOR
    log_dir.mkdir(parents=True, exist_ok=True)
    if _CONFIGURED_FOR == log_dir:
        return

    shared = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog_redactor,
    ]
    structlog.configure(
        processors=[*shared, structlog.stdlib.ProcessorFormatter.wrap_for_formatter],
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=False,
    )

    file_handler = logging.handlers.RotatingFileHandler(
        log_dir / "zoi.log", maxBytes=5 * 1024 * 1024, backupCount=5, encoding="utf-8"
    )
    file_handler.setFormatter(
        structlog.stdlib.ProcessorFormatter(processor=structlog.processors.JSONRenderer(ensure_ascii=False),
                                            foreign_pre_chain=shared)
    )
    console = _CurrentStderrHandler()
    console.setFormatter(
        structlog.stdlib.ProcessorFormatter(processor=structlog.dev.ConsoleRenderer(colors=False),
                                            foreign_pre_chain=shared)
    )
    root = logging.getLogger("zoi")
    for handler in list(root.handlers):
        root.removeHandler(handler)
        handler.close()
    root.addHandler(file_handler)
    root.addHandler(console)
    root.setLevel(level)
    root.propagate = False
    _CONFIGURED_FOR = log_dir


def get_logger(name: str = "zoi") -> structlog.stdlib.BoundLogger:
    return structlog.get_logger("zoi" if name == "zoi" else f"zoi.{name}")

import logging
import os
import re

def _mask(s: str) -> str:
    if not isinstance(s, str):
        return s
    s = re.sub(r"\b(\d{6})\d{3}\b", r"\1***", s)  # mask 9-digit ids/cards
    return s

class PiiFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            record.msg = _mask(record.msg)
        return True

def configure_logging():
    level = getattr(logging, os.getenv("LOG_LEVEL", "INFO").upper(), logging.INFO)
    logger = logging.getLogger()
    logger.setLevel(level)
    handler = logging.StreamHandler()
    handler.setLevel(level)
    handler.addFilter(PiiFilter())
    fmt = logging.Formatter("[%(asctime)s] %(levelname)s %(name)s: %(message)s")
    handler.setFormatter(fmt)
    logger.handlers = [handler]
    return logger

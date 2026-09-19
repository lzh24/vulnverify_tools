import json
import logging
import sys
from typing import Any, Dict


class JSONFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        # Windows strftime does not support %f
        timestamp = self.formatTime(record, "%Y-%m-%dT%H:%M:%S")
        # Manually add milliseconds if needed, or just use seconds
        # timestamp = f"{timestamp}.{int(record.msecs):03d}Z"
        
        log_data: Dict[str, Any] = {
            "timestamp": timestamp,
            "level": record.levelname,
            "message": record.getMessage(),
        }
        
        if hasattr(record, "tool_name"):
            log_data["tool_name"] = record.tool_name
        if hasattr(record, "request_id"):
            log_data["request_id"] = record.request_id
        if hasattr(record, "duration_ms"):
            log_data["duration_ms"] = record.duration_ms
        if record.exc_info:
            log_data["error"] = self.formatException(record.exc_info)
        
        return json.dumps(log_data)


def setup_logger(tool_name: str, log_level: str = "INFO") -> logging.Logger:
    logger = logging.getLogger(tool_name)
    logger.setLevel(getattr(logging, log_level.upper()))
    
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JSONFormatter())
    logger.addHandler(handler)
    
    return logger

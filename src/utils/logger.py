"""
Centralized logging system with PII anonymization.

Features:
- JSON structured logging
- Automatic PII detection and masking
- Request/response tracking with request IDs
- Performance metrics
- Compliance logging (audit trails)
- Log rotation by size and time
- Multiple handlers (console, file)
"""

import logging
import logging.handlers
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional
import uuid
from functools import wraps

from src.security.pii_masker import mask_pii, PiiType


class PiiAnonymizingFilter(logging.Filter):
    """
    Logging filter that anonymizes PII in log records.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        """
        Process log record and mask PII.

        Args:
            record: LogRecord to filter

        Returns:
            True to allow the record to be logged
        """
        # Anonymize message
        if isinstance(record.msg, str):
            masked_msg, detections = mask_pii(record.msg, strategy="redact")
            record.msg = masked_msg

        # Anonymize args if they're in the message
        if record.args:
            if isinstance(record.args, dict):
                for key, value in record.args.items():
                    if isinstance(value, str):
                        masked_value, _ = mask_pii(value, strategy="redact")
                        record.args[key] = masked_value

            elif isinstance(record.args, tuple):
                record.args = tuple(
                    mask_pii(arg, strategy="redact")[0] if isinstance(arg, str) else arg
                    for arg in record.args
                )

        # Anonymize extra fields
        for key, value in record.__dict__.items():
            if isinstance(value, str) and key not in [
                'name', 'module', 'funcName', 'levelname', 'filename', 'pathname'
            ]:
                masked_value, _ = mask_pii(value, strategy="redact")
                record.__dict__[key] = masked_value

        return True


class JsonFormatter(logging.Formatter):
    """
    JSON formatter for structured logging.
    """

    def format(self, record: logging.LogRecord) -> str:
        """
        Format log record as JSON.

        Args:
            record: LogRecord to format

        Returns:
            JSON formatted log string
        """
        log_data = {
            "timestamp": datetime.utcnow().isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
            "message": record.getMessage(),
        }

        # Add request ID if available
        if hasattr(record, "request_id"):
            log_data["request_id"] = record.request_id

        # Add user ID if available
        if hasattr(record, "user_id"):
            log_data["user_id"] = record.user_id

        # Add extra fields
        for key, value in record.__dict__.items():
            if key not in [
                'name', 'msg', 'args', 'created', 'filename', 'funcName',
                'levelname', 'levelno', 'lineno', 'module', 'msecs',
                'message', 'pathname', 'process', 'processName', 'relativeCreated',
                'thread', 'threadName', 'exc_info', 'exc_text', 'stack_info'
            ]:
                log_data[key] = value

        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_data, default=str)


class ContextualLogger:
    """
    Logger wrapper with context tracking.

    Automatically tracks:
    - Request IDs
    - User IDs
    - Performance metrics
    - Audit events
    """

    def __init__(self, name: str):
        """Initialize contextual logger."""
        self.logger = logging.getLogger(name)
        self.context: Dict[str, Any] = {}

    def set_context(self, **kwargs) -> None:
        """Set context variables (e.g., request_id, user_id)."""
        self.context.update(kwargs)

    def clear_context(self) -> None:
        """Clear context."""
        self.context.clear()

    def _log_with_context(
        self,
        level: int,
        msg: str,
        *args,
        **kwargs
    ) -> None:
        """Log with context."""
        # Merge context into extra
        extra = kwargs.get("extra", {})
        extra.update(self.context)
        kwargs["extra"] = extra

        self.logger.log(level, msg, *args, **kwargs)

    def debug(self, msg: str, *args, **kwargs) -> None:
        """Log debug message."""
        self._log_with_context(logging.DEBUG, msg, *args, **kwargs)

    def info(self, msg: str, *args, **kwargs) -> None:
        """Log info message."""
        self._log_with_context(logging.INFO, msg, *args, **kwargs)

    def warning(self, msg: str, *args, **kwargs) -> None:
        """Log warning message."""
        self._log_with_context(logging.WARNING, msg, *args, **kwargs)

    def error(self, msg: str, *args, **kwargs) -> None:
        """Log error message."""
        self._log_with_context(logging.ERROR, msg, *args, **kwargs)

    def critical(self, msg: str, *args, **kwargs) -> None:
        """Log critical message."""
        self._log_with_context(logging.CRITICAL, msg, *args, **kwargs)

    def audit(
        self,
        event: str,
        user_id: Optional[str] = None,
        details: Optional[Dict] = None
    ) -> None:
        """
        Log an audit event.

        Args:
            event: Type of event (e.g., 'user_login', 'data_access')
            user_id: User who performed the action
            details: Additional event details
        """
        extra = {
            "event_type": event,
            "user_id": user_id or self.context.get("user_id"),
            **(details or {})
        }
        self.info(f"AUDIT: {event}", extra=extra)

    def performance(
        self,
        operation: str,
        duration_ms: float,
        status: str = "success"
    ) -> None:
        """
        Log performance metrics.

        Args:
            operation: Name of operation
            duration_ms: Duration in milliseconds
            status: Status (success, failure, etc.)
        """
        extra = {
            "operation": operation,
            "duration_ms": duration_ms,
            "status": status
        }
        self.info(f"PERFORMANCE: {operation} ({duration_ms}ms)", extra=extra)


def setup_logging(
    log_dir: Path = Path("logs"),
    log_level: int = logging.INFO,
    json_format: bool = True,
    anonymize_pii: bool = True,
    max_bytes: int = 10 * 1024 * 1024,  # 10 MB
    backup_count: int = 10
) -> None:
    """
    Set up centralized logging.

    Args:
        log_dir: Directory for log files
        log_level: Logging level (logging.INFO, logging.DEBUG, etc.)
        json_format: Use JSON formatting
        anonymize_pii: Anonymize PII in logs
        max_bytes: Max size of log file before rotation
        backup_count: Number of backup files to keep
    """
    log_dir.mkdir(parents=True, exist_ok=True)

    # Create formatter
    if json_format:
        formatter = JsonFormatter()
    else:
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )

    # Get root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)

    # Remove existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(log_level)
    console_handler.setFormatter(formatter)
    if anonymize_pii:
        console_handler.addFilter(PiiAnonymizingFilter())
    root_logger.addHandler(console_handler)

    # File handler with rotation
    file_handler = logging.handlers.RotatingFileHandler(
        log_dir / "app.log",
        maxBytes=max_bytes,
        backupCount=backup_count
    )
    file_handler.setLevel(log_level)
    file_handler.setFormatter(formatter)
    if anonymize_pii:
        file_handler.addFilter(PiiAnonymizingFilter())
    root_logger.addHandler(file_handler)

    # Error file handler
    error_handler = logging.handlers.RotatingFileHandler(
        log_dir / "error.log",
        maxBytes=max_bytes,
        backupCount=backup_count
    )
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(formatter)
    if anonymize_pii:
        error_handler.addFilter(PiiAnonymizingFilter())
    root_logger.addHandler(error_handler)

    # Audit file handler
    audit_handler = logging.handlers.RotatingFileHandler(
        log_dir / "audit.log",
        maxBytes=max_bytes,
        backupCount=backup_count
    )
    audit_handler.setLevel(logging.INFO)
    audit_handler.setFormatter(formatter)
    root_logger.addHandler(audit_handler)


def get_logger(name: str) -> ContextualLogger:
    """Get a contextual logger instance."""
    return ContextualLogger(name)


def log_operation(operation_name: str):
    """
    Decorator for logging function execution.

    Args:
        operation_name: Name of operation for logging
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            import time
            logger = get_logger(func.__module__)
            request_id = str(uuid.uuid4())

            logger.set_context(request_id=request_id, operation=operation_name)

            try:
                start_time = time.time()
                result = func(*args, **kwargs)
                duration = (time.time() - start_time) * 1000

                logger.performance(operation_name, duration, "success")
                return result

            except Exception as e:
                duration = (time.time() - start_time) * 1000
                logger.performance(operation_name, duration, "error")
                logger.error(f"Error in {operation_name}: {str(e)}", exc_info=True)
                raise

            finally:
                logger.clear_context()

        return wrapper

    return decorator


# Export convenience functions
__all__ = [
    'setup_logging',
    'get_logger',
    'log_operation',
    'ContextualLogger',
    'PiiAnonymizingFilter',
    'JsonFormatter',
]

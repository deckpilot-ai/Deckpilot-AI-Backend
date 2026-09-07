"""Centralized production diagnostics and error logging service."""

import hashlib
import json
import logging
import re
import time
import traceback
from typing import Any
from sqlalchemy import or_, and_, delete
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.context import (
    generate_correlation_id,
    get_correlation_id,
    get_current_job_id,
    get_current_project_id,
    get_current_user_id,
)
from app.db.engine import SessionLocal
from app.models.application_log import ApplicationLog

logger = logging.getLogger("deckpilot.diagnostics")

# Sensitive key patterns for recursive redaction
SENSITIVE_KEY_PATTERNS = [
    r"pass(word)?",
    r"secret",
    r"token",
    r"key",
    r"auth(orization)?",
    r"cookie",
    r"session",
    r"jwt",
    r"credential",
    r"cert",
    r"private",
    r"api[_-]?key",
    r"access[_-]?token",
    r"refresh[_-]?token",
]
SENSITIVE_KEY_REGEX = re.compile(f"^({'|'.join(SENSITIVE_KEY_PATTERNS)})$", re.IGNORECASE)

# String patterns: Bearer tokens, JWTs, Database credentials
BEARER_REGEX = re.compile(r"Bearer\s+[A-Za-z0-9_\-\.]+", re.IGNORECASE)
JWT_REGEX = re.compile(r"eyJ[A-Za-z0-9-_=]+\.[A-Za-z0-9-_=]+\.?[A-Za-z0-9-_.+/=]*")
DB_URL_REGEX = re.compile(r"(sqlite|libsql|postgresql|mysql|mongodb):\/\/[^:\s]+:[^@\s]+@[^\s]+")

# Maximum limits to prevent oversized logs
MAX_MESSAGE_LENGTH = 2000
MAX_STACK_TRACE_LENGTH = 10000
MAX_DATA_LENGTH = 8000


def sanitize_value(val: Any, depth: int = 0) -> Any:
    """Recursively redact secrets and sensitive data from dictionaries, lists, and strings."""
    if depth > 10:
        return "[TRUNCATED_NESTING]"

    if isinstance(val, dict):
        sanitized = {}
        for k, v in val.items():
            k_str = str(k)
            if SENSITIVE_KEY_REGEX.search(k_str) or any(s in k_str.lower() for s in ["password", "secret", "token", "apikey", "api_key", "auth"]):
                sanitized[k_str] = "[REDACTED]"
            else:
                sanitized[k_str] = sanitize_value(v, depth + 1)
        return sanitized

    if isinstance(val, (list, tuple, set)):
        return [sanitize_value(item, depth + 1) for item in val]

    if isinstance(val, (bytes, bytearray, memoryview)):
        return f"<binary data: {len(val)} bytes>"

    if isinstance(val, str):
        sanitized_str = BEARER_REGEX.sub("Bearer [REDACTED]", val)
        sanitized_str = JWT_REGEX.sub("[REDACTED_JWT]", sanitized_str)
        sanitized_str = DB_URL_REGEX.sub(r"\1://[REDACTED_USER]:[REDACTED_PASS]@[HOST]", sanitized_str)
        return sanitized_str

    return val


def sanitize_to_json_str(data: Any, max_len: int = MAX_DATA_LENGTH) -> str | None:
    """Sanitize data and serialize to a JSON string within length limits."""
    if data is None:
        return None
    try:
        clean_data = sanitize_value(data)
        encoded = json.dumps(clean_data, default=str)
        if len(encoded) > max_len:
            return encoded[:max_len] + "... [TRUNCATED]"
        return encoded
    except Exception as e:
        return f'{{"error": "Failed to serialize context: {str(e)}"}}'


def compute_fingerprint(
    error_type: str | None,
    service: str,
    operation: str | None,
    error_message: str | None,
) -> str | None:
    """Generate a stable fingerprint for grouping similar error instances."""
    if not error_type and not error_message:
        return None
    
    # Normalize error message by removing digits, UUIDs, and extra whitespace
    norm_msg = (error_message or "").strip().lower()
    norm_msg = re.sub(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", "<uuid>", norm_msg)
    norm_msg = re.sub(r"\b\d+\b", "<num>", norm_msg)
    norm_msg = re.sub(r"\s+", " ", norm_msg)[:200]

    raw = f"{error_type or 'Unknown'}:{service}:{operation or 'none'}:{norm_msg}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


class DiagnosticsService:
    """Centralized service for capturing production errors, slow operations, and diagnostic events."""

    @staticmethod
    def _persist(log_entry: ApplicationLog) -> None:
        """Write log entry to the database in an isolated session with fallback to console."""
        try:
            with SessionLocal() as db:
                db.add(log_entry)
                db.commit()
        except Exception as db_err:
            # Fallback to standard console logger to ensure application never crashes on logging failures
            logger.error(
                "CRITICAL: Failed to persist ApplicationLog to DB: %s. Log entry details: "
                "id=%s correlation_id=%s level=%s service=%s agent=%s error_type=%s error_message=%s",
                db_err,
                log_entry.id,
                log_entry.correlation_id,
                log_entry.level,
                log_entry.service,
                log_entry.agent_name,
                log_entry.error_type,
                log_entry.error_message,
            )

    @classmethod
    def log(
        cls,
        level: str = "ERROR",
        message: str = "",
        error: BaseException | None = None,
        correlation_id: str | None = None,
        service: str = "deckpilot-backend",
        component: str | None = None,
        agent_name: str | None = None,
        operation: str | None = None,
        endpoint: str | None = None,
        http_method: str | None = None,
        status_code: int | None = None,
        user_id: str | None = None,
        workspace_id: str | None = None,
        project_id: str | None = None,
        conversation_id: str | None = None,
        message_id: str | None = None,
        job_id: str | None = None,
        provider: str | None = None,
        provider_operation: str | None = None,
        provider_status_code: int | None = None,
        provider_request_id: str | None = None,
        model_name: str | None = None,
        started_at: int | None = None,
        completed_at: int | None = None,
        duration_ms: int | None = None,
        attempt_number: int | None = 1,
        max_attempts: int | None = 1,
        request_data: Any = None,
        additional_context: Any = None,
        save_to_db: bool = True,
    ) -> str:
        """Log a diagnostic entry, sanitize all inputs, compute fingerprint, and persist."""
        cid = correlation_id or get_correlation_id() or generate_correlation_id()
        uid = user_id or get_current_user_id()
        pid = project_id or get_current_project_id()
        jid = job_id or get_current_job_id()

        error_type = type(error).__name__ if error else None
        error_msg = str(error) if error else message
        if error_msg and len(error_msg) > MAX_MESSAGE_LENGTH:
            error_msg = error_msg[:MAX_MESSAGE_LENGTH] + "... [TRUNCATED]"

        stack_trace = None
        if error:
            tb = "".join(traceback.format_exception(type(error), error, error.__traceback__))
            # Sanitize stack trace for any potential inline secrets/tokens
            stack_trace = sanitize_value(tb)
            if len(stack_trace) > MAX_STACK_TRACE_LENGTH:
                stack_trace = stack_trace[:MAX_STACK_TRACE_LENGTH] + "\n... [TRUNCATED]"

        clean_request_data = sanitize_to_json_str(request_data)
        clean_context = sanitize_to_json_str(additional_context)

        fingerprint = compute_fingerprint(error_type, service, operation or component or agent_name, error_msg)

        now = int(time.time())
        level = level.upper()

        # Always log to standard python logger
        log_msg = (
            f"[{level}] correlation_id={cid} service={service} agent={agent_name} "
            f"op={operation} err={error_type}: {error_msg}"
        )
        if level in ("CRITICAL", "ERROR"):
            logger.error(log_msg)
        elif level == "WARNING":
            logger.warning(log_msg)
        else:
            logger.info(log_msg)

        # Determine if we should save to DB (policy: WARNING, ERROR, CRITICAL, or explicit save_to_db)
        should_db_log = save_to_db and level in ("WARNING", "ERROR", "CRITICAL")
        if should_db_log:
            entry = ApplicationLog(
                correlation_id=cid,
                fingerprint=fingerprint,
                timestamp=now,
                level=level,
                environment=settings.app_env,
                service=service,
                component=component,
                agent_name=agent_name,
                operation=operation,
                endpoint=endpoint,
                http_method=http_method,
                status_code=status_code,
                user_id=uid,
                workspace_id=workspace_id,
                project_id=pid,
                conversation_id=conversation_id,
                message_id=message_id,
                job_id=jid,
                error_type=error_type,
                error_message=error_msg,
                stack_trace=stack_trace,
                provider=provider,
                provider_operation=provider_operation,
                provider_status_code=provider_status_code,
                provider_request_id=provider_request_id,
                model_name=model_name,
                started_at=started_at,
                completed_at=completed_at or now,
                duration_ms=duration_ms,
                attempt_number=attempt_number,
                max_attempts=max_attempts,
                request_data=clean_request_data,
                additional_context=clean_context,
                resolved=0,
            )
            cls._persist(entry)

        return cid

    @classmethod
    def log_exception(
        cls,
        exc: BaseException,
        endpoint: str | None = None,
        http_method: str | None = None,
        status_code: int = 500,
        request_data: Any = None,
        additional_context: Any = None,
        **kwargs: Any,
    ) -> str:
        """Handle unhandled exceptions with full trace, endpoint details, and correlation ID."""
        return cls.log(
            level="ERROR",
            error=exc,
            endpoint=endpoint,
            http_method=http_method,
            status_code=status_code,
            request_data=request_data,
            additional_context=additional_context,
            **kwargs,
        )

    @classmethod
    def log_agent_failure(
        cls,
        agent_name: str,
        operation: str,
        error: BaseException | str,
        duration_ms: int | None = None,
        attempt_number: int = 1,
        max_attempts: int = 1,
        additional_context: Any = None,
        **kwargs: Any,
    ) -> str:
        """Log an agent task execution failure."""
        err_obj = error if isinstance(error, BaseException) else None
        msg = str(error) if not isinstance(error, BaseException) else ""
        return cls.log(
            level="ERROR",
            agent_name=agent_name,
            operation=operation,
            error=err_obj,
            message=msg,
            duration_ms=duration_ms,
            attempt_number=attempt_number,
            max_attempts=max_attempts,
            additional_context=additional_context,
            **kwargs,
        )

    @classmethod
    def log_external_api_failure(
        cls,
        provider: str,
        operation: str,
        error: BaseException | str,
        model_name: str | None = None,
        provider_status_code: int | None = None,
        provider_request_id: str | None = None,
        duration_ms: int | None = None,
        attempt_number: int = 1,
        max_attempts: int = 1,
        additional_context: Any = None,
        **kwargs: Any,
    ) -> str:
        """Log an external API provider failure (LLM, R2, Cloudflare, etc.)."""
        err_obj = error if isinstance(error, BaseException) else None
        msg = str(error) if not isinstance(error, BaseException) else ""
        return cls.log(
            level="ERROR",
            provider=provider,
            provider_operation=operation,
            model_name=model_name,
            provider_status_code=provider_status_code,
            provider_request_id=provider_request_id,
            error=err_obj,
            message=msg,
            duration_ms=duration_ms,
            attempt_number=attempt_number,
            max_attempts=max_attempts,
            additional_context=additional_context,
            **kwargs,
        )

    @classmethod
    def log_slow_operation(
        cls,
        component: str,
        operation: str,
        duration_ms: int,
        threshold_ms: int,
        agent_name: str | None = None,
        provider: str | None = None,
        additional_context: Any = None,
        **kwargs: Any,
    ) -> str:
        """Log a warning when an operation exceeds its configured latency threshold."""
        msg = f"Slow operation detected in {component}:{operation}. Took {duration_ms}ms (threshold: {threshold_ms}ms)"
        context = {
            "duration_ms": duration_ms,
            "threshold_ms": threshold_ms,
            **(additional_context or {}),
        }
        return cls.log(
            level="WARNING",
            message=msg,
            component=component,
            operation=operation,
            agent_name=agent_name,
            provider=provider,
            duration_ms=duration_ms,
            additional_context=context,
            **kwargs,
        )

    @staticmethod
    def cleanup_old_logs(
        db: Session,
        error_retention_days: int = 90,
        warning_retention_days: int = 14,
        resolved_retention_days: int = 30,
    ) -> int:
        """Clean up old application logs according to retention policies."""
        now = int(time.time())
        error_cutoff = now - (error_retention_days * 86400)
        warning_cutoff = now - (warning_retention_days * 86400)
        resolved_cutoff = now - (resolved_retention_days * 86400)

        condition = or_(
            and_(ApplicationLog.level.in_(["ERROR", "CRITICAL"]), ApplicationLog.timestamp < error_cutoff),
            and_(ApplicationLog.level.in_(["WARNING", "INFO", "DEBUG"]), ApplicationLog.timestamp < warning_cutoff),
            and_(ApplicationLog.resolved == 1, ApplicationLog.timestamp < resolved_cutoff),
        )

        stmt = delete(ApplicationLog).where(condition)
        result = db.execute(stmt)
        db.commit()
        return result.rowcount or 0

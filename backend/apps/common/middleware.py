"""
Observability Middleware & Sensitive Log Redaction Filter.
Provides:
- Request correlation IDs (X-Request-ID)
- Request duration timing (X-Response-Time-Ms)
- Configurable slow-request performance warnings
- Structured request/status logging with sensitive data redaction
"""

import logging
import re
import time
import uuid
from django.conf import settings

request_logger = logging.getLogger('bizpermit.requests')
perf_logger = logging.getLogger('bizpermit.performance')

_SAFE_REQ_ID_RE = re.compile(r'^[A-Za-z0-9_\-]{6,64}$')
_BEARER_RE = re.compile(r'(Bearer\s+)[A-Za-z0-9\-_]+\.[A-Za-z0-9\-_]+\.[A-Za-z0-9\-_]+', re.IGNORECASE)
_URI_CRED_RE = re.compile(r'(://[^:\s]+:)([^@\s]+)(@)')
_SENSITIVE_KV_RE = re.compile(
    r'((?:password|passwd|secret|token|refresh_token|access_token|api_key|authorization)\s*[=:]\s*)([^\s,&"\'}\]]+)',
    re.IGNORECASE,
)
_SENSITIVE_QUERY_KEYS = {'token', 'password', 'secret', 'key', 'access_token', 'refresh_token'}


def redact_sensitive_text(text: str) -> str:
    """Masks JWTs, MongoDB URI passwords, and secret key-value pairs in log strings."""
    if not text or not isinstance(text, str):
        return text
    masked = _BEARER_RE.sub(r'\1[REDACTED_JWT]', text)
    masked = _URI_CRED_RE.sub(r'\1*****\3', masked)
    masked = _SENSITIVE_KV_RE.sub(r'\1[REDACTED]', masked)
    return masked


class SensitiveDataFilter(logging.Filter):
    """Logging filter that redacts credentials, tokens, and secrets from log records."""

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            record.msg = redact_sensitive_text(record.msg)
        if record.args:
            if isinstance(record.args, dict):
                record.args = {
                    k: redact_sensitive_text(v) if isinstance(v, str) else v
                    for k, v in record.args.items()
                }
            elif isinstance(record.args, tuple):
                record.args = tuple(
                    redact_sensitive_text(a) if isinstance(a, str) else a
                    for a in record.args
                )
        return True


def _sanitize_query_params(query_dict) -> str:
    if not query_dict:
        return ""
    parts = []
    for key in query_dict.keys():
        if key.lower() in _SENSITIVE_QUERY_KEYS:
            parts.append(f"{key}=[REDACTED]")
        else:
            parts.append(f"{key}={query_dict.get(key)}")
    return "?" + "&".join(parts) if parts else ""


class RequestObservabilityMiddleware:
    """Assigns correlation IDs, measures latency, and logs API requests safely."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        incoming_id = request.headers.get('X-Request-ID', '').strip()
        if incoming_id and _SAFE_REQ_ID_RE.match(incoming_id):
            request.request_id = incoming_id
        else:
            request.request_id = f"req_{uuid.uuid4().hex[:12]}"

        start = time.perf_counter()
        response = self.get_response(request)
        duration_ms = round((time.perf_counter() - start) * 1000, 2)

        response['X-Request-ID'] = request.request_id
        response['X-Response-Time-Ms'] = str(duration_ms)

        user = getattr(request, 'user', None)
        user_id = getattr(user, 'id', None) if getattr(user, 'is_authenticated', False) else 'anon'
        safe_qs = _sanitize_query_params(getattr(request, 'GET', None))
        status_code = getattr(response, 'status_code', 0)

        log_msg = (
            f"request_id={request.request_id} method={request.method} "
            f"path={request.path}{safe_qs} status={status_code} "
            f"duration_ms={duration_ms} user={user_id}"
        )

        if status_code >= 500:
            request_logger.error(log_msg)
        elif status_code >= 400:
            request_logger.warning(log_msg)
        elif request.path != '/api/v1/health/live':
            request_logger.info(log_msg)

        slow_threshold = getattr(settings, 'SLOW_REQUEST_THRESHOLD_MS', 500)
        if duration_ms >= slow_threshold:
            perf_logger.warning(
                f"SLOW_REQUEST request_id={request.request_id} method={request.method} "
                f"path={request.path} duration_ms={duration_ms} threshold_ms={slow_threshold}"
            )

        return response

"""Error severity classifier."""

SEVERITY_MAP = {
    # Severity 4 — human required
    "PermissionError": 4,
    "SecurityError": 4,
    "DBMigration": 4,
    "AuthChange": 4,
    "auth": 4,
    "security": 4,
    "jwt": 4,
    "password": 4,
    # Severity 3 — AI fix
    "SyntaxError": 3,
    "ImportError": 3,
    "AttributeError": 3,
    "NameError": 3,
    "TypeError": 3,
    "KeyError": 3,
    # Severity 2 — auto restart
    "ConnectionError": 2,
    "Timeout": 2,
    "ProcessCrashed": 2,
    "ServiceUnavailable": 2,
    # Severity 1 — log only
    "DeprecationWarning": 1,
    "slow_response": 1,
}

AUTH_SENSITIVE_SERVICES = {"auth", "users", "sessions"}


def classify_error(service: str, error_type: str) -> int:
    """Classify error severity 1–4."""
    # Any error in auth services is severity 4
    if service.lower() in AUTH_SENSITIVE_SERVICES:
        return 4

    # Check error type keywords
    error_lower = error_type.lower()
    for keyword, severity in SEVERITY_MAP.items():
        if keyword.lower() in error_lower:
            return severity

    # Default to severity 2 for unknown service errors
    return 2

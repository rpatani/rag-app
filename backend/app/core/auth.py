"""
API-key authentication.

Single-key model, appropriate for a single-firm appliance deployment:
the operator sets APP_API_KEY in the environment; every /api request must
present it. When APP_API_KEY is unset, auth is disabled (development mode)
and a warning is logged at startup.

Security properties:
- Timing-safe comparison (hmac.compare_digest) to prevent key recovery
  via response-time measurement.
- The key is never logged; failures log only the client address.
- Key accepted via "Authorization: Bearer <key>" or "X-API-Key: <key>".
"""

import hmac
import logging

from fastapi import HTTPException, Request, status

from app.config import get_settings

logger = logging.getLogger(__name__)


def _extract_key(request: Request) -> str | None:
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        return auth_header[len("Bearer "):]
    return request.headers.get("X-API-Key")


def require_api_key(request: Request) -> None:
    """FastAPI dependency: reject the request unless it carries the API key."""
    settings = get_settings()

    if not settings.app_api_key:
        # Auth disabled (dev mode). Warned once at startup in main.py.
        return

    provided = _extract_key(request)
    if not provided or not hmac.compare_digest(
        provided.encode("utf-8"), settings.app_api_key.encode("utf-8")
    ):
        client = request.client.host if request.client else "unknown"
        logger.warning("Rejected unauthenticated request from %s to %s", client, request.url.path)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid API key.",
            headers={"WWW-Authenticate": "Bearer"},
        )

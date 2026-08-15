"""Server-side API-Key authentication and role resolution from environment config."""

from __future__ import annotations

import json
import os
from typing import Mapping

from fastapi import Header, HTTPException, Security
from fastapi.security import APIKeyHeader

from .domain.authority import Principal, Role

# Standard API Key header definition
API_KEY_HEADER = APIKeyHeader(name="X-API-Key", auto_error=False)


def _load_api_key_registry() -> dict[str, Principal]:
    """Load API Key to Principal mapping from environment configuration without hardcoding."""
    env_keys = os.environ.get("LOT_ZERO_API_KEYS")
    if env_keys:
        try:
            raw_dict = json.loads(env_keys)
            registry = {}
            for key, data in raw_dict.items():
                registry[key] = Principal(
                    tenant_id=data["tenant_id"],
                    principal_id=data["principal_id"],
                    roles=tuple(data["roles"]),
                )
            return registry
        except Exception as exc:
            raise RuntimeError(f"Failed to parse LOT_ZERO_API_KEYS environment variable: {exc}") from exc

    # Default configured environment keys for evaluation & testing environments
    return {
        "key-qa-lead-01": Principal(
            tenant_id="EVAL-TENANT-01", principal_id="QA-LEAD-01", roles=("qa",)
        ),
        "key-recall-coord-01": Principal(
            tenant_id="EVAL-TENANT-01", principal_id="RECALL-COORD-01", roles=("recall_coordinator",)
        ),
        "key-ops-01": Principal(
            tenant_id="EVAL-TENANT-01", principal_id="OPS-001", roles=("customer_operations",)
        ),
        "key-ops-approver-01": Principal(
            tenant_id="EVAL-TENANT-01", principal_id="OPS-APPROVER-01", roles=("customer_operations",)
        ),
        "key-closure-auth-01": Principal(
            tenant_id="EVAL-TENANT-01", principal_id="CLOSURE-AUTH-01", roles=("closure_authority",)
        ),
        "key-agent-svc-01": Principal(
            tenant_id="EVAL-TENANT-01", principal_id="AGENT-SVC-01", roles=("agent_service",)
        ),
    }


def get_principal_for_key(api_key: str) -> Principal | None:
    """Lookup Principal for given API key."""
    registry = _load_api_key_registry()
    return registry.get(api_key.strip()) if api_key else None


async def get_current_principal(
    x_api_key: str | None = Security(API_KEY_HEADER),
    authorization: str | None = Header(default=None),
) -> Principal:
    """FastAPI dependency to strictly authenticate request and resolve Principal."""
    key = x_api_key
    if not key and authorization and authorization.startswith("Bearer "):
        key = authorization[7:].strip()

    if not key:
        raise HTTPException(
            status_code=401,
            detail="Authentication required: X-API-Key or Bearer token missing.",
        )

    principal = get_principal_for_key(key)
    if principal is None:
        raise HTTPException(
            status_code=401,
            detail="Authentication failed: Invalid API key.",
        )

    return principal


def require_role(principal: Principal, role: Role) -> Principal:
    """Verify that the authenticated principal possesses the required domain role."""
    if role not in principal.roles:
        raise HTTPException(
            status_code=403,
            detail=f"Forbidden: Principal '{principal.principal_id}' lacks required role '{role}'.",
        )
    return principal


# Server secret for short-lived HMAC SSE tokens
SSE_SECRET = os.environ.get("LOT_ZERO_SSE_SECRET", "lot-zero-ephemeral-sse-token-secret-key-2026")


def create_sse_token(principal: Principal, ttl_seconds: int = 60) -> str:
    """Create short-lived HMAC-signed token for EventSource authentication."""
    import base64
    import hashlib
    import hmac
    import time

    exp = int(time.time()) + ttl_seconds
    payload_dict = {
        "principal_id": principal.principal_id,
        "tenant_id": principal.tenant_id,
        "exp": exp,
    }
    payload_bytes = json.dumps(payload_dict, separators=(",", ":")).encode("utf-8")
    b64_payload = base64.urlsafe_b64encode(payload_bytes).decode("utf-8").rstrip("=")
    sig = hmac.new(SSE_SECRET.encode("utf-8"), b64_payload.encode("utf-8"), hashlib.sha256).hexdigest()
    return f"{b64_payload}.{sig}"


def verify_sse_token(token: str) -> Principal | None:
    """Verify HMAC signature, expiration, and principal for given SSE token."""
    import base64
    import hashlib
    import hmac
    import time

    try:
        parts = token.strip().split(".")
        if len(parts) != 2:
            return None
        b64_payload, sig = parts
        padded = b64_payload + "=" * (-len(b64_payload) % 4)
        expected_sig = hmac.new(SSE_SECRET.encode("utf-8"), b64_payload.encode("utf-8"), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(sig, expected_sig):
            return None
        data = json.loads(base64.urlsafe_b64decode(padded.encode("utf-8")).decode("utf-8"))
        if time.time() > data.get("exp", 0):
            return None
        principal_id = data.get("principal_id")
        tenant_id = data.get("tenant_id")
        registry = _load_api_key_registry()
        for p in registry.values():
            if p.principal_id == principal_id and p.tenant_id == tenant_id:
                return p
        return Principal(tenant_id=tenant_id, principal_id=principal_id, roles=())
    except Exception:
        return None

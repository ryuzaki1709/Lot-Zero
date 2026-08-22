"""Centralized typed configuration management for Lot Zero."""

from __future__ import annotations

import json
import os
from urllib.parse import urlparse

from pydantic import BaseModel, Field


def _validate_origin(origin: str) -> str:
    """Ensure an allowed origin is a valid HTTP/HTTPS URL with scheme and host."""
    clean = origin.strip().rstrip("/")
    if not clean:
        raise ValueError("Allowed origin cannot be empty")
    parsed = urlparse(clean)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        raise ValueError(f"Invalid origin URL format: {origin}")
    return clean


class LotZeroConfig(BaseModel):
    """Centralized configuration for Lot Zero application runtime."""

    evaluation_mode: bool = False
    tenant_id: str = "EVAL-TENANT-01"
    db_path: str = Field(default_factory=lambda: os.getenv("LOT_ZERO_DB_PATH", "lot_zero.db"))
    sse_secret: str = ""
    api_keys_raw: str | None = None
    allowed_origins: list[str] = Field(default_factory=list)


def load_config() -> LotZeroConfig:
    """Load configuration from environment variables."""
    eval_mode_str = os.getenv("LOT_ZERO_EVALUATION_MODE", "false").strip().lower()
    evaluation_mode = eval_mode_str in ("true", "1", "yes")

    tenant_id = os.getenv("LOT_ZERO_TENANT_ID", "EVAL-TENANT-01").strip()
    db_path = os.getenv("LOT_ZERO_DB_PATH", "lot_zero.db").strip()
    sse_secret = os.getenv("LOT_ZERO_SSE_SECRET", "").strip()
    api_keys_raw = os.getenv("LOT_ZERO_API_KEYS")

    raw_origins = os.getenv("LOT_ZERO_ALLOWED_ORIGINS", "")
    allowed_origins: list[str] = []
    if raw_origins:
        for part in raw_origins.split(","):
            part_clean = part.strip()
            if part_clean:
                allowed_origins.append(_validate_origin(part_clean))
    elif evaluation_mode:
        allowed_origins = [
            "http://localhost:5173",
            "http://127.0.0.1:5173",
            "http://localhost:3000",
            "http://127.0.0.1:3000",
            "http://localhost:8000",
            "http://127.0.0.1:8000",
        ]

    return LotZeroConfig(
        evaluation_mode=evaluation_mode,
        tenant_id=tenant_id,
        db_path=db_path,
        sse_secret=sse_secret,
        api_keys_raw=api_keys_raw,
        allowed_origins=allowed_origins,
    )


def validate_config_for_startup(config: LotZeroConfig) -> None:
    """Fail-fast validation for non-evaluation mode."""
    if not config.evaluation_mode:
        if not config.api_keys_raw or not config.api_keys_raw.strip():
            raise RuntimeError(
                "FATAL: Production startup refused: LOT_ZERO_API_KEYS environment variable is missing or empty."
            )
        try:
            parsed = json.loads(config.api_keys_raw)
            if not isinstance(parsed, dict) or len(parsed) == 0:
                raise ValueError("LOT_ZERO_API_KEYS must be a non-empty JSON mapping.")
        except Exception as exc:
            raise RuntimeError(
                f"FATAL: Production startup refused: Failed to parse LOT_ZERO_API_KEYS JSON: {exc}"
            ) from exc

        if (
            not config.sse_secret
            or config.sse_secret == "lot-zero-ephemeral-sse-token-secret-key-2026"
            or len(config.sse_secret) < 32
        ):
            raise RuntimeError(
                "FATAL: Production startup refused: Strong LOT_ZERO_SSE_SECRET (minimum 32 characters, non-default) is required."
            )

        if not config.allowed_origins:
            raise RuntimeError(
                "FATAL: Production startup refused: Explicit LOT_ZERO_ALLOWED_ORIGINS list is required in production."
            )
    else:
        # Evaluation mode defaults
        if not config.sse_secret:
            config.sse_secret = "lot-zero-ephemeral-sse-token-secret-key-2026"

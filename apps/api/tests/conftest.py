"""Pytest configuration and session-wide fixtures for Lot Zero test suite."""

import os

import pytest

# Ensure evaluation mode is active by default for test execution
os.environ["LOT_ZERO_EVALUATION_MODE"] = "true"
os.environ["LOT_ZERO_SSE_SECRET"] = "lot-zero-ephemeral-sse-token-secret-key-2026-test-32chars"
os.environ["LOT_ZERO_ALLOWED_ORIGINS"] = (
    "http://localhost:5173,http://127.0.0.1:5173,http://localhost:8000,http://127.0.0.1:8000"
)


@pytest.fixture(autouse=True)
def ensure_evaluation_mode(monkeypatch):
    """Keep evaluation mode active by default for all test cases."""
    monkeypatch.setenv("LOT_ZERO_EVALUATION_MODE", "true")
    monkeypatch.setenv(
        "LOT_ZERO_SSE_SECRET", "lot-zero-ephemeral-sse-token-secret-key-2026-test-32chars"
    )
    monkeypatch.setenv(
        "LOT_ZERO_ALLOWED_ORIGINS",
        "http://localhost:5173,http://127.0.0.1:5173,http://localhost:8000,http://127.0.0.1:8000",
    )

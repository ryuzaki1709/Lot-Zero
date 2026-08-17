"""Gemini Multimodal Agent for analyzing raw food safety signals and generating evidence spans."""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import traceback
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel

from .models import EvidenceSpan

logger = logging.getLogger(__name__)


class ClaimExtraction(BaseModel):
    claim_type: str
    verbatim_quote: str


class SignalAnalysisSchema(BaseModel):
    ingredient_lot: str
    pathogen: str
    claims: list[ClaimExtraction]


@dataclass(frozen=True)
class ExtractedSignal:
    source_id: str
    ingredient_lot: str
    pathogen: str
    spans: tuple[EvidenceSpan, ...]
    recommended_scope_records: tuple[str, ...]
    extracted_at: datetime
    model_version: str
    doc_hash: str
    is_live_model: bool = False
    discarded_claims: tuple[dict[str, Any], ...] = ()
    raw_text: str = ""


def _deterministic_extract(raw_notice_text: str) -> tuple[str, str, list[dict[str, str]]]:
    """Deterministic fallback extractor parsing raw document text directly."""
    # 1. Ingredient Lot extraction
    lot_match = re.search(r"(?:Ingredient\s+Lot|Lot)\s+([A-Z0-9-]+)", raw_notice_text, re.IGNORECASE)
    ingredient_lot = lot_match.group(1).strip() if lot_match else "UNKNOWN-LOT"

    # 2. Pathogen extraction
    pathogen_match = re.search(r"POSITIVE\s+for\s+([^\.\n\(\)]+)", raw_notice_text, re.IGNORECASE)
    pathogen = pathogen_match.group(1).strip() if pathogen_match else "Pathogen Detected"

    # 3. Citation phrases derived from document content
    candidate_claims = []
    
    # Check lot sentence
    lot_quote_match = re.search(r"(?:Raw\s+Ingredient\s+Lot\s+[A-Z0-9-]+\s*\([^\)]+\)|Lot\s+[A-Z0-9-]+)", raw_notice_text)
    if lot_quote_match:
        candidate_claims.append({
            "claim_type": "Contaminated Lot",
            "verbatim_quote": lot_quote_match.group(0),
        })

    # Check pathogen sentence
    pathogen_quote_match = re.search(r"POSITIVE\s+for\s+[^\.\n]+", raw_notice_text)
    if pathogen_quote_match:
        candidate_claims.append({
            "claim_type": "Biohazard Finding",
            "verbatim_quote": pathogen_quote_match.group(0),
        })

    # Check scope / recommendation sentence
    scope_quote_match = re.search(r"(?:Immediate\s+scope\s+isolation[^\.\n]+|RECOMMENDATION:[^\.\n]+)", raw_notice_text)
    if scope_quote_match:
        val = scope_quote_match.group(0)
        if val.startswith("RECOMMENDATION:"):
            val = val.replace("RECOMMENDATION:", "").strip()
        candidate_claims.append({
            "claim_type": "Containment Scope",
            "verbatim_quote": val,
        })

    return ingredient_lot, pathogen, candidate_claims


def analyze_safety_signal(
    raw_notice_text: str,
    *,
    tenant_id: str = "EVAL-TENANT-01",
    case_id: str = "EVAL-CASE-01",
    source_id: str = "LAB-SIGNAL-20260814-001",
    doc_version: str = "v1.0 (Signed Apex Labs Report)",
) -> ExtractedSignal:
    """Analyze raw laboratory notice text, extract contaminated lot and bounding evidence spans.
    
    Derives SHA-256 digest dynamically from the provided raw_notice_text, queries Gemini
    with structured schema if configured, derives character offsets mechanically via string indexing,
    and rejects ungrounded non-verbatim quotes.
    """
    now = datetime.now(UTC)
    doc_hash = hashlib.sha256(raw_notice_text.encode("utf-8")).hexdigest()

    use_vertex = os.getenv("GOOGLE_GENAI_USE_VERTEXAI", "").strip().lower() in ("true", "1", "yes")
    gemini_key = os.getenv("GEMINI_API_KEY")

    parsed_result: SignalAnalysisSchema | None = None
    model_tag = "gemini-3.5-flash (Deterministic Replay)"
    is_live_model = False

    prompt = (
        "You are an industrial food safety recall specialist. Analyze this laboratory notification and extract:\n"
        "1. The exact raw ingredient lot identifier.\n"
        "2. The exact identified biological pathogen.\n"
        "3. Key grounding claims. For each claim, provide the claim_type and the EXACT character-for-character "
        "verbatim_quote copied directly from the text (do NOT calculate offsets and do NOT paraphrase).\n\n"
        f"DOCUMENT TEXT:\n{raw_notice_text}"
    )

    if use_vertex:
        try:
            from google import genai
            from google.genai import types

            project = os.getenv("GOOGLE_CLOUD_PROJECT", "project-b2c3348e-d718-4255-be2")
            location = os.getenv("GOOGLE_CLOUD_LOCATION", "global")
            client = genai.Client(vertexai=True, project=project, location=location)
            
            response = client.models.generate_content(
                model="gemini-3.5-flash",
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=SignalAnalysisSchema,
                ),
            )
            parsed_result = SignalAnalysisSchema.model_validate_json(response.text)
            model_tag = "gemini-3.5-flash (Vertex AI Live)"
            is_live_model = True
            logger.info("Gemini live extraction on Vertex AI succeeded.")
        except Exception as e:
            logger.exception("Vertex AI Exception during safety signal extraction: %s", e)
            traceback.print_exc()
            model_tag = f"gemini-3.5-flash (Vertex AI Fallback: {type(e).__name__})"
    elif gemini_key:
        try:
            from google import genai
            from google.genai import types

            client = genai.Client(api_key=gemini_key)
            response = client.models.generate_content(
                model="gemini-3.5-flash",
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=SignalAnalysisSchema,
                ),
            )
            parsed_result = SignalAnalysisSchema.model_validate_json(response.text)
            model_tag = "gemini-3.5-flash (Google GenAI Live)"
            is_live_model = True
            logger.info("Gemini live extraction on Google GenAI API succeeded.")
        except Exception as e:
            logger.exception("Google GenAI Exception during safety signal extraction: %s", e)
            traceback.print_exc()
            model_tag = f"gemini-3.5-flash (Google GenAI Fallback: {type(e).__name__})"

    # Fallback to deterministic parser if live model didn't run or failed
    if parsed_result is None:
        det_lot, det_pathogen, det_claims = _deterministic_extract(raw_notice_text)
        parsed_result = SignalAnalysisSchema(
            ingredient_lot=det_lot,
            pathogen=det_pathogen,
            claims=[ClaimExtraction(claim_type=c["claim_type"], verbatim_quote=c["verbatim_quote"]) for c in det_claims],
        )

    # Mechanical grounding verification and offset calculation
    valid_spans: list[EvidenceSpan] = []
    discarded_claims: list[dict[str, Any]] = []

    for idx, claim in enumerate(parsed_result.claims):
        quote = claim.verbatim_quote.strip()
        if not quote:
            continue
        
        # Grounding check: must exist verbatim in raw_notice_text
        if quote in raw_notice_text:
            start_offset = raw_notice_text.index(quote)
            end_offset = start_offset + len(quote)
            valid_spans.append(
                EvidenceSpan(
                    evidence_id=f"EVID-0{len(valid_spans) + 1}",
                    tenant_id=tenant_id,
                    case_id=case_id,
                    source_record_id=source_id,
                    source_doc_hash=doc_hash,
                    doc_version=doc_version,
                    claim_type=claim.claim_type,
                    start_offset=start_offset,
                    end_offset=end_offset,
                    captured_at=now,
                )
            )
        else:
            # Ungrounded claim rejected
            logger.warning("Rejected ungrounded citation quote: %r (claim=%s)", quote, claim.claim_type)
            discarded_claims.append({
                "claim_type": claim.claim_type,
                "quote": quote,
                "reason": "Quote not found verbatim in source document",
            })

    return ExtractedSignal(
        source_id=source_id,
        ingredient_lot=parsed_result.ingredient_lot.strip(),
        pathogen=parsed_result.pathogen.strip(),
        spans=tuple(valid_spans),
        recommended_scope_records=(),
        extracted_at=now,
        model_version=model_tag,
        doc_hash=doc_hash,
        is_live_model=is_live_model,
        discarded_claims=tuple(discarded_claims),
        raw_text=raw_notice_text,
    )

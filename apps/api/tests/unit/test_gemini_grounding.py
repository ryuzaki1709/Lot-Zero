"""Tests for Gemini signal grounding, schema extraction, and mechanical citation offset verification."""

import hashlib
from lot_zero.domain.gemini_agent import (
    ClaimExtraction,
    SignalAnalysisSchema,
    analyze_safety_signal,
)
from lot_zero.domain.selectors import RAW_TEXT


def test_gemini_grounding_follows_document():
    """Verify that extraction follows the input document dynamically rather than returning constants."""
    custom_doc = (
        "[EMERGENCY LAB ALERT - PACIFIC QUALITY LABS]\n"
        "SAMPLE ID: SPL-100492 | DATE: 2026-08-16 08:30 UTC\n"
        "CLIENT: EVAL-TENANT-01 Foods Corp\n"
        "TEST ITEM: Raw Ingredient Lot ING-9999 (Organic Rolled Oats)\n"
        "RESULT: POSITIVE for Listeria monocytogenes.\n"
        "CONCENTRATION: 5.1 x 10^2 CFU/g.\n"
        "RECOMMENDATION: Immediate scope isolation of all finished batches utilizing Lot ING-9999."
    )

    extracted = analyze_safety_signal(custom_doc)

    # 1. Assert extracted lot and pathogen follow custom document
    assert extracted.ingredient_lot == "ING-9999"
    assert "Listeria" in extracted.pathogen

    # 2. Assert dynamic SHA-256 hash
    expected_hash = hashlib.sha256(custom_doc.encode("utf-8")).hexdigest()
    assert extracted.doc_hash == expected_hash
    assert extracted.doc_hash != hashlib.sha256(RAW_TEXT.encode("utf-8")).hexdigest()

    # 3. Assert all derived offsets index the custom document mechanically
    assert len(extracted.spans) > 0
    for span in extracted.spans:
        assert span.source_doc_hash == expected_hash
        assert span.start_offset < span.end_offset
        sliced = custom_doc[span.start_offset:span.end_offset]
        assert len(sliced) > 0
        if span.claim_type == "Contaminated Lot":
            assert "ING-9999" in sliced
        elif span.claim_type == "Biohazard Finding":
            assert "Listeria" in sliced
        elif span.claim_type == "Containment Scope":
            assert "ING-9999" in sliced


def test_hallucinated_claims_rejected():
    """Verify that hallucinated or non-verbatim quotes are rejected and surfaced as discarded claims."""
    from unittest.mock import MagicMock, patch

    custom_doc = (
        "[REPORT] Sample SPL-123.\n"
        "TEST ITEM: Ingredient Lot ING-7777 (Sugar)\n"
        "RESULT: POSITIVE for E. coli O157:H7.\n"
        "RECOMMENDATION: Isolate immediately."
    )

    fake_schema = SignalAnalysisSchema(
        ingredient_lot="ING-7777",
        pathogen="E. coli O157:H7",
        claims=[
            # Genuine verbatim claim
            ClaimExtraction(
                claim_type="Biohazard Finding",
                verbatim_quote="POSITIVE for E. coli O157:H7",
            ),
            # Hallucinated / paraphrased non-verbatim claim
            ClaimExtraction(
                claim_type="Fabricated Safety Clearance",
                verbatim_quote="Everything is completely safe and cleared for distribution across all stores",
            ),
        ],
    )

    with patch("lot_zero.domain.gemini_agent.os.getenv") as mock_env:
        mock_env.side_effect = lambda k, d="": "true" if k == "GOOGLE_GENAI_USE_VERTEXAI" else d
        with patch("google.genai.Client") as mock_client_cls:
            mock_client = MagicMock()
            mock_client_cls.return_value = mock_client
            mock_response = MagicMock()
            mock_response.text = fake_schema.model_dump_json()
            mock_client.models.generate_content.return_value = mock_response

            extracted = analyze_safety_signal(custom_doc)

    assert extracted.ingredient_lot == "ING-7777"
    assert extracted.pathogen == "E. coli O157:H7"
    assert extracted.is_live_model is True

    # Valid claim accepted
    assert len(extracted.spans) == 1
    assert extracted.spans[0].claim_type == "Biohazard Finding"
    assert custom_doc[extracted.spans[0].start_offset:extracted.spans[0].end_offset] == "POSITIVE for E. coli O157:H7"

    # Hallucinated claim rejected & discarded
    assert len(extracted.discarded_claims) == 1
    assert extracted.discarded_claims[0]["claim_type"] == "Fabricated Safety Clearance"
    assert "not found verbatim" in extracted.discarded_claims[0]["reason"].lower()


def test_changing_document_changes_doc_hash_and_offsets():
    """Verify that prepending header text changes doc hash and shifts mechanical offsets."""
    prefix = "--- CONFIDENTIAL REGULATORY SUBMISSION HEADER ---\nINSPECTOR: AGENT-07\n\n"
    shifted_doc = prefix + RAW_TEXT

    extracted_original = analyze_safety_signal(RAW_TEXT)
    extracted_shifted = analyze_safety_signal(shifted_doc)

    # Hash must be distinct
    assert extracted_original.doc_hash != extracted_shifted.doc_hash
    assert extracted_shifted.doc_hash == hashlib.sha256(shifted_doc.encode("utf-8")).hexdigest()

    # Offsets must shift by prefix length
    prefix_len = len(prefix)
    assert len(extracted_original.spans) == len(extracted_shifted.spans)

    for orig_span, shifted_span in zip(extracted_original.spans, extracted_shifted.spans):
        assert shifted_span.start_offset == orig_span.start_offset + prefix_len
        assert shifted_span.end_offset == orig_span.end_offset + prefix_len
        assert RAW_TEXT[orig_span.start_offset:orig_span.end_offset] == shifted_doc[shifted_span.start_offset:shifted_span.end_offset]

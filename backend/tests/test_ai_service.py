import pytest
from fastapi.testclient import TestClient

from app.ai.service import ai_service
from app.main import app
from app.mapping.schemas import CanonicalInvoice
from app.matching.schemas import (
    FieldDifference,
    MatchClassification,
    ReconciliationRecordResult,
    UnmatchedReason,
)

client = TestClient(app)


def make_inv(
    inv_num: str = "INV-100", gstin: str = "27AAAAA0000A1Z5", total: float = 1180.0
) -> CanonicalInvoice:
    return CanonicalInvoice(
        invoice_number=inv_num,
        gstin=gstin,
        invoice_date="2024-04-01",
        taxable_value=1000.0,
        cgst=90.0,
        sgst=90.0,
        igst=0.0,
        total_invoice_value=total,
    )


# 1. Test AI Candidate Ambiguity Resolution
def test_ai_candidate_ambiguity_resolution():
    gst_rec = make_inv(inv_num="INV-100")
    candidate1 = make_inv(inv_num="INV100")
    candidate2 = make_inv(inv_num="INV-999")

    response = ai_service.resolve_candidate_ambiguity(gst_rec, [candidate1, candidate2])

    assert response.selected_candidate_invoice_number == "INV100"
    assert response.confidence > 0.70
    assert len(response.evidence) >= 1
    assert "Selected candidate 'INV100'" in response.reasoning


# 2. Test Low Confidence Ambiguity Resolution Fallback
def test_ai_ambiguity_low_confidence_fallback():
    gst_rec = make_inv(inv_num="INV-100", gstin="27AAAAA0000A1Z5")
    # Low similarity candidate with different GSTIN
    candidate_low = make_inv(inv_num="XYZ-999", gstin="27BBBBB0000B1Z2")

    response = ai_service.resolve_candidate_ambiguity(gst_rec, [candidate_low])

    assert response.requires_manual_review is True
    assert response.confidence < 0.80


# 3. Test Post-Reconciliation Discrepancy Review for EXACT_MATCH
def test_ai_discrepancy_review_exact_match():
    rec_result = ReconciliationRecordResult(
        gst_record=make_inv(),
        erp_record=make_inv(),
        classification=MatchClassification.EXACT_MATCH,
        field_differences=[],
    )

    review = ai_service.review_discrepancy(rec_result)

    assert "No discrepancies found" in review.explanation
    assert "Approve automatically" in review.recommended_action


# 4. Test Post-Reconciliation Discrepancy Review for DISCREPANCY
def test_ai_discrepancy_review_discrepancy():
    diff = FieldDifference(
        field_name="total_invoice_value",
        gst_value=1180.0,
        erp_value=1500.0,
        difference_amount=320.0,
        is_within_tolerance=False,
        is_critical=True,
    )
    rec_result = ReconciliationRecordResult(
        gst_record=make_inv(total=1180.0),
        erp_record=make_inv(total=1500.0),
        classification=MatchClassification.DISCREPANCY,
        field_differences=[diff],
    )

    review = ai_service.review_discrepancy(rec_result)

    assert "Financial discrepancy detected" in review.explanation
    assert "total_invoice_value" in review.explanation
    assert "Ineligible for automatic ITC claim" in review.audit_remark
    assert "amended debit/credit note" in review.recommended_action.lower()


# 5. Test API POST /api/v1/ai/resolve-ambiguity
def test_api_resolve_ambiguity_endpoint():
    payload = {
        "gst_record": {
            "invoice_number": "INV-100",
            "gstin": "27AAAAA0000A1Z5",
            "total_invoice_value": 1180.0,
        },
        "candidate_erp_records": [
            {
                "invoice_number": "INV100",
                "gstin": "27AAAAA0000A1Z5",
                "total_invoice_value": 1180.0,
            }
        ],
    }

    response = client.post("/api/v1/ai/resolve-ambiguity", json=payload)
    assert response.status_code == 200

    data = response.json()
    assert data["selected_candidate_invoice_number"] == "INV100"
    assert data["confidence"] > 0.0


# 6. Test API POST /api/v1/ai/review-discrepancy
def test_api_review_discrepancy_endpoint():
    payload = {
        "reconciliation_result": {
            "gst_record": {
                "invoice_number": "INV-100",
                "gstin": "27AAAAA0000A1Z5",
                "total_invoice_value": 1180.0,
            },
            "erp_record": {
                "invoice_number": "INV-100",
                "gstin": "27AAAAA0000A1Z5",
                "total_invoice_value": 1500.0,
            },
            "classification": "DISCREPANCY",
            "field_differences": [
                {
                    "field_name": "total_invoice_value",
                    "gst_value": 1180.0,
                    "erp_value": 1500.0,
                    "difference_amount": 320.0,
                    "is_within_tolerance": False,
                    "is_critical": True,
                }
            ],
        }
    }

    response = client.post("/api/v1/ai/review-discrepancy", json=payload)
    assert response.status_code == 200

    data = response.json()
    assert "Financial discrepancy detected" in data["explanation"]
    assert "audit_remark" in data
    assert "recommended_action" in data

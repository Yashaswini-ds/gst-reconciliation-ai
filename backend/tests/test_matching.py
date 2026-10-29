import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.mapping.schemas import CanonicalInvoice
from app.matching.engine import matching_engine
from app.matching.schemas import MatchClassification, ReconciliationConfig, UnmatchedReason

client = TestClient(app)


def make_invoice(
    inv_num: str = "INV-100",
    gstin: str = "27AAAAA0000A1Z5",
    inv_date: str = "2024-04-01",
    taxable: float = 1000.0,
    cgst: float = 90.0,
    sgst: float = 90.0,
    igst: float = 0.0,
    total: float = 1180.0,
) -> CanonicalInvoice:
    return CanonicalInvoice(
        invoice_number=inv_num,
        gstin=gstin,
        invoice_date=inv_date,
        taxable_value=taxable,
        cgst=cgst,
        sgst=sgst,
        igst=igst,
        total_invoice_value=total,
    )


# 1. Test Exact Match
def test_exact_match():
    gst_rec = make_invoice()
    erp_rec = make_invoice()

    response = matching_engine.reconcile_batch([gst_rec], [erp_rec])

    assert response.summary.exact_matches == 1
    assert response.summary.discrepancies == 0
    assert response.results[0].classification == MatchClassification.EXACT_MATCH
    assert response.results[0].requires_manual_review is False


# 2. Test Partial Match (minor non-critical date difference)
def test_partial_match_date_difference():
    gst_rec = make_invoice(inv_date="2024-04-01")
    erp_rec = make_invoice(inv_date="2024-04-05")  # Date differs

    response = matching_engine.reconcile_batch([gst_rec], [erp_rec])

    assert response.summary.partial_matches == 1
    assert response.summary.discrepancies == 0
    assert response.results[0].classification == MatchClassification.PARTIAL_MATCH


# 3. Test Discrepancy (critical total invoice value mismatch beyond tolerance)
def test_discrepancy_total_value_mismatch():
    gst_rec = make_invoice(total=1180.0)
    erp_rec = make_invoice(total=1500.0)  # Differs by 320.0 (beyond 1.0 INR tolerance)

    response = matching_engine.reconcile_batch([gst_rec], [erp_rec])

    assert response.summary.discrepancies == 1
    assert response.results[0].classification == MatchClassification.DISCREPANCY
    assert len(response.results[0].field_differences) >= 1
    assert response.results[0].field_differences[0].field_name == "total_invoice_value"


# 4. Test Unmatched MISSING_IN_ERP
def test_unmatched_missing_in_erp():
    gst_rec = make_invoice(gstin="27AAAAA0000A1Z5")
    erp_rec = make_invoice(gstin="27BBBBB0000B1Z2")  # Different GSTIN -> No candidate

    response = matching_engine.reconcile_batch([gst_rec], [erp_rec])

    assert response.summary.unmatched_missing_in_erp == 1
    assert response.summary.unmatched_missing_in_gst == 1
    
    res_gst = [r for r in response.results if r.unmatched_reason == UnmatchedReason.MISSING_IN_ERP]
    assert len(res_gst) == 1
    assert res_gst[0].classification == MatchClassification.UNMATCHED


# 5. Test Fuzzy Candidate Matching and Manual Review Routing
def test_fuzzy_candidate_matching():
    gst_rec = make_invoice(inv_num="INV-001")
    erp_rec = make_invoice(inv_num="INV001")  # Formatting variation

    config = ReconciliationConfig(fuzzy_threshold=0.80)
    response = matching_engine.reconcile_batch([gst_rec], [erp_rec], config)

    assert response.summary.exact_matches == 0
    # Field comparison sees invoice_number string difference -> Partial Match
    assert response.results[0].classification in [MatchClassification.EXACT_MATCH, MatchClassification.PARTIAL_MATCH]
    # Internal workflow flag set for fuzzy candidate
    assert response.results[0].requires_manual_review is True


# 6. Test API POST /api/v1/reconcile/run Endpoint Success
def test_api_reconcile_run_endpoint_success():
    payload = {
        "gst_records": [
            {
                "invoice_number": "INV-500",
                "gstin": "27AAAAA0000A1Z5",
                "invoice_date": "2024-05-10",
                "taxable_value": 5000.0,
                "cgst": 450.0,
                "sgst": 450.0,
                "igst": 0.0,
                "total_invoice_value": 5900.0,
            }
        ],
        "erp_records": [
            {
                "invoice_number": "INV-500",
                "gstin": "27AAAAA0000A1Z5",
                "invoice_date": "2024-05-10",
                "taxable_value": 5000.0,
                "cgst": 450.0,
                "sgst": 450.0,
                "igst": 0.0,
                "total_invoice_value": 5900.0,
            }
        ],
    }

    response = client.post("/api/v1/reconcile/run", json=payload)
    assert response.status_code == 200

    data = response.json()
    assert data["success"] is True
    assert data["summary"]["total_gst_records"] == 1
    assert data["summary"]["exact_matches"] == 1
    assert data["results"][0]["classification"] == "EXACT_MATCH"


# 7. Test API POST /api/v1/reconcile/run Empty Request
def test_api_reconcile_run_empty_records():
    payload = {"gst_records": [], "erp_records": []}
    response = client.post("/api/v1/reconcile/run", json=payload)

    assert response.status_code == 400
    data = response.json()
    assert data["detail"]["code"] == "EMPTY_DATASETS"


# 8. Test Duplicate Candidate Ambiguity
def test_duplicate_candidate_ambiguity():
    gst_rec = make_invoice(inv_num="INV-100", total=1180.0)
    erp_rec1 = make_invoice(inv_num="INV-100", total=1180.0)
    erp_rec2 = make_invoice(inv_num="INV-100", total=1180.0)  # Duplicate candidate in ERP

    response = matching_engine.reconcile_batch([gst_rec], [erp_rec1, erp_rec2])

    assert response.results[0].candidate_confidence == 0.90
    assert response.results[0].requires_manual_review is True
    assert response.summary.manual_reviews_required >= 1


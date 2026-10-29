import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.mapping.schemas import CanonicalInvoice
from app.matching.schemas import (
    BatchReconciliationResponse,
    BatchReconciliationSummary,
    MatchClassification,
    ReconciliationRecordResult,
)
from app.reports.vendor_risk_schemas import VendorRiskCategory
from app.reports.vendor_risk_service import vendor_risk_service

client = TestClient(app)


def make_inv(inv_num="INV-100", gstin="27AAAAA0000A1Z5", total=1180.0, cgst=90.0, sgst=90.0):
    return CanonicalInvoice(
        invoice_number=inv_num,
        gstin=gstin,
        invoice_date="2024-04-01",
        taxable_value=total - (cgst + sgst),
        cgst=cgst,
        sgst=sgst,
        igst=0.0,
        total_invoice_value=total,
    )


def test_vendor_risk_service_evaluation():
    # Vendor 1: High compliance (100% exact match)
    v1_rec = ReconciliationRecordResult(
        gst_record=make_inv(gstin="27AAAAA0000A1Z5"),
        erp_record=make_inv(gstin="27AAAAA0000A1Z5"),
        classification=MatchClassification.EXACT_MATCH,
    )

    # Vendor 2: Low compliance (100% discrepancy)
    v2_rec = ReconciliationRecordResult(
        gst_record=make_inv(gstin="36BBBBA1111B1Z9", total=6000.0, cgst=500.0, sgst=500.0),
        erp_record=make_inv(gstin="36BBBBA1111B1Z9", total=8000.0, cgst=500.0, sgst=500.0),
        classification=MatchClassification.DISCREPANCY,
    )

    batch_resp = BatchReconciliationResponse(
        summary=BatchReconciliationSummary(
            total_gst_records=2,
            total_erp_records=2,
            exact_matches=1,
            partial_matches=0,
            discrepancies=1,
            unmatched_missing_in_erp=0,
            unmatched_missing_in_gst=0,
            manual_reviews_required=0,
        ),
        results=[v1_rec, v2_rec],
    )

    report = vendor_risk_service.evaluate_vendor_compliance(batch_resp)
    assert report.total_vendors_evaluated == 2
    assert report.high_risk_vendors_count == 1
    assert report.low_risk_vendors_count == 1

    # Check High Risk Vendor
    v2_profile = next(p for p in report.vendor_profiles if p.gstin == "36BBBBA1111B1Z9")
    assert v2_profile.compliance_score == 0.0
    assert v2_profile.risk_category == VendorRiskCategory.HIGH_RISK
    assert v2_profile.section_16_4_warning is True


def test_api_vendor_risk_analytics_endpoint():
    v1_rec = ReconciliationRecordResult(
        gst_record=make_inv(gstin="27AAAAA0000A1Z5"),
        erp_record=make_inv(gstin="27AAAAA0000A1Z5"),
        classification=MatchClassification.EXACT_MATCH,
    )

    payload = {
        "summary": {
            "total_gst_records": 1,
            "total_erp_records": 1,
            "exact_matches": 1,
            "partial_matches": 0,
            "discrepancies": 0,
            "unmatched_missing_in_erp": 0,
            "unmatched_missing_in_gst": 0,
            "manual_reviews_required": 0,
        },
        "results": [v1_rec.model_dump()],
    }

    response = client.post("/api/v1/orchestration/vendor-risk-analytics", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["total_vendors_evaluated"] == 1
    assert data["low_risk_vendors_count"] == 1
    assert data["vendor_profiles"][0]["compliance_score"] == 100.0

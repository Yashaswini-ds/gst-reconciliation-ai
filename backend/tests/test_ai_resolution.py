import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.ai.service import ai_service
from app.ai.schemas import AIResolutionRequest, ResolutionActionType, VoucherType
from app.mapping.schemas import CanonicalInvoice
from app.matching.schemas import MatchClassification, ReconciliationRecordResult


def make_invoice(inv_num="INV-100", total=1180.0):
    return CanonicalInvoice(
        invoice_number=inv_num,
        gstin="27AAAAA0000A1Z5",
        invoice_date="2024-04-01",
        taxable_value=1000.0,
        cgst=90.0,
        sgst=90.0,
        igst=0.0,
        total_invoice_value=total,
    )


@pytest.mark.asyncio
async def test_ai_resolution_exact_match():
    # Setup exact match
    res = ReconciliationRecordResult(
        gst_record=make_invoice(),
        erp_record=make_invoice(),
        classification=MatchClassification.EXACT_MATCH,
    )

    resp = await ai_service.generate_resolution_recommendation_async(res)
    assert resp.action_type == ResolutionActionType.ACCEPT_TOLERANCE_DIFFERENCE
    assert resp.adjustment_voucher is None
    assert resp.vendor_notice is None


@pytest.mark.asyncio
async def test_ai_resolution_unmatched_gst_only():
    # Setup unmatched GST record (missing in ERP)
    res = ReconciliationRecordResult(
        gst_record=make_invoice("INV-GST", 1180.0),
        erp_record=None,
        classification=MatchClassification.UNMATCHED,
    )

    resp = await ai_service.generate_resolution_recommendation_async(res, supplier_name="Acme Corp")
    assert resp.action_type == ResolutionActionType.POST_JOURNAL_ADJUSTMENT
    assert resp.adjustment_voucher is not None
    assert resp.adjustment_voucher.voucher_type == VoucherType.JOURNAL_ENTRY
    assert "Acme Corp" in resp.adjustment_voucher.credit_account
    assert resp.vendor_notice is None


@pytest.mark.asyncio
async def test_ai_resolution_unmatched_erp_only():
    # Setup unmatched ERP record (missing in GST)
    res = ReconciliationRecordResult(
        gst_record=None,
        erp_record=make_invoice("INV-ERP", 1180.0),
        classification=MatchClassification.UNMATCHED,
    )

    resp = await ai_service.generate_resolution_recommendation_async(res, supplier_name="Acme Corp")
    assert resp.action_type == ResolutionActionType.HOLD_ITC_CLAIM
    assert resp.adjustment_voucher is not None
    assert resp.adjustment_voucher.voucher_type == VoucherType.JOURNAL_ENTRY
    assert resp.vendor_notice is not None
    assert resp.vendor_notice.recipient_gstin == "27AAAAA0000A1Z5"
    assert "INV-ERP" in resp.vendor_notice.subject


@pytest.mark.asyncio
async def test_ai_resolution_discrepancy_erp_excess():
    # Setup ERP total > GST total
    res = ReconciliationRecordResult(
        gst_record=make_invoice("INV-DISC", 1000.0),
        erp_record=make_invoice("INV-DISC", 1180.0),
        classification=MatchClassification.DISCREPANCY,
    )

    resp = await ai_service.generate_resolution_recommendation_async(res, supplier_name="Beta Corp")
    assert resp.action_type == ResolutionActionType.ISSUE_DEBIT_NOTE
    assert resp.adjustment_voucher is not None
    assert resp.adjustment_voucher.voucher_type == VoucherType.DEBIT_NOTE
    assert resp.adjustment_voucher.amount == 180.0
    assert resp.vendor_notice is not None
    assert "Beta Corp" in resp.vendor_notice.notice_body


@pytest.mark.asyncio
async def test_ai_resolution_discrepancy_gst_excess():
    # Setup GST total > ERP total
    res = ReconciliationRecordResult(
        gst_record=make_invoice("INV-DISC", 1180.0),
        erp_record=make_invoice("INV-DISC", 1000.0),
        classification=MatchClassification.DISCREPANCY,
    )

    resp = await ai_service.generate_resolution_recommendation_async(res, supplier_name="Gamma Corp")
    assert resp.action_type == ResolutionActionType.ISSUE_CREDIT_NOTE
    assert resp.adjustment_voucher is not None
    assert resp.adjustment_voucher.voucher_type == VoucherType.CREDIT_NOTE
    assert resp.adjustment_voucher.amount == 180.0


def test_api_resolution_endpoint():
    client = TestClient(app)
    # Construct request payload
    res = ReconciliationRecordResult(
        gst_record=make_invoice("INV-DISC", 1000.0),
        erp_record=make_invoice("INV-DISC", 1180.0),
        classification=MatchClassification.DISCREPANCY,
    )
    payload = {
        "reconciliation_result": res.model_dump(),
        "supplier_name": "Acme Corp"
    }

    response = client.post("/api/v1/ai/generate-resolution", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["action_type"] == ResolutionActionType.ISSUE_DEBIT_NOTE
    assert data["adjustment_voucher"]["amount"] == 180.0
    assert data["vendor_notice"] is not None


def test_api_batch_resolution_endpoint():
    client = TestClient(app)
    res1 = ReconciliationRecordResult(
        gst_record=make_invoice("INV-DISC-1", 1000.0),
        erp_record=make_invoice("INV-DISC-1", 1180.0),
        classification=MatchClassification.DISCREPANCY,
    )
    res2 = ReconciliationRecordResult(
        gst_record=make_invoice("INV-DISC-2", 1200.0),
        erp_record=make_invoice("INV-DISC-2", 1000.0),
        classification=MatchClassification.DISCREPANCY,
    )

    payload = [
        {"reconciliation_result": res1.model_dump(), "supplier_name": "Vendor A"},
        {"reconciliation_result": res2.model_dump(), "supplier_name": "Vendor B"}
    ]

    response = client.post("/api/v1/ai/batch-generate-resolutions", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    assert data[0]["action_type"] == ResolutionActionType.ISSUE_DEBIT_NOTE
    assert data[1]["action_type"] == ResolutionActionType.ISSUE_CREDIT_NOTE

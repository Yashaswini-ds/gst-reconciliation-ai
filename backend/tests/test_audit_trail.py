import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.reports.audit_logger import audit_logger
from app.reports.schemas import ReconciliationSummaryReport
from app.matching.schemas import BatchReconciliationResponse, BatchReconciliationSummary


def test_audit_logger_service_log_run():
    audit_logger.clear_history()

    batch_resp = BatchReconciliationResponse(
        summary=BatchReconciliationSummary(
            total_gst_records=10,
            total_erp_records=10,
            exact_matches=8,
            partial_matches=1,
            discrepancies=1,
            unmatched_missing_in_erp=0,
            unmatched_missing_in_gst=0,
            manual_reviews_required=1,
        ),
        results=[],
    )


    summary_rep = ReconciliationSummaryReport(
        total_gst_invoices=10,
        total_erp_invoices=10,
        match_rate_percentage=90.0,
        exact_matches_count=8,
        partial_matches_count=1,
        discrepancies_count=1,
        unmatched_count=0,
        manual_reviews_required_count=1,
        itc_claimable_amount=15000.0,
        itc_disputed_amount=1200.0,
    )

    entry = audit_logger.log_run(
        gst_filename="test_gstr2b.csv",
        erp_filename="test_erp.csv",
        batch_response=batch_resp,
        summary_report=summary_rep,
        ai_fallback_used=False,
    )

    assert entry.gst_filename == "test_gstr2b.csv"
    assert entry.total_gst_records == 10
    assert entry.itc_claimable_amount == 15000.0

    history = audit_logger.get_audit_history()
    assert len(history) == 1
    assert history[0].audit_id == entry.audit_id


def test_api_audit_trail_endpoint():
    client = TestClient(app)
    audit_logger.clear_history()

    batch_resp = BatchReconciliationResponse(
        summary=BatchReconciliationSummary(

            total_gst_records=5,
            total_erp_records=5,
            exact_matches=5,
            partial_matches=0,
            discrepancies=0,
            unmatched_missing_in_erp=0,
            unmatched_missing_in_gst=0,
            manual_reviews_required=0,
        ),
        results=[],
    )

    summary_rep = ReconciliationSummaryReport(
        total_gst_invoices=5,
        total_erp_invoices=5,
        match_rate_percentage=100.0,
        exact_matches_count=5,
        partial_matches_count=0,
        discrepancies_count=0,
        unmatched_count=0,
        manual_reviews_required_count=0,
        itc_claimable_amount=8000.0,
        itc_disputed_amount=0.0,
    )

    audit_logger.log_run(
        gst_filename="sample_gst.csv",
        erp_filename="sample_erp.csv",
        batch_response=batch_resp,
        summary_report=summary_rep,
    )

    response = client.get("/api/v1/orchestration/audit-trail")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) >= 1
    assert data[0]["gst_filename"] == "sample_gst.csv"

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.orchestration.service import orchestration_service
from app.reports.service import reporting_service

client = TestClient(app)


# 1. Test full end-to-end orchestration service
def test_end_to_end_orchestration_service():
    gst_csv = (
        "GSTIN of Supplier,Invoice Number,Invoice Date,Taxable Value,CGST,SGST,IGST,Invoice Value\n"
        "27AAAAA0000A1Z5,INV-100,01/04/2024,1000.00,90.00,90.00,0.00,1180.00\n"
        "27AAAAA0000A1Z5,INV-200,02/04/2024,2000.00,180.00,180.00,0.00,2360.00\n"
    ).encode("utf-8")

    erp_csv = (
        "Vendor_GSTIN,ERP_Doc_Num,Doc_Date,Taxable_Amt,CGST_Amt,SGST_Amt,IGST_Amt,Gross_Val\n"
        "27AAAAA0000A1Z5,INV-100,01/04/2024,1000.00,90.00,90.00,0.00,1180.00\n"
        "27AAAAA0000A1Z5,INV-200,02/04/2024,2000.00,180.00,180.00,0.00,2800.00\n"  # Value discrepancy
    ).encode("utf-8")

    pipeline_resp = orchestration_service.run_full_pipeline(
        gst_filename="gstr2b.csv",
        gst_bytes=gst_csv,
        erp_filename="purchase_register.csv",
        erp_bytes=erp_csv,
        include_ai_reviews=True,
    )

    assert pipeline_resp.success is True
    assert pipeline_resp.gst_file_metadata.row_count == 2
    assert pipeline_resp.erp_file_metadata.row_count == 2

    summary = pipeline_resp.batch_summary
    assert summary.exact_matches == 1
    assert summary.discrepancies == 1

    analytics = pipeline_resp.report_analytics
    assert analytics.match_rate_percentage == 50.0
    assert analytics.itc_claimable_amount == 180.0  # 90+90 from INV-100

    assert pipeline_resp.ai_reviews is not None
    assert len(pipeline_resp.ai_reviews) == 1  # 1 non-exact review for INV-200


# 2. Test reporting CSV export string generation
def test_reporting_csv_export():
    gst_csv = "gstin,invoice_no,total_val\n27AAAAA0000A1Z5,INV-100,1180.00\n".encode("utf-8")
    erp_csv = "gstin,invoice_no,total_val\n27AAAAA0000A1Z5,INV-100,1180.00\n".encode("utf-8")

    pipeline_resp = orchestration_service.run_full_pipeline(
        "gst.csv", gst_csv, "erp.csv", erp_csv
    )

    # Convert to BatchReconciliationResponse structure for export
    from app.matching.schemas import BatchReconciliationResponse
    batch_resp = BatchReconciliationResponse(
        success=True,
        summary=pipeline_resp.batch_summary,
        results=pipeline_resp.results,
    )

    csv_output = reporting_service.export_reconciliation_csv(batch_resp)
    assert "GSTIN,GST_Invoice_Number,ERP_Invoice_Number" in csv_output
    assert "27AAAAA0000A1Z5,INV-100,INV-100" in csv_output
    assert "EXACT_MATCH" in csv_output


# 3. Test API POST /api/v1/orchestration/reconcile-files
def test_api_reconcile_files_endpoint():
    gst_content = "gstin,invoice_no,total_val\n27AAAAA0000A1Z5,INV-500,12000.00\n".encode("utf-8")
    erp_content = "gstin,invoice_no,total_val\n27AAAAA0000A1Z5,INV-500,12000.00\n".encode("utf-8")

    response = client.post(
        "/api/v1/orchestration/reconcile-files",
        files={
            "gst_file": ("gst.csv", gst_content, "text/csv"),
            "erp_file": ("erp.csv", erp_content, "text/csv"),
        },
    )

    assert response.status_code == 200
    data = response.json()

    assert data["success"] is True
    assert data["batch_summary"]["exact_matches"] == 1
    assert data["report_analytics"]["match_rate_percentage"] == 100.0


# 4. Test API POST /api/v1/orchestration/export-csv
def test_api_export_csv_endpoint():
    batch_payload = {
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
        "results": [
            {
                "gst_record": {
                    "invoice_number": "INV-100",
                    "gstin": "27AAAAA0000A1Z5",
                    "total_invoice_value": 1180.0,
                },
                "erp_record": {
                    "invoice_number": "INV-100",
                    "gstin": "27AAAAA0000A1Z5",
                    "total_invoice_value": 1180.0,
                },
                "classification": "EXACT_MATCH",
            }
        ],
    }

    response = client.post("/api/v1/orchestration/export-csv", json=batch_payload)
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    assert "reconciliation_audit_report.csv" in response.headers["content-disposition"]
    assert "EXACT_MATCH" in response.text

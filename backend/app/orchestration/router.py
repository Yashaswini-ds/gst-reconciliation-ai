import json
from typing import Optional
from fastapi import APIRouter, File, Form, HTTPException, Response, UploadFile, status

from app.matching.schemas import BatchReconciliationResponse
from app.orchestration.schemas import FullPipelineResponse
from app.orchestration.service import orchestration_service
from app.reports.service import reporting_service
from app.reports.vendor_risk_schemas import VendorRiskAnalyticsReport

router = APIRouter(prefix="/orchestration", tags=["Pipeline Orchestration & Audit Export"])



@router.post(
    "/reconcile-files",
    response_model=FullPipelineResponse,
    status_code=status.HTTP_200_OK,
    summary="End-to-End Reconciliation over Uploaded GST & ERP Files",
    description="Uploads GST Portal and ERP invoice files, ingests, normalizes, matches records, generates AI reviews, and returns complete summary analytics.",
)
async def reconcile_files_endpoint(
    gst_file: UploadFile = File(..., description="GST Portal GSTR-2B/2A invoice file (.csv, .xlsx, .xls)"),
    erp_file: UploadFile = File(..., description="ERP Purchase Register invoice file (.csv, .xlsx, .xls)"),
    include_ai_reviews: bool = True,
    gst_mapping: Optional[str] = Form(None, description="GST column mapping JSON string"),
    erp_mapping: Optional[str] = Form(None, description="ERP column mapping JSON string"),
):
    """API endpoint executing end-to-end reconciliation over two uploaded invoice files."""
    if not gst_file or not gst_file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "MISSING_GST_FILE", "message": "GST Portal invoice file is required."},
        )

    if not erp_file or not erp_file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "MISSING_ERP_FILE", "message": "ERP Purchase Register file is required."},
        )

    gst_map_dict = None
    if gst_mapping:
        try:
            gst_map_dict = json.loads(gst_mapping)
        except json.JSONDecodeError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"code": "INVALID_GST_MAPPING", "message": "GST column mapping is not valid JSON."},
            )

    erp_map_dict = None
    if erp_mapping:
        try:
            erp_map_dict = json.loads(erp_mapping)
        except json.JSONDecodeError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"code": "INVALID_ERP_MAPPING", "message": "ERP column mapping is not valid JSON."},
            )

    try:
        gst_bytes = await gst_file.read()
        erp_bytes = await erp_file.read()

        response = orchestration_service.run_full_pipeline(
            gst_filename=gst_file.filename,
            gst_bytes=gst_bytes,
            erp_filename=erp_file.filename,
            erp_bytes=erp_bytes,
            include_ai_reviews=include_ai_reviews,
            gst_mapping=gst_map_dict,
            erp_mapping=erp_map_dict,
        )
        return response
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"code": "PIPELINE_ORCHESTRATION_ERROR", "message": f"Orchestration pipeline failed: {str(exc)}"},
        )


@router.post(
    "/export-csv",
    status_code=status.HTTP_200_OK,
    summary="Export Reconciliation Results to CSV Report",
    description="Generates downloadable CSV reconciliation audit report from batch reconciliation results.",
)
async def export_reconciliation_csv_endpoint(batch_response: BatchReconciliationResponse):
    """API endpoint to export reconciliation batch results to downloadable CSV."""
    try:
        csv_content = reporting_service.export_reconciliation_csv(batch_response)
        return Response(
            content=csv_content,
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=reconciliation_audit_report.csv"},
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"code": "CSV_EXPORT_ERROR", "message": f"CSV export failed: {str(exc)}"},
        )


@router.get(
    "/audit-trail",
    status_code=status.HTTP_200_OK,
    summary="Retrieve Reconciliation Run Audit History",
    description="Retrieves compliance audit logs for historical reconciliation pipeline executions.",
)
async def get_audit_trail_endpoint():
    """API endpoint to fetch reconciliation audit history."""
    from app.reports.audit_logger import audit_logger
    return audit_logger.get_audit_history()


@router.post(
    "/vendor-risk-analytics",
    response_model=VendorRiskAnalyticsReport,
    status_code=status.HTTP_200_OK,
    summary="Generate Vendor Compliance Risk Analytics",
    description="Evaluates reconciliation results grouped by supplier GSTIN to compute vendor compliance scores (0-100) and Section 16(4) ITC risk alerts.",
)
async def vendor_risk_analytics_endpoint(batch_response: BatchReconciliationResponse):
    """API endpoint to generate supplier risk profiles and compliance scores."""
    from app.reports.vendor_risk_service import vendor_risk_service
    from app.reports.vendor_risk_schemas import VendorRiskAnalyticsReport
    try:
        return vendor_risk_service.evaluate_vendor_compliance(batch_response)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"code": "VENDOR_RISK_ERROR", "message": f"Vendor risk evaluation failed: {str(exc)}"},
        )



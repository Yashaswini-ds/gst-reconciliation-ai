from fastapi import APIRouter, HTTPException, status

from app.matching.engine import matching_engine
from app.matching.schemas import BatchReconciliationRequest, BatchReconciliationResponse

router = APIRouter(prefix="/reconcile", tags=["Matching & Reconciliation"])


@router.post(
    "/run",
    response_model=BatchReconciliationResponse,
    status_code=status.HTTP_200_OK,
    summary="Execute GST vs ERP invoice reconciliation run",
    description="Compares canonical GST and ERP records, candidate matching, tolerance checks, and assigns primary reconciliation classifications.",
)
async def run_reconciliation_endpoint(request: BatchReconciliationRequest):
    """API endpoint to run batch reconciliation between GST and ERP records."""
    if not request.gst_records and not request.erp_records:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "EMPTY_DATASETS", "message": "Request contains no GST or ERP records to reconcile."},
        )

    try:
        response = matching_engine.reconcile_batch(
            gst_records=request.gst_records,
            erp_records=request.erp_records,
            config=request.config,
        )
        return response
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"code": "RECONCILIATION_ERROR", "message": f"An error occurred during reconciliation: {str(exc)}"},
        )

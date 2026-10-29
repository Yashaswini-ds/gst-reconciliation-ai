from fastapi import APIRouter, HTTPException, status

from app.ai.schemas import (
    AICandidateResolutionRequest,
    AICandidateResolutionResponse,
    AIDiscrepancyReviewRequest,
    AIDiscrepancyReviewResponse,
    AIPairwiseSourceRoleRequest,
    AIPairwiseSourceRoleResponse,
    AIResolutionRequest,
    AIResolutionResponse,
)
from app.ai.service import ai_service
from typing import List

router = APIRouter(prefix="/ai", tags=["AI Assistance & Discrepancy Review"])


@router.post(
    "/resolve-ambiguity",
    response_model=AICandidateResolutionResponse,
    status_code=status.HTTP_200_OK,
    summary="AI Candidate Ambiguity Resolution",
    description="Evaluates structured record evidence to resolve candidate matching ambiguity when deterministic methods are insufficient.",
)
async def resolve_ambiguity_endpoint(request: AICandidateResolutionRequest):
    """API endpoint to perform AI candidate ambiguity resolution."""
    if not request.candidate_erp_records:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "EMPTY_CANDIDATES", "message": "Request contains no candidate ERP records to evaluate."},
        )

    try:
        response = await ai_service.resolve_candidate_ambiguity_async(
            gst_record=request.gst_record, candidate_erp_records=request.candidate_erp_records
        )
        return response

    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"code": "AI_RESOLUTION_ERROR", "message": f"AI candidate resolution failed: {str(exc)}"},
        )


@router.post(
    "/review-discrepancy",
    response_model=AIDiscrepancyReviewResponse,
    status_code=status.HTTP_200_OK,
    summary="AI Post-Reconciliation Discrepancy Review",
    description="Generates human-readable explanations, audit remarks, and recommended actions for non-exact reconciliation results.",
)
async def review_discrepancy_endpoint(request: AIDiscrepancyReviewRequest):
    """API endpoint to generate AI post-reconciliation review remarks."""
    try:
        response = await ai_service.review_discrepancy_async(request.reconciliation_result)
        return response

    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"code": "AI_REVIEW_ERROR", "message": f"AI discrepancy review failed: {str(exc)}"},
        )


@router.post(
    "/generate-resolution",
    response_model=AIResolutionResponse,
    status_code=status.HTTP_200_OK,
    summary="AI Accounting Resolution Voucher & Notice",
    description="Generates recommended tax compliance action, ledger adjustment entry voucher, and formal notice templates to vendor.",
)
async def generate_resolution_endpoint(request: AIResolutionRequest):
    """API endpoint to generate resolution recommendation and accounting voucher."""
    try:
        response = await ai_service.generate_resolution_recommendation_async(
            request.reconciliation_result, request.supplier_name
        )
        return response
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"code": "AI_RESOLUTION_VOUCHER_ERROR", "message": f"AI resolution recommendation failed: {str(exc)}"},
        )


@router.post(
    "/batch-generate-resolutions",
    response_model=List[AIResolutionResponse],
    status_code=status.HTTP_200_OK,
    summary="Batch AI Accounting Resolution Vouchers & Notices",
    description="Processes multiple reconciliation results in batch to generate ledger adjustment vouchers and supplier notice drafts.",
)
async def batch_generate_resolutions_endpoint(requests: List[AIResolutionRequest]):
    """API endpoint to batch generate resolution recommendations."""
    try:
        results = [req.reconciliation_result for req in requests]
        response = await ai_service.batch_generate_resolutions_async(results)
        return response
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"code": "AI_BATCH_RESOLUTION_ERROR", "message": f"AI batch resolution recommendation failed: {str(exc)}"},
        )


@router.post(
    "/detect-source-role",
    response_model=AIPairwiseSourceRoleResponse,
    status_code=status.HTTP_200_OK,
    summary="AI File Source Role Detection",
    description="Evaluates GST and ERP column headers pairwise to semantically classify roles and assignment validity.",
)
async def detect_source_role_endpoint(request: AIPairwiseSourceRoleRequest):
    """API endpoint to detect file source roles pairwise based on column headers."""
    try:
        response = await ai_service.detect_source_role_async(request.gst_columns, request.erp_columns)
        return response
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"code": "SOURCE_ROLE_ERROR", "message": f"Source role detection failed: {str(exc)}"},
        )


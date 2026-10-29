from fastapi import APIRouter, HTTPException, status

from app.mapping.schemas import (
    NormalizeRequest,
    NormalizedDatasetResponse,
    DetectMappingRequest,
    DetectMappingResponse,
)
from app.mapping.service import mapping_service

router = APIRouter(prefix="/mapping", tags=["Mapping & Normalization"])


@router.post(
    "/normalize",
    response_model=NormalizedDatasetResponse,
    status_code=status.HTTP_200_OK,
    summary="Normalize raw invoice records to Canonical Invoice Schema",
    description="Auto-detects column mappings and applies controlled, field-specific normalization rules to raw invoice records.",
)
async def normalize_dataset_endpoint(request: NormalizeRequest):
    """API endpoint to map and normalize a dataset of raw invoice records."""
    if not request.records:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "EMPTY_RECORDS", "message": "Request contains no raw records to normalize."},
        )

    try:
        canonical_records, mapping_used = mapping_service.normalize_dataset(
            records=request.records, custom_config=request.column_mapping
        )

        valid_count = sum(
            1 for rec in canonical_records if rec.invoice_number != "" and rec.gstin != ""
        )

        return NormalizedDatasetResponse(
            success=True,
            total_records=len(canonical_records),
            valid_records_count=valid_count,
            column_mapping_used=mapping_used,
            records=canonical_records,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"code": "NORMALIZATION_ERROR", "message": f"Failed to normalize dataset: {str(exc)}"},
        )


@router.post(
    "/detect",
    response_model=DetectMappingResponse,
    status_code=status.HTTP_200_OK,
    summary="Detect column mappings dynamically for a list of headers (M7.5)",
    description="Analyzes file column headers to auto-detect canonical fields using deterministic aliases and AI Gateway mapping suggestions.",
)
async def detect_column_mappings_endpoint(request: DetectMappingRequest):
    """API endpoint to detect column mappings and return structured confidence details."""
    try:
        detailed_mappings = await mapping_service.detect_column_mappings_detailed(
            available_columns=request.columns,
            enable_ai=request.enable_ai,
        )
        return DetectMappingResponse(
            success=True,
            mappings=detailed_mappings,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"code": "MAPPING_DETECTION_ERROR", "message": f"Failed to detect column mappings: {str(exc)}"},
        )

from enum import Enum
from typing import Any, List, Optional
from pydantic import BaseModel, Field

from app.mapping.schemas import CanonicalInvoice


class MatchClassification(str, Enum):
    EXACT_MATCH = "EXACT_MATCH"
    PARTIAL_MATCH = "PARTIAL_MATCH"
    DISCREPANCY = "DISCREPANCY"
    UNMATCHED = "UNMATCHED"


class UnmatchedReason(str, Enum):
    MISSING_IN_ERP = "MISSING_IN_ERP"
    MISSING_IN_GST = "MISSING_IN_GST"


class FieldDifference(BaseModel):
    """Details of a field-level discrepancy between GST and ERP records."""

    field_name: str = Field(..., description="Canonical field name")
    gst_value: Optional[Any] = Field(None, description="Value present in GST record")
    erp_value: Optional[Any] = Field(None, description="Value present in ERP record")
    difference_amount: Optional[float] = Field(None, description="Numerical difference if numeric field")
    is_within_tolerance: bool = Field(True, description="True if difference is within configured tolerance")
    is_critical: bool = Field(False, description="True if field is configured as a critical financial field")


class ReconciliationConfig(BaseModel):
    """Configuration settings for matching tolerances and rules."""

    amount_tolerance_inr: float = Field(1.0, ge=0.0, description="Absolute INR tolerance for financial amounts")
    fuzzy_threshold: float = Field(0.80, ge=0.0, le=1.0, description="Minimum fuzzy candidate similarity threshold")
    critical_fields: List[str] = Field(
        default=["total_invoice_value", "taxable_value"],
        description="Fields where tolerance breach causes DISCREPANCY classification",
    )
    required_fields: List[str] = Field(
        default=["gstin", "invoice_number"],
        description="Fields required to establish exact match candidate identification",
    )


class ReconciliationRecordResult(BaseModel):
    """Detailed reconciliation result for a single invoice pair or unmatched record."""

    gst_record: Optional[CanonicalInvoice] = Field(None, description="GST Portal canonical invoice record")
    erp_record: Optional[CanonicalInvoice] = Field(None, description="ERP canonical invoice record")
    classification: MatchClassification = Field(..., description="Final primary reconciliation classification")
    unmatched_reason: Optional[UnmatchedReason] = Field(None, description="Reason if record is UNMATCHED")
    requires_manual_review: bool = Field(False, description="Internal workflow state flag for ambiguous candidates")
    candidate_confidence: float = Field(1.0, ge=0.0, le=1.0, description="Candidate identification confidence score")
    field_differences: List[FieldDifference] = Field(default=[], description="List of field-level differences")
    remarks: List[str] = Field(default=[], description="Rule evaluation notes and remarks")


class BatchReconciliationRequest(BaseModel):
    """API payload model for executing batch reconciliation."""

    gst_records: List[CanonicalInvoice] = Field(..., description="Normalized GST Portal records")
    erp_records: List[CanonicalInvoice] = Field(..., description="Normalized ERP records")
    config: Optional[ReconciliationConfig] = Field(None, description="Optional custom matching configuration")


class BatchReconciliationSummary(BaseModel):
    """Summary metrics of a batch reconciliation run."""

    total_gst_records: int = Field(...)
    total_erp_records: int = Field(...)
    exact_matches: int = Field(0)
    partial_matches: int = Field(0)
    discrepancies: int = Field(0)
    unmatched_missing_in_erp: int = Field(0)
    unmatched_missing_in_gst: int = Field(0)
    manual_reviews_required: int = Field(0)


class BatchReconciliationResponse(BaseModel):
    """API response model for batch reconciliation run."""

    success: bool = True
    summary: BatchReconciliationSummary
    results: List[ReconciliationRecordResult]

from pydantic import BaseModel, Field


class ReconciliationSummaryReport(BaseModel):
    """Aggregated summary report metrics for a reconciliation run."""

    total_gst_invoices: int = Field(..., ge=0)
    total_erp_invoices: int = Field(..., ge=0)
    match_rate_percentage: float = Field(..., ge=0.0, le=100.0)
    exact_matches_count: int = Field(..., ge=0)
    partial_matches_count: int = Field(..., ge=0)
    discrepancies_count: int = Field(..., ge=0)
    unmatched_count: int = Field(..., ge=0)
    manual_reviews_required_count: int = Field(..., ge=0)
    itc_claimable_amount: float = Field(..., description="Total ITC amount eligible for claim (EXACT + PARTIAL)")
    itc_disputed_amount: float = Field(..., description="Total ITC amount blocked due to discrepancies or missing ERP")

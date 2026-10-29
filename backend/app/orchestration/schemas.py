from typing import List, Optional
from pydantic import BaseModel, Field

from app.ai.schemas import AIDiscrepancyReviewResponse
from app.ingestion.schemas import IngestionMetadata
from app.matching.schemas import BatchReconciliationSummary, ReconciliationRecordResult
from app.reports.schemas import ReconciliationSummaryReport


class FullPipelineResponse(BaseModel):
    """Unified API response model for end-to-end reconciliation run."""

    success: bool = True
    gst_file_metadata: IngestionMetadata
    erp_file_metadata: IngestionMetadata
    batch_summary: BatchReconciliationSummary
    report_analytics: ReconciliationSummaryReport
    results: List[ReconciliationRecordResult]
    ai_reviews: Optional[List[AIDiscrepancyReviewResponse]] = Field(None, description="AI reviews attached to non-exact records")

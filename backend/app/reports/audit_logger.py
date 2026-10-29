from datetime import datetime, timezone
import uuid
from typing import List, Optional

from pydantic import BaseModel, Field

from app.matching.schemas import BatchReconciliationResponse
from app.reports.schemas import ReconciliationSummaryReport


class AuditTrailEntry(BaseModel):
    """Structured audit log entry for tax compliance and run history tracking."""

    audit_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    gst_filename: str
    erp_filename: str
    total_gst_records: int
    total_erp_records: int
    exact_matches: int
    partial_matches: int
    discrepancies: int
    unmatched: int
    itc_claimable_amount: float
    itc_disputed_amount: float
    ai_fallback_used: bool = False
    full_pipeline_response: Optional[dict] = None


class AuditLoggerService:
    """Service logging reconciliation run audit records for compliance auditing."""

    def __init__(self):
        self._history: List[AuditTrailEntry] = []

    def log_run(
        self,
        gst_filename: str,
        erp_filename: str,
        batch_response: BatchReconciliationResponse,
        summary_report: ReconciliationSummaryReport,
        ai_fallback_used: bool = False,
        full_pipeline_response: Optional[dict] = None,
    ) -> AuditTrailEntry:
        """Records an audit trail entry for a completed reconciliation batch run."""
        entry = AuditTrailEntry(
            gst_filename=gst_filename or "uploaded_gst.csv",
            erp_filename=erp_filename or "uploaded_erp.csv",
            total_gst_records=summary_report.total_gst_invoices,
            total_erp_records=summary_report.total_erp_invoices,
            exact_matches=summary_report.exact_matches_count,
            partial_matches=summary_report.partial_matches_count,
            discrepancies=summary_report.discrepancies_count,
            unmatched=summary_report.unmatched_count,
            itc_claimable_amount=summary_report.itc_claimable_amount,
            itc_disputed_amount=summary_report.itc_disputed_amount,
            ai_fallback_used=ai_fallback_used,
            full_pipeline_response=full_pipeline_response,
        )
        self._history.insert(0, entry)  # Prepend latest first
        return entry

    def get_audit_history(self) -> List[AuditTrailEntry]:
        """Returns ordered audit trail history."""
        return list(self._history)

    def clear_history(self):
        """Resets audit trail history (used for testing)."""
        self._history.clear()


audit_logger = AuditLoggerService()

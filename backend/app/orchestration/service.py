from typing import List, Optional

from app.ai.schemas import AIDiscrepancyReviewResponse
from app.ai.service import ai_service
from app.ingestion.service import ingestion_service
from app.mapping.service import mapping_service
from app.matching.engine import matching_engine
from app.matching.schemas import MatchClassification, ReconciliationConfig
from app.orchestration.schemas import FullPipelineResponse
from app.reports.service import reporting_service


class OrchestrationService:
    """Orchestrates end-to-end file ingestion, normalization, deterministic matching, AI reviews, and reporting."""

    def run_full_pipeline(
        self,
        gst_filename: str,
        gst_bytes: bytes,
        erp_filename: str,
        erp_bytes: bytes,
        config: Optional[ReconciliationConfig] = None,
        include_ai_reviews: bool = True,
        gst_mapping: Optional[dict] = None,
        erp_mapping: Optional[dict] = None,
    ) -> FullPipelineResponse:
        """Executes the complete 10-step reconciliation pipeline over uploaded GST and ERP files."""
        # 1. Ingestion Stage (M1)
        gst_meta, gst_df = ingestion_service.ingest_file(gst_filename, gst_bytes)
        erp_meta, erp_df = ingestion_service.ingest_file(erp_filename, erp_bytes)

        # 2. Normalization & Canonical Schema Mapping Stage (M2)
        gst_raw_records = gst_df.to_dict(orient="records")
        erp_raw_records = erp_df.to_dict(orient="records")

        gst_canonicals, _ = mapping_service.normalize_dataset(
            gst_raw_records, column_mapping_override=gst_mapping
        )
        erp_canonicals, _ = mapping_service.normalize_dataset(
            erp_raw_records, column_mapping_override=erp_mapping
        )

        # 3. Deterministic Matching & Candidate Generation Stage (M3)
        batch_resp = matching_engine.reconcile_batch(
            gst_records=gst_canonicals,
            erp_records=erp_canonicals,
            config=config,
        )

        # 4. Post-Reconciliation AI Discrepancy Review Stage (M4)
        ai_reviews: Optional[List[AIDiscrepancyReviewResponse]] = None
        if include_ai_reviews:
            ai_reviews = []
            for res in batch_resp.results:
                if res.classification != MatchClassification.EXACT_MATCH:
                    review = ai_service.review_discrepancy(res)
                    ai_reviews.append(review)

        # 5. Reporting Analytics Stage (M5)
        analytics_report = reporting_service.generate_summary_report(batch_resp)

        # 6. Compliance Audit Trail Logging (M9)
        from app.reports.audit_logger import audit_logger
        pipeline_resp_obj = FullPipelineResponse(
            success=True,
            gst_file_metadata=gst_meta,
            erp_file_metadata=erp_meta,
            batch_summary=batch_resp.summary,
            report_analytics=analytics_report,
            results=batch_resp.results,
            ai_reviews=ai_reviews,
        )
        audit_logger.log_run(
            gst_filename=gst_filename,
            erp_filename=erp_filename,
            batch_response=batch_resp,
            summary_report=analytics_report,
            ai_fallback_used=False,
            full_pipeline_response=pipeline_resp_obj.model_dump(),
        )

        return FullPipelineResponse(
            success=True,
            gst_file_metadata=gst_meta,
            erp_file_metadata=erp_meta,
            batch_summary=batch_resp.summary,
            report_analytics=analytics_report,
            results=batch_resp.results,
            ai_reviews=ai_reviews,
        )



orchestration_service = OrchestrationService()

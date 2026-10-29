import csv
import io
from app.matching.schemas import BatchReconciliationResponse, MatchClassification
from app.reports.schemas import ReconciliationSummaryReport


class ReportingService:
    """Service handling reconciliation analytics, summary metrics, and CSV audit reports."""

    def generate_summary_report(
        self, batch_response: BatchReconciliationResponse
    ) -> ReconciliationSummaryReport:
        """Computes summary metrics and ITC claim totals from reconciliation results."""
        summary = batch_response.summary
        total_processed = summary.total_gst_records

        matched_count = summary.exact_matches + summary.partial_matches
        match_rate = round((matched_count / total_processed * 100), 2) if total_processed > 0 else 0.0

        itc_claimable = 0.0
        itc_disputed = 0.0

        for res in batch_response.results:
            if res.gst_record:
                # Total ITC amount = CGST + SGST + IGST
                gst_itc = (
                    res.gst_record.cgst + res.gst_record.sgst + res.gst_record.igst
                )

                if res.classification in [
                    MatchClassification.EXACT_MATCH,
                    MatchClassification.PARTIAL_MATCH,
                ]:
                    itc_claimable += gst_itc
                else:
                    itc_disputed += gst_itc

        return ReconciliationSummaryReport(
            total_gst_invoices=summary.total_gst_records,
            total_erp_invoices=summary.total_erp_records,
            match_rate_percentage=match_rate,
            exact_matches_count=summary.exact_matches,
            partial_matches_count=summary.partial_matches,
            discrepancies_count=summary.discrepancies,
            unmatched_count=summary.unmatched_missing_in_erp + summary.unmatched_missing_in_gst,
            manual_reviews_required_count=summary.manual_reviews_required,
            itc_claimable_amount=round(itc_claimable, 2),
            itc_disputed_amount=round(itc_disputed, 2),
        )

    def export_reconciliation_csv(
        self, batch_response: BatchReconciliationResponse
    ) -> str:
        """Exports reconciliation results into a formatted CSV text stream."""
        output = io.StringIO()
        writer = csv.writer(output)

        # Write CSV Header
        writer.writerow([
            "GSTIN",
            "GST_Invoice_Number",
            "ERP_Invoice_Number",
            "GST_Invoice_Date",
            "GST_Total_Value",
            "ERP_Total_Value",
            "Classification",
            "Unmatched_Reason",
            "Requires_Manual_Review",
            "Difference_Notes",
        ])

        # Write Data Rows
        for res in batch_response.results:
            gstin = res.gst_record.gstin if res.gst_record else (res.erp_record.gstin if res.erp_record else "")
            gst_inv = res.gst_record.invoice_number if res.gst_record else ""
            erp_inv = res.erp_record.invoice_number if res.erp_record else ""
            gst_date = res.gst_record.invoice_date if res.gst_record else ""
            gst_total = res.gst_record.total_invoice_value if res.gst_record else 0.0
            erp_total = res.erp_record.total_invoice_value if res.erp_record else 0.0
            classification = res.classification.value
            unmatched_reason = res.unmatched_reason.value if res.unmatched_reason else ""
            manual_review = "YES" if res.requires_manual_review else "NO"

            diff_notes = "; ".join(
                f"{d.field_name}: diff={d.difference_amount}" if d.difference_amount is not None else f"{d.field_name} mismatch"
                for d in res.field_differences
            )

            writer.writerow([
                gstin,
                gst_inv,
                erp_inv,
                gst_date,
                gst_total,
                erp_total,
                classification,
                unmatched_reason,
                manual_review,
                diff_notes,
            ])

        return output.getvalue()


reporting_service = ReportingService()

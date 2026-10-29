from typing import Dict, List

from app.matching.schemas import BatchReconciliationResponse, MatchClassification
from app.reports.vendor_risk_schemas import (
    VendorRiskAnalyticsReport,
    VendorRiskCategory,
    VendorRiskProfile,
)


class VendorRiskService:
    """Service computing vendor compliance risk scores and Section 16(4) ITC risk analytics."""

    def evaluate_vendor_compliance(
        self, batch_response: BatchReconciliationResponse
    ) -> VendorRiskAnalyticsReport:
        """Groups batch reconciliation results by supplier GSTIN and evaluates compliance risk profiles."""
        vendor_data: Dict[str, dict] = {}

        for res in batch_response.results:
            gstin = res.gst_record.gstin if res.gst_record else (res.erp_record.gstin if res.erp_record else "UNKNOWN_VENDOR")
            gstin = gstin.strip().upper()

            if gstin not in vendor_data:
                vendor_data[gstin] = {
                    "total_invoices": 0,
                    "exact": 0,
                    "partial": 0,
                    "discrepancy": 0,
                    "unmatched": 0,
                    "claimable_itc": 0.0,
                    "disputed_itc": 0.0,
                }

            v = vendor_data[gstin]
            v["total_invoices"] += 1

            # Extract tax components
            gst_itc = 0.0
            if res.gst_record:
                gst_itc = res.gst_record.cgst + res.gst_record.sgst + res.gst_record.igst

            if res.classification == MatchClassification.EXACT_MATCH:
                v["exact"] += 1
                v["claimable_itc"] += gst_itc
            elif res.classification == MatchClassification.PARTIAL_MATCH:
                v["partial"] += 1
                v["claimable_itc"] += gst_itc
            elif res.classification == MatchClassification.DISCREPANCY:
                v["discrepancy"] += 1
                v["disputed_itc"] += gst_itc
            else:  # UNMATCHED
                v["unmatched"] += 1
                v["disputed_itc"] += gst_itc

        profiles: List[VendorRiskProfile] = []
        high_risk_count = 0
        med_risk_count = 0
        low_risk_count = 0
        total_disputed_itc = 0.0

        for gstin, data in vendor_data.items():
            total = data["total_invoices"]
            accurate_count = data["exact"] + data["partial"]
            
            # Match accuracy component (70% weight)
            accuracy_rate = (accurate_count / total) if total > 0 else 1.0
            
            # Calculate compliance score (0 - 100)
            score = round(accuracy_rate * 100.0, 1)

            # Categorize Risk
            if score >= 80.0:
                cat = VendorRiskCategory.LOW_RISK
                low_risk_count += 1
            elif score >= 50.0:
                cat = VendorRiskCategory.MEDIUM_RISK
                med_risk_count += 1
            else:
                cat = VendorRiskCategory.HIGH_RISK
                high_risk_count += 1

            disputed = round(data["disputed_itc"], 2)
            total_disputed_itc += disputed
            sec_16_4_warn = disputed > 5000.0 or cat == VendorRiskCategory.HIGH_RISK

            profile = VendorRiskProfile(
                gstin=gstin,
                total_invoices=total,
                exact_matches=data["exact"],
                partial_matches=data["partial"],
                discrepancies=data["discrepancy"],
                unmatched=data["unmatched"],
                claimable_itc_amount=round(data["claimable_itc"], 2),
                disputed_itc_amount=disputed,
                compliance_score=score,
                risk_category=cat,
                section_16_4_warning=sec_16_4_warn,
            )
            profiles.append(profile)

        # Sort vendor profiles by risk (High risk first)
        profiles.sort(key=lambda x: x.compliance_score)

        return VendorRiskAnalyticsReport(
            total_vendors_evaluated=len(profiles),
            high_risk_vendors_count=high_risk_count,
            medium_risk_vendors_count=med_risk_count,
            low_risk_vendors_count=low_risk_count,
            total_disputed_itc_at_risk=round(total_disputed_itc, 2),
            vendor_profiles=profiles,
        )


vendor_risk_service = VendorRiskService()

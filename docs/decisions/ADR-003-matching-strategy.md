# ADR-003: Multi-Tiered Matching & Reconciliation Strategy

## Status
Accepted (Revised)

## Context
Initial matching proposals relied on fixed percentage tiers (e.g., 100% = Exact, 80-99% = Fuzzy/AI, <80% = Manual Review). Fixed percentage thresholds are unsuitable for tax and financial reconciliation because they obscure field-specific differences and can misclassify financial discrepancies.

## Decision
Adopt a multi-tiered reconciliation strategy based on candidate identification, field-level comparison, deterministic rule evaluation, configurable field tolerances, and AI-assisted ambiguity resolution.

### Multi-Tiered Workflow:
1. **Deterministic Candidate Identification**: Exact matching on primary identifiers (`gstin`, `invoice_number`).
2. **Fuzzy Candidate Generation**: Formatting variation handling for candidate identification (never automatically establishing financial reconciliation).
3. **AI-Assisted Ambiguity Resolution**: Invoked when candidates remain ambiguous, returning structured candidate evaluation (`candidate`, `confidence`, `evidence`, `reasoning`).
4. **Deterministic Field & Tolerance Evaluation**: Comparing records field-by-field against configured rules and financial tolerances.
5. **Reconciliation Classification**: Classifying into `EXACT_MATCH`, `PARTIAL_MATCH`, `DISCREPANCY`, or `UNMATCHED` (`MISSING_IN_ERP` / `MISSING_IN_GST`).
6. **Manual Review Routing**: Insufficient confidence routes records to the internal `MANUAL_REVIEW_REQUIRED` workflow state.

## Consequences
- Eliminates risky arbitrary percentage-based reconciliation classifications.
- Guarantees deterministic financial calculations while leveraging AI for candidate ambiguity resolution and post-reconciliation discrepancy reporting.
- Supports configurable field importance and tolerance limits tailored to business requirements.

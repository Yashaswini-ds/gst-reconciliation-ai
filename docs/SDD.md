# Software Design Document (SDD) - GST Reconciliation AI

## 1. Overview
The GST Reconciliation AI application is designed to compare and reconcile invoice records between the GST Portal and an enterprise ERP system. Input files from both sources frequently present heterogeneous formats, varying column schemas, different date representations, diverse numeric formats, and formatting variations in invoice numbers. Before reconciliation, all records are normalized and mapped to a unified canonical schema.

---

## 2. Canonical Data Schema & Normalization

### 2.1 Canonical Invoice Fields
- `invoice_number`: Normalized invoice identifier
- `gstin`: 15-digit Goods and Services Tax Identification Number
- `invoice_date`: Standardized date representation
- `taxable_value`: Base taxable amount
- `cgst`: Central GST amount
- `sgst`: State GST amount
- `igst`: Integrated GST amount
- `total_invoice_value`: Gross invoice amount inclusive of taxes

### 2.2 Controlled Normalization Rules
> [!WARNING]
> Blanket normalization rules (e.g., unconditionally stripping all prefixes, mandatory zero-padding, or removing all non-alphanumeric characters) are strictly prohibited as they create false matches and alter invoice identity.

Data normalization must be:
- **Field-specific**: Applied selectively based on data type (e.g., trimming whitespace, case standardization, date formatting).
- **Controlled & Preservative**: Designed to preserve fundamental invoice identity while removing trivial formatting noise.
- **Configurable**: Configurable per dataset source where appropriate.

### 2.3 Input Ingestion & Same-File Upload Validation (M7.14)
To ensure dataset integrity and prevent artificial self-matching errors, the input ingestion layer validates the two selected physical files:
- **Same-File Detection**: Evaluates file handles and paths (`validateSelectedFiles`) to detect if the user accidentally selected the exact same physical file for both the GST Portal input and the ERP Purchase Register input.
- **Deterministic Safety Barrier**: Same-file selection triggers a deterministic frontend validation block, disabling reconciliation execution.
- **Self-Reconciliation Protection**: Prevents a file from being reconciled against itself, preserving authentic cross-system reconciliation integrity.

---

## 3. Reconciliation Decision Matrix & Matching Principles

### 3.1 Matching Principles
Record classification is **not** based on simple overall percentages (e.g., 100% = Exact, 80-99% = Fuzzy, <80% = Manual Review). Percentage-based final classification rules are strictly forbidden.

Classification is deterministically derived through:
- Candidate record identification (exact and fuzzy)
- Configured matching rules per field
- Field-level comparison against configured business rules
- Configured tolerance limits for financial fields
- Field importance ratings (critical vs. supporting)
- Structured AI evidence (where ambiguity exists)

Numerical calculations, field-level difference evaluations, and tolerance checks remain strictly deterministic. AI assists with semantic interpretation, candidate evidence evaluation, and ambiguity resolution.

### 3.2 Conceptual Matching Pipeline
The system processes records through a 10-step conceptual pipeline:

1. **Normalization**: Normalize GST and ERP records according to controlled, field-specific rules.
2. **Candidate Generation**: Generate candidate ERP records for each GST record.
3. **Deterministic Candidate Identification**: Attempt exact matching on primary identifiers (`gstin`, `invoice_number`).
4. **Fuzzy Candidate Matching**: If exact candidate identification is insufficient, execute fuzzy matching to identify candidate matches (e.g., `INV-001` vs `INV001`).
5. **AI-Assisted Matching**: If candidate ambiguity remains, invoke AI-assisted matching using structured record evidence.
6. **Field-by-Field Comparison**: Compare the selected GST and ERP records across all canonical fields.
7. **Rule & Tolerance Evaluation**: Apply configured matching rules, field requirements, and tolerance limits.
8. **Reconciliation Classification**: Assign one of the four primary reconciliation classifications.
9. **AI Discrepancy Analysis**: For non-exact results, perform post-reconciliation AI analysis to generate explanatory remarks and audit notes.
10. **Manual Review Routing**: If evidence or confidence is insufficient, route the record to `MANUAL_REVIEW_REQUIRED` internal workflow state instead of forcing a match.

---

## 4. Reconciliation Classifications

### 4.1 Primary Classifications

#### 1. `EXACT_MATCH`
A record is classified as `EXACT_MATCH` when:
- A corresponding ERP record is confidently identified.
- All configured required/critical fields match according to configured rules.
- Configured financial fields match within their configured tolerances.
- No configured discrepancy exists in any fields required for an exact match.
- Supporting fields (such as invoice date) satisfy configured comparison rules.

#### 2. `PARTIAL_MATCH`
A record is classified as `PARTIAL_MATCH` when:
- The corresponding invoice is identified with sufficient confidence, establishing the overall transaction relationship.
- One or more configured fields differ.a
- The field differences do not meet configured criteria for a major financial discrepancy (e.g., minor invoice date difference, tax head component allocation shifts where total transaction value remains consistent).

#### 3. `DISCREPANCY`
A record is classified as `DISCREPANCY` when:
- The corresponding invoice is identified with sufficient confidence.
- One or more critical/important financial values differ beyond configured tolerances.
- Examples include mismatch in `total_invoice_value`, `taxable_value`, or significant differences in `cgst`/`sgst`/`igst`.
- The engine deterministically identifies the exact conflicting fields and computes numerical differences.

#### 4. `UNMATCHED`
A record is classified as `UNMATCHED` when:
- No corresponding record can be identified with sufficient confidence.
- Unmatched records are sub-classified as either:
  - `MISSING_IN_ERP` (Present in GST Portal, absent in ERP)
  - `MISSING_IN_GST` (Present in ERP, absent in GST Portal)
- If fuzzy or AI matching cannot establish sufficient evidence, the system does not force a match.

### 4.2 Internal Workflow State: `MANUAL_REVIEW_REQUIRED`
> [!IMPORTANT]
> `MANUAL_REVIEW_REQUIRED` is an **internal workflow/review state**, not one of the four primary reconciliation classifications. Records with ambiguous candidates or low AI confidence are routed to this state for human reviewer intervention.

---

## 5. Decision Matrix Table

| Candidate Condition | Field & Financial Comparison | Result Classification |
| :--- | :--- | :--- |
| No sufficiently confident candidate | N/A | **`UNMATCHED`** (`MISSING_IN_ERP` / `MISSING_IN_GST`) |
| Candidate identified | All configured required fields & financial values satisfy rules and tolerances | **`EXACT_MATCH`** |
| Candidate identified | Differences exist, but do not meet configured major financial discrepancy criteria | **`PARTIAL_MATCH`** |
| Candidate identified | One or more configured critical financial values differ beyond tolerance | **`DISCREPANCY`** |
| Ambiguous candidate | Insufficient AI or fuzzy matching confidence | **`MANUAL_REVIEW_REQUIRED`** *(Internal Workflow State)* |

---

## 6. Fuzzy & AI-Assisted Mechanisms

### 6.1 Fuzzy Matching
- Functions strictly as a **candidate-generation and candidate-assistance mechanism** (e.g., matching `INV-001` with `INV001`).
- Fuzzy similarity scores **never** automatically establish a final financial reconciliation result.
- Produces candidate evidence and confidence scores for downstream evaluation by the deterministic reconciliation engine.

### 6.2 AI-Assisted Matching
- Invoked when deterministic and fuzzy candidate identification cannot confidently resolve an ambiguous case.
- Considers structured record evidence (`invoice_number` similarity, `gstin`, `invoice_date`, `taxable_value`, tax components, `total_invoice_value`).
- Returns structured evaluation output containing candidate identifier, confidence score, evidence, and reasoning.
- Evaluated against configurable review thresholds; low-confidence results are routed to manual review.

### 6.3 Post-Reconciliation AI Discrepancy Review
- Executed after deterministic reconciliation classification.
- Analyzes non-exact records (`PARTIAL_MATCH`, `DISCREPANCY`) to generate human-readable discrepancy explanations, AI remarks, audit notes, and recommended action steps.
- **AI does not perform basic arithmetic or tolerance calculations**; all calculations remain strictly deterministic.

### 6.4 AI Pairwise Input Source-Role Validation (M7.15)
- **Role Detection**: Evaluates column headers of both uploaded files simultaneously (`gst_columns`, `erp_columns`) to classify input roles (`GST_LIKELY`, `ERP_LIKELY`, `AMBIGUOUS`).
- **Data Minimization**: Only column header string arrays are transmitted to the LLM; no invoice row records, monetary figures, or tax values are sent.
- **Hard-Blocking Gate**: If Gemini returns swapped file roles (`gst_role == "ERP_LIKELY"` and `erp_role == "GST_LIKELY"`, or `assignment_valid == false`), reconciliation execution is hard-blocked.
- **AI-Assisted Safety Layer**: Functions strictly as an input validation assistant and does not replace deterministic reconciliation classification or financial rules.
- **Graceful Fallback**: If Gemini fails or returns low confidence (`< 0.70`), the gateway safely degrades to `AMBIGUOUS` (`assignment_valid = true`), allowing deterministic column mapping rules (M7.8) to make the final decision.

### 6.5 Actionable Discrepancy Outputs & Resolution Vouchers (M7.9)
- **Accounting Assistance**: Generates human-readable accounting resolution recommendations and vendor notices for non-exact reconciliation records (`PARTIAL_MATCH`, `DISCREPANCY`).
- **Supported Voucher Types**:
  - `PURCHASE_REGISTER_AMENDMENT`: Generated for date or metadata mismatches where invoice total is consistent.
  - `ITC_REVERSAL_JOURNAL`: Generated for tax component or value discrepancies requiring input tax credit adjustment.
- **Non-Execution Boundary**: AI provides recommendations and structured voucher suggestions only. The AI **never** executes accounting transactions, modifies financial totals, or alters primary reconciliation classifications.
- **Deterministic Data Origin**: All numerical amounts, tax subtotals, and field differences used in voucher suggestions originate 100% from pre-computed deterministic reconciliation results.

---

## 7. Field Configurability
Matching behavior must be configurable per canonical field:
- **Status**: Enabled / Disabled
- **Requirement Level**: Required / Optional
- **Field Importance**: Critical / Supporting
- **Tolerance**: Configurable absolute or percentage tolerances (where applicable)

---

## 8. AI Gateway & Hybrid LLM Architecture (M7)

### 8.1 Architectural Principle & Boundary
The application enforces a **Hybrid AI + Deterministic Design**:
- **Deterministic Engine = Financial Authority**: Retains 100% exclusive authority over numeric comparisons, tolerance checks, primary classifications (`EXACT_MATCH`, `PARTIAL_MATCH`, `DISCREPANCY`, `UNMATCHED`), ITC claimable totals, and financial audit reports.
- **AI Gateway = Intelligence Assistance**: Abstracted gateway servicing 5 narrowly scoped tasks:
  1. *AI Schema Mapping*: Header mapping suggestions for unknown columns.
  2. *AI Candidate Ambiguity Resolution*: Candidate evidence evaluation for ambiguous candidate pairs.
  3. *AI Discrepancy Review*: Human-readable discrepancy explanations, AI remarks, audit remarks, and action recommendations.
  4. *AI Pairwise Source-Role Validation (M7.15)*: Semantic input role verification (`GST_LIKELY`, `ERP_LIKELY`, `AMBIGUOUS`) for uploaded column header pairs to detect swapped file assignments (`assignment_valid = false`).
  5. *AI Actionable Discrepancy & Resolution Vouchers (M7.9)*: On-demand generation of structured accounting adjustment vouchers (`PURCHASE_REGISTER_AMENDMENT`, `ITC_REVERSAL_JOURNAL`) and vendor notices for non-exact records.

### 8.2 AI Gateway Responsibilities & Abstraction Layer
The AI Gateway decouples core application logic from specific LLM providers (OpenAI, Gemini, Anthropic, Ollama):
- **Structured JSON Contracts**: Enforces Pydantic schema parsing on all AI outputs.
- **Enterprise Data Minimization**: Never transmits full uploaded files to external LLMs; scopes payloads to isolated candidate pairs or column header arrays.
- **Deterministic Fallback**: If an AI provider fails, times out, or returns invalid schema, the system degrades gracefully to deterministic rules or sets `requires_manual_review = True`. AI failure **never** alters financial totals or primary reconciliation classifications.
- **Auditability**: Records non-sensitive audit metadata (task type, model ID, latency, confidence, fallback status) for compliance tracking.

---

## 9. Supplier Compliance & Risk Analytics (M7.13)

### 9.1 Deterministic Compliance Score Formula
Supplier-level compliance and risk profiles are computed **100% deterministically** by grouping reconciliation outcomes by supplier GSTIN. It is a deterministic analytics metric derived directly from reconciliation classifications, **not** an LLM-generated score.

$$\text{compliance\_score} = \text{round}\left( \frac{\text{exact\_matches} + \text{partial\_matches}}{\text{total\_invoices}} \times 100.0, \, 1 \right)$$

*(Note: If `total_invoices` is `0`, `accuracy_rate` defaults to `1.0`, yielding a `compliance_score` of `100.0`)*.

### 9.2 Risk Categorization Thresholds
- **`LOW_RISK`**: `compliance_score >= 80.0`
- **`MEDIUM_RISK`**: `50.0 <= compliance_score < 80.0`
- **`HIGH_RISK`**: `compliance_score < 50.0`

### 9.3 ITC Risk Allocation & Section 16(4) Warning
- **Claimable ITC**: Accumulated deterministically from `EXACT_MATCH` and `PARTIAL_MATCH` invoice records (`cgst + sgst + igst`).
- **Disputed ITC**: Accumulated deterministically from `DISCREPANCY` and `UNMATCHED` invoice records.
- **Section 16(4) Risk Warning**: Triggered deterministically when `disputed_itc > 5000.0` (INR) or when the supplier is categorized as `HIGH_RISK`, warning compliance officers of potential tax credit forfeiture risks under Section 16(4) of the CGST Act.

---

## 10. Audit History & Traceability (M7.10)

### 10.1 Audit Persistence & Run History
- **Run Logging**: Every completed reconciliation run logs structured audit metadata, run summaries, and reconciliation record results to persistent storage.
- **History API**: Historical reconciliation executions can be queried and loaded via the `/api/v1/orchestration/history` endpoint.
- **Traceability**: Provides full historical auditability, allowing compliance officers to review past reconciliation runs, track supplier risk trends, and inspect AI Gateway execution metrics over time.
- **Non-Sensitive Audit Metadata**: Retains task types, provider names, model identifiers, latencies, confidence scores, and fallback usage without persisting raw API key secrets or unencrypted external tokens.

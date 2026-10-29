# AI Architecture & Gateway Specification (M7.1)

## 1. Executive Summary & Architectural Principle

The GST Invoice Reconciliation AI platform establishes a **Hybrid AI + Deterministic Architecture**.

- **Deterministic Engine = Financial & Reconciliation Authority**: The core Python engine retains exclusive authority over data normalization, numeric comparisons, tolerance checks, primary reconciliation classifications (`EXACT_MATCH`, `PARTIAL_MATCH`, `DISCREPANCY`, `UNMATCHED`), ITC claimable calculations, and summary audit reports.
- **AI Gateway = Intelligence & Assistance Layer**: The AI Gateway operates as a controlled assistance service for semantic tasks (heterogeneous column header mapping, candidate evidence evaluation for ambiguous pairs, human-readable discrepancy explanations, pairwise file source-role validation, and accounting resolution voucher generation).

```text
                               ┌─────────────────────────────────────────┐
                                │       Application Workflows             │
                               └────────────────────┬────────────────────┘
                                                    │
                                                    ▼
                               ┌─────────────────────────────────────────┐
                               │           AI Gateway Layer              │
                               │  (Task Scope, Prompts, Schema Validation│
                               └────────────────────┬────────────────────┘
                                                    │
                                       ┌────────────┴────────────┐
                                       ▼                         ▼
                         ┌───────────────────────────┐ ┌───────────────────┐
                         │  External Enterprise LLM  │ │ Local / On-Prem   │
                         │  (OpenAI / Gemini API)    │ │ (Ollama / Llama)  │
                         └─────────────┬─────────────┘ └─────────┬─────────┘
                                       └────────────┬────────────┘
                                                    │
                                                    ▼
                               ┌─────────────────────────────────────────┐
                               │   Structured AI Response & Validation   │
                               └────────────────────┬────────────────────┘
                                                    │
                                                    ▼
                               ┌─────────────────────────────────────────┐
                               │ Deterministic Engine / Manual Review    │
                               └─────────────────────────────────────────┘
```

---

## 2. Responsibilities Matrix

| Domain / Task | Deterministic Engine (Authority) | AI Gateway (Assistance) |
| :--- | :--- | :--- |
| **Header Mapping** | Executes exact/alias dictionary lookups & enforces canonical field constraints | Suggests mappings for unknown/heterogeneous column headers |
| **Candidate Search** | Identifies candidate index pairs via exact and fuzzy string similarity | Evaluates structured evidence for ambiguous candidate pairs |
| **Financial Arithmetic** | **100% Authoritative**: Calculates exact numerical differences & tax totals | **STRICTLY FORBIDDEN**: Never performs math or tax calculations |
| **Tolerance Checks** | Evaluates configured absolute/percentage amount tolerances | **STRICTLY FORBIDDEN**: Cannot evaluate or modify tolerances |
| **Classifications** | Assigns `EXACT_MATCH`, `PARTIAL_MATCH`, `DISCREPANCY`, `UNMATCHED` | **STRICTLY FORBIDDEN**: Cannot set primary classifications |
| **Discrepancy Notes** | Generates pre-computed field difference objects (`FieldDifference`) | Generates human-readable explanations, audit remarks, and action steps |
| **Source Role Safety** | Validates same-file selections (`validateSelectedFiles`) deterministically | Evaluates pairwise GST/ERP column headers to detect swapped file assignments |
| **Resolution Vouchers** | Computes exact numerical difference amounts for voucher items | Suggests voucher types (`PURCHASE_REGISTER_AMENDMENT`, `ITC_REVERSAL_JOURNAL`) |
| **Fallback & Safety** | Fallbacks gracefully to manual review (`requires_manual_review = True`) | Validates response schemas & enforces retry/timeout limits |

---

## 3. Centralized AI Gateway Abstraction

The AI Gateway provides a provider-agnostic interface insulating the core application from vendor-specific LLM APIs.

### 3.1 Key Gateway Responsibilities
1. **Narrow Task Scoping**: Accepts tightly bounded tasks without exposing unneeded context.
2. **Provider Management**: Adapts requests to approved enterprise providers (OpenAI, Gemini, Anthropic, Ollama).
3. **Controlled Prompting**: Injects standard system instructions and safety constraints.
4. **Structured JSON Enforcement**: Enforces Pydantic response contract parsing.
5. **Validation & Retry**: Handles malformed JSON responses, rate limits, and network timeouts.
6. **Graceful Fallback**: Returns fallback data structures to trigger safe application degradation.
7. **Audit Logging**: Records audit metadata (timestamps, model ID, token usage, latency) without logging sensitive invoice payloads.

---

## 4. Primary AI Tasks & Structured JSON Contracts

### 4.1 Task 1: AI Schema Mapping
- **Purpose**: Assists in mapping unfamiliar or non-standard source column headers to canonical invoice fields.
- **Boundary**: AI suggestions must match supported canonical schema keys (`invoice_number`, `gstin`, `invoice_date`, `taxable_value`, `cgst`, `sgst`, `igst`, `total_invoice_value`). Deterministic rules override AI suggestions.
- **Contract Schema**:
```json
{
  "suggestions": [
    {
      "source_column": "Doc_Ref_No",
      "canonical_field": "invoice_number",
      "confidence": 0.95,
      "evidence": "Doc_Ref_No is a common vendor acronym for invoice document number",
      "reasoning": "Contains document number semantics matching invoice_number identity"
    }
  ]
}
```

### 4.2 Task 2: AI Candidate Ambiguity Resolution
- **Purpose**: Evaluates candidate evidence when candidate generation produces multiple plausible ERP records.
- **Boundary**: AI receives *only* pre-selected candidate records. AI cannot invent candidates outside the supplied list, nor calculate financial values.
- **Contract Schema**:
```json
{
  "candidate": "INV-1001",
  "confidence": 0.88,
  "evidence": [
    "Invoice number character sequence matches with minor hyphens",
    "GSTIN matches supplier identity"
  ],
  "reasoning": "INV-1001 represents the same transaction as INV1001 despite hyphen formatting difference"
}
```

### 4.3 Task 3: AI Discrepancy Review
- **Purpose**: Analyzes non-exact reconciliation records (`PARTIAL_MATCH`, `DISCREPANCY`) to generate clear human-readable notes.
- **Boundary**: Accepts pre-calculated `FieldDifference` objects. Cannot alter classifications or recalculate differences.
- **Contract Schema**:
```json
{
  "remark": "Invoice total matches, but CGST and SGST amounts show state tax head reallocation",
  "audit_remark": "Tax head shift detected between CGST/SGST (INR 90.00 each) and IGST (INR 180.00)",
  "recommended_action": "Verify inter-state vs intra-state supply classification with vendor before ITC claim",
  "reasoning": "Gross invoice value of INR 1180.00 is identical across both records"
}
```

### 4.4 Task 4: AI Pairwise Input Source-Role Validation (M7.15)
- **Purpose**: Evaluates column headers of both uploaded files simultaneously (`gst_columns`, `erp_columns`) to classify input roles (`GST_LIKELY`, `ERP_LIKELY`, `AMBIGUOUS`).
- **Boundary**: Receives string lists of column header names only; no invoice rows, monetary figures, or tax values are sent. If swapped file assignments are detected (`assignment_valid = false`), frontend reconciliation execution is hard-blocked.
- **Contract Schema**:
```json
{
  "gst_role": "GST_LIKELY",
  "erp_role": "ERP_LIKELY",
  "assignment_valid": true,
  "confidence": 0.95,
  "reasoning": "GST Slot contains GSTR-2B tax headers while ERP Slot contains ERP document voucher headers"
}
```

### 4.5 Task 5: AI Actionable Discrepancy & Resolution Vouchers (M7.9)
- **Purpose**: Generates structured accounting adjustment voucher suggestions (`PURCHASE_REGISTER_AMENDMENT`, `ITC_REVERSAL_JOURNAL`) and vendor notices for non-exact records.
- **Boundary**: AI provides recommendations only. All financial amounts and difference figures used in recommendations originate 100% from deterministic reconciliation calculations.
- **Contract Schema**:
```json
{
  "action_type": "ITC_REVERSAL_JOURNAL",
  "summary": "Reverse disputed ITC claim for non-matching tax amounts",
  "reasoning": "GSTR-2B IGST amount exceeds ERP purchase register entry",
  "adjustment_voucher": {
    "voucher_type": "ITC_REVERSAL_JOURNAL",
    "debit_account": "GSTR-2B Ineligible/Disputed ITC Clearing Account",
    "credit_account": "Input Tax Credit - IGST",
    "amount": 1440.0,
    "narration": "Being reversal of IGST credit for invoice #INV-2024-005"
  },
  "confidence_score": 0.95
}
```

---

## 5. Enterprise Data Minimization & Privacy

1. **No Bulk File Uploads**: Uploaded 100,000-row GST/ERP files are **never** transmitted to an external LLM.
2. **Narrow Scope**: Only isolated candidate pairs or single column header arrays are passed.
3. **Sanitization**: Sensitive personal data, bank details, and unneeded fields are stripped prior to gateway dispatch.
4. **Configurable Deployment**: Organizations can disable external cloud LLMs and select on-premise local models (e.g. Ollama) via environment settings.

---

## 6. Deterministic Fallback & Graceful Degradation

> [!IMPORTANT]
> **AI Failure Principle**: "AI failure must degrade gracefully and must never cause incorrect financial reconciliation."

```text
                            ┌────────────────────────┐
                            │    AI Gateway Call     │
                            └───────────┬────────────┘
                                        │
                         ┌──────────────┴──────────────┐
                         ▼                             ▼
                 [Success & Valid]             [Error / Timeout / Invalid]
                         │                             │
                         ▼                             ▼
             Apply AI Assistance Output     Fallback to Deterministic Rules
                                            or set requires_manual_review = True
```

- **If AI Provider Fails / Times Out**:
  - Schema Mapping: Uses deterministic alias dictionary; leaves unmapped columns for user selection.
  - Candidate Resolution: Uses deterministic similarity score or flags `requires_manual_review = True`.
  - Discrepancy Review: Generates template audit note from pre-computed `FieldDifference` objects.
  - Source-Role Validation: Safely returns `AMBIGUOUS` (`assignment_valid = true`), allowing deterministic column mapping rules to make the decision.
  - Resolution Recommendation: Returns fallback template voucher based on pre-calculated difference fields.
- **Zero Financial Impact**: Financial totals and primary classifications remain 100% accurate.

---

## 7. Security, Prompts, & Auditability

### 7.1 Prompt Safety Rules
All AI prompts must inject mandatory system instructions:
> *"You are an AI assistant for a GST reconciliation engine. You do NOT perform financial arithmetic, tax calculations, or tolerance checks. You do NOT invent invoice records. You evaluate only supplied evidence and output valid JSON matching the requested schema."*

### 7.2 Security & Secrets
- API keys (`OPENAI_API_KEY`, `GEMINI_API_KEY`) must come exclusively from environment configuration.
- API keys and raw prompt invoice payloads are **never** logged to file logs.

### 7.3 Audit Metadata
Each AI Gateway call records:
- `task_type`: `SCHEMA_MAPPING` | `CANDIDATE_RESOLUTION` | `DISCREPANCY_REVIEW` | `SOURCE_ROLE` | `RESOLUTION_RECOMMENDATION`
- `provider`: `openai` | `gemini` | `ollama` | `fallback`
- `model_identifier`: `gpt-4o` | `gemini-1.5-flash` | `offline-engine`
- `request_timestamp` & `latency_ms`
- `confidence_score` & `validation_status`
- `fallback_used`: `true` | `false`

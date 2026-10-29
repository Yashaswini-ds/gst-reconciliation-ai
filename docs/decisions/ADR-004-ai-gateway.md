# ADR-004: Centralized AI Gateway & Hybrid LLM Architecture

## Status
Accepted (SDD Architecture Specification - M7.1)

## Context
The GST Portal vs ERP Invoice Reconciliation application requires intelligent assistance to address three distinct challenges:
1. Mapping heterogeneous source file column headers to canonical invoice schema fields.
2. Evaluating structured record evidence when candidate identification produces multiple plausible ERP candidates.
3. Explaining non-exact reconciliation results (`PARTIAL_MATCH`, `DISCREPANCY`) with clear human-readable remarks and audit recommendations.

However, direct coupling of application modules to specific LLM vendor SDKs (e.g., OpenAI, Gemini, Anthropic, Ollama) creates vendor lock-in, introduces security risks of unauthorized enterprise data transmission, and risks violating financial authority principles if an LLM attempts financial arithmetic.

## Decision
We establish a **Centralized AI Gateway Abstraction Layer** and enforce a strict **Hybrid AI + Deterministic Architectural Boundary**.

### 1. Hybrid Responsibility Boundary
- **Deterministic Engine = Financial & Reconciliation Authority**: Handles file ingestion, schema validation, controlled field normalizations, numeric comparisons, tolerance evaluations, primary classifications (`EXACT_MATCH`, `PARTIAL_MATCH`, `DISCREPANCY`, `UNMATCHED`), ITC claimable totals, and canonical dataset state.
- **LLM / AI Gateway = Intelligence & Assistance Layer**: Provides semantic header mapping suggestions, candidate evidence evaluation for ambiguous pairs, human-readable discrepancy explanations, AI remarks, and audit recommendations.

### 2. AI Forbidden Responsibilities
The LLM and AI Gateway are strictly forbidden from:
- Performing financial arithmetic or tax calculations.
- Comparing monetary values mathematically or evaluating numerical tolerances.
- Modifying source invoice values or canonical schema definitions.
- Directly assigning or overriding primary reconciliation classifications.
- Generating authoritative financial totals.
- Silently approving or rejecting financial claims.

### 3. AI Gateway Abstraction Layer
The AI Gateway sits between application logic and AI model providers:

```text
Application Logic
      ↓
  AI Gateway (Narrow Task Request)
      ↓
  Provider Adapter (OpenAI / Gemini / Enterprise / Local Model)
      ↓
  Structured Response Parsing & Validation (Pydantic Schema)
      ↓
  Application Logic (or Deterministic Fallback if Validation/API Fails)
```

### 4. Enterprise Data Minimization
- Full uploaded datasets (e.g., 100,000-row GST/ERP files) are **never** sent to an LLM provider.
- AI requests are narrowly scoped to isolated record pairs or single column lists.
- PII, unnecessary vendor details, and unneeded financial fields are excluded from LLM payloads.

### 5. Deterministic Fallback & Graceful Degradation
- **Principle**: "AI failure must degrade gracefully and must never cause incorrect financial reconciliation."
- If the AI Gateway experiences provider outages, API timeouts, schema validation failures, or rate limits, the system falls back gracefully:
  - **Schema Mapping**: Prefers deterministic alias lookup; unmapped headers remain unmapped or prompt user for manual configuration.
  - **Candidate Resolution**: Uses deterministic fuzzy scores or routes to `requires_manual_review = True`.
  - **Discrepancy Review**: Generates template-based audit remarks from pre-computed deterministic `FieldDifference` metadata.
- Financial reconciliation classifications and amounts remain 100% deterministic and unaffected by AI availability.

## Consequences
- **Vendor Independence**: Allows seamless switching between external LLMs (OpenAI, Gemini), enterprise private deployments, or local models (Ollama/llama.cpp) without changing application code.
- **Financial Compliance**: Zero risk of LLM arithmetic hallucinations corrupting tax filing totals.
- **Enterprise Privacy**: Data minimization guarantees compliance with corporate data security policies.
- **Auditing**: Full audibility metadata recorded for all AI Gateway interactions.

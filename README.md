HEAD
# GST Invoice Reconciliation AI — Enterprise Decision Engine

[![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110+-green.svg)](https://fastapi.tiangolo.com/)
[![Pytest](https://img.shields.io/badge/Pytest-77%20Passed-emerald.svg)](https://docs.pytest.org/)
[![License](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

An enterprise-grade, SDD-driven **GST Invoice Reconciliation Decision Engine** combining deterministic financial precision with hybrid AI-assisted discrepancy reviews. 

Built specifically for Indian GST compliance (GSTR-2B / GSTR-2A vs ERP Purchase Registers), this system enforces strict architectural boundaries: **deterministic algorithms control all financial math, tolerances, and primary match classifications**, while an abstracted **Centralized AI Gateway** handles non-financial schema mapping suggestions, candidate ambiguity evidence evaluation, and post-reconciliation audit notes.

---

## 🌟 Key Features

- **Hybrid Responsibility Architecture**: Financial arithmetic and ITC totals remain 100% deterministic; AI is strictly restricted to schema mapping, ambiguity evaluation, and audit remarks.
- **Robust File Ingestion (M1)**: Ingests CSV, XLSX, and XLS invoice datasets with header normalization and row metadata tracking.
- **Canonical Schema Mapping & Normalization (M2 & M7.3)**:
  - Priority 1: Deterministic dictionary mapping.
  - Priority 2: AI Gateway schema mapping for unknown headers with Pydantic validation & confidence thresholding (≥ 0.70).
  - 15-character uppercase GSTIN validation, invoice number normalization, date standardization, and monetary precision.
- **Candidate Generation & Matching Engine (M3 & M7.4)**:
  - Exact Matching (`EXACT_MATCH`), 2-day date proximity matching (`PARTIAL_MATCH`), value mismatch detection (`DISCREPANCY`), and unmatched handling (`UNMATCHED`).
  - Candidate Ambiguity Resolution with safety checks to reject unlisted AI candidates.
- **Predictive ITC Risk & Vendor Risk Scoring (M11)**:
  - Groups reconciliation results by supplier GSTIN.
  - Computes **Vendor Compliance Score (0–100)** and risk categories (`LOW_RISK`, `MEDIUM_RISK`, `HIGH_RISK`).
  - Highlights Section 16(4) CGST Act tax credit forfeiture risks.
  - Interactive **Supplier Compliance & Risk Profiles Matrix** rendered in the web dashboard.
- **End-to-End Pipeline Orchestration (M5 & M9)**:

  - Single API pipeline execution (`/api/v1/orchestration/reconcile-files`).
  - Automated compliance audit trail logging (`/api/v1/orchestration/audit-trail`).
  - Multi-tab CSV audit report generation (`/api/v1/orchestration/export-csv`).
- **Interactive Web Dashboard (M6 & M9)**:
  - Modern dark-mode web portal at `http://localhost:8000/`.
  - Drag-and-drop file upload, tolerance slider, metric summary cards, tab filtering, downloadable CSV reports, and side-by-side **Discrepancy Inspector Modal**.
- **Centralized AI Gateway (M7 & M8)**:
  - Abstract provider interface (`BaseAIProvider`) with live adapters for **OpenAI** (`gpt-4o`) and **Google Gemini** (`gemini-1.5-flash`).
  - Zero-dependency offline **`FallbackAIProvider`** when cloud API keys are absent.

---

## 🏗️ Architectural Overview

```
                        ┌─────────────────────────────────────────┐
                        │        Upload GST & ERP Invoices        │
                        └────────────────────┬────────────────────┘
                                             │
                                             ▼
                        ┌─────────────────────────────────────────┐
                        │    M1 File Ingestion & Parsing Engine    │
                        └────────────────────┬────────────────────┘
                                             │
                                             ▼
                        ┌─────────────────────────────────────────┐
                        │ M2 Schema Mapping & Normalization Engine│
                        │  (Priority 1: Alias Dict | Priority 2: AI)│
                        └────────────────────┬────────────────────┘
                                             │
                                             ▼
                        ┌─────────────────────────────────────────┐
                        │ M3 Deterministic Matching & Tolerances  │
                        │  (EXACT / PARTIAL / DISCREPANCY / UNMATCH)│
                        └────────────────────┬────────────────────┘
                                             │
                                             ▼
                        ┌─────────────────────────────────────────┐
                        │ M4/M7 AI Gateway & Discrepancy Review   │
                        │   (Human Remarks & Audit Recommendations)│
                        └────────────────────┬────────────────────┘
                                             │
                                             ▼
                        ┌─────────────────────────────────────────┐
                        │  M5/M6/M9 Analytics, Web UI & Audit Log │
                        └─────────────────────────────────────────┘
```

---

## 🛠️ Quick Start & Installation

### 1. Prerequisites
- Python **3.11+**
- Virtual Environment tool (`venv`)

### 2. Clone & Environment Setup
```bash
git clone https://github.com/your-org/gst-reconciliation-ai.git
cd gst-reconciliation-ai

# Create & activate virtual environment
python -m venv venv
# On Windows:
venv\Scripts\activate
# On Linux/macOS:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 3. Environment Configuration
Copy `.env.example` to `.env`:
```bash
cp .env.example .env
```

To configure AI providers in `.env`:
- **Offline Fallback (Default)**: Set `AI_PROVIDER=fallback`
- **OpenAI**: Set `AI_PROVIDER=openai` and `OPENAI_API_KEY=sk-...`
- **Google Gemini**: Set `AI_PROVIDER=gemini` and `GEMINI_API_KEY=AIzaSy...`

---

## 🚀 Running the Application

Start the FastAPI backend and web server:
```bash
python -m uvicorn app.main:app --reload
```

- **Web Dashboard**: Access `http://localhost:8000/` in your browser.
- **Interactive OpenAPI Documentation**: Access `http://localhost:8000/docs` or `http://localhost:8000/redoc`.

---

## 🧪 Running the Test Suite

The project includes **77 automated unit & integration tests** covering all modules (M1–M13):

```bash
pytest -v
```

### Test Coverage Highlights:
- File ingestion, empty file rejection, and malformed CSV handling (`tests/test_ingestion.py`)
- Normalization, GSTIN parsing, and custom column mapping (`tests/test_normalization.py`)
- Deterministic matching, date proximity, and duplicate candidate ambiguity (`tests/test_matching.py`)
- AI Gateway abstraction, Pydantic validation, and provider fallback (`tests/test_ai_gateway.py`)
- AI Schema mapping, confidence thresholds, and invalid field rejection (`tests/test_ai_mapping.py`)
- AI Candidate ambiguity resolution & unlisted invoice rejection (`tests/test_ai_ambiguity.py`)
- AI Discrepancy review generation (`tests/test_ai_discrepancy.py`)
- Live provider adapters (OpenAI & Gemini mocks) (`tests/test_live_providers.py`)
- Pipeline orchestration & CSV report generation (`tests/test_orchestration.py`)
- Audit trail logging service (`tests/test_audit_trail.py`)
- Web UI static asset delivery (`tests/test_web_ui.py`)

---

## 📡 API Endpoints Reference

| Category | Endpoint | Method | Description |
| :--- | :--- | :--- | :--- |
| **Pipeline** | `/api/v1/orchestration/reconcile-files` | `POST` | End-to-end reconciliation over uploaded GST & ERP files |
| **Export** | `/api/v1/orchestration/export-csv` | `POST` | Exports batch reconciliation results to downloadable CSV |
| **Audit** | `/api/v1/orchestration/audit-trail` | `GET` | Retrieves compliance audit log history |
| **AI** | `/api/v1/ai/resolve-ambiguity` | `POST` | AI candidate evidence evaluation endpoint |
| **AI** | `/api/v1/ai/review-discrepancy` | `POST` | Post-reconciliation AI discrepancy review generator |
| **Health** | `/health` | `GET` | Health check endpoint |

---

## 📜 Architectural Decision Records (ADRs)

Detailed architectural decision records are stored under `docs/decisions/`:
- [ADR-001: Hybrid AI & Deterministic Reconciliation Boundaries](file:///c:/Users/yashaswini.ds/Desktop/gst-reconciliation-ai/docs/decisions/ADR-001-ai-matching.md)
- [ADR-002: Canonical Schema & Normalization Strategy](file:///c:/Users/yashaswini.ds/Desktop/gst-reconciliation-ai/docs/decisions/ADR-002-normalization.md)
- [ADR-003: Deterministic Matching Engine Rules & Tolerances](file:///c:/Users/yashaswini.ds/Desktop/gst-reconciliation-ai/docs/decisions/ADR-003-matching-strategy.md)
- [ADR-004: Centralized AI Gateway Abstraction](file:///c:/Users/yashaswini.ds/Desktop/gst-reconciliation-ai/docs/decisions/ADR-004-ai-gateway.md)

---

## 📄 License

This project is licensed under the MIT License.

# gst-reconciliation-ai
 cae4daabc15050f97ca3fce181af223bc0731fca

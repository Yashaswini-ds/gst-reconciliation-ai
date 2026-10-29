# ADR-002: Data Normalization Strategy

## Status
Accepted (Revised)

## Context
GST Portal and ERP data streams use heterogeneous column names, date representations, and invoice formatting. Uncontrolled or blanket normalization (such as mandatory zero-padding, unconditional prefix removal, or stripping all non-alphanumeric characters) can alter invoice identity and lead to false matches.

## Decision
Implement controlled, field-specific, and configurable data normalization rules across both datasets prior to candidate generation and field comparison.

### Key Principles:
- **Field-Specific**: Normalization logic is tailored to each field type (e.g. whitespace trimming, string casing, standardizing date representations).
- **Identity Preservative**: Invoice number transformations must preserve underlying invoice identity and avoid generating artificial collisions.
- **Configurable**: Source-specific normalization settings can be enabled/disabled per integration pipeline.
- **No Blanket Stripping**: Blanket prefix removal, blanket zero-padding, and destructive string mutations are prohibited.

## Consequences
- Prevents false-positive candidate matching caused by aggressive normalization.
- Ensures accurate canonical mapping for GST Portal and ERP invoice data.

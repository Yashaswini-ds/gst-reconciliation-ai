"""Matching Engine & Candidate Generation Module."""

from app.matching.schemas import (
    FieldDifference,
    MatchClassification,
    ReconciliationConfig,
    ReconciliationRecordResult,
    UnmatchedReason,
)
from app.matching.engine import MatchingEngine, matching_engine

__all__ = [
    "MatchClassification",
    "UnmatchedReason",
    "FieldDifference",
    "ReconciliationConfig",
    "ReconciliationRecordResult",
    "MatchingEngine",
    "matching_engine",
]

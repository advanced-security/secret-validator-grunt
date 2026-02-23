"""
Report evaluation framework.

Provides deterministic checks for validating the structural
and semantic quality of secret validation reports.
"""

from secret_validator_grunt.evals.checks import (
    run_all_checks,
    has_required_sections,
    valid_verdict,
    valid_confidence_score,
    confidence_label_matches_score,
    metadata_complete,
    has_key_finding,
    has_verification_tests,
    has_code_evidence,
    verdict_confidence_coherent,
    score_to_label,
)

__all__ = [
    "run_all_checks",
    "has_required_sections",
    "valid_verdict",
    "valid_confidence_score",
    "confidence_label_matches_score",
    "metadata_complete",
    "has_key_finding",
    "has_verification_tests",
    "has_code_evidence",
    "verdict_confidence_coherent",
    "score_to_label",
]

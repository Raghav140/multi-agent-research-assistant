"""Improved evidence confidence calculation model.

This module provides a confidence calculation model that considers
evidence quality, source diversity, agreement score, and citation quality.
"""

from typing import Any, Dict, Optional
from backend.utils.logging_config import get_logger

logger = get_logger(__name__)


def calculate_evidence_confidence(
    evidence_quality: float,
    source_diversity: float,
    agreement_score: float,
    citation_quality: float,
) -> Dict[str, Any]:
    """Calculate evidence confidence using improved model.

    Confidence components:
    - Evidence quality: 40%
    - Source diversity: 25%
    - Agreement score: 20%
    - Citation quality: 15%

    Args:
        evidence_quality: Average evidence quality score (0-1)
        source_diversity: Source diversity score (0-1)
        agreement_score: Agreement between sources (0-1)
        citation_quality: Citation quality score (0-1)

    Returns:
        Dictionary with confidence_score, confidence_level, and reason
    """
    # Calculate weighted confidence
    confidence_score = (
        (evidence_quality * 0.40) +
        (source_diversity * 0.25) +
        (agreement_score * 0.20) +
        (citation_quality * 0.15)
    )

    # Determine confidence level
    if confidence_score >= 0.75:
        confidence_level = "High"
    elif confidence_score >= 0.50:
        confidence_level = "Medium"
    else:
        confidence_level = "Low"

    # Generate reason
    reason = _generate_confidence_reason(
        evidence_quality,
        source_diversity,
        agreement_score,
        citation_quality,
        confidence_level,
    )

    logger.debug(
        "Evidence confidence calculated",
        extra={
            "evidence_quality": evidence_quality,
            "source_diversity": source_diversity,
            "agreement_score": agreement_score,
            "citation_quality": citation_quality,
            "confidence_score": confidence_score,
            "confidence_level": confidence_level,
        },
    )

    return {
        "confidence_score": confidence_score,
        "confidence_level": confidence_level,
        "reason": reason,
    }


def _generate_confidence_reason(
    evidence_quality: float,
    source_diversity: float,
    agreement_score: float,
    citation_quality: float,
    confidence_level: str,
) -> str:
    """Generate reason for confidence level.

    Args:
        evidence_quality: Evidence quality score
        source_diversity: Source diversity score
        agreement_score: Agreement score
        citation_quality: Citation quality score
        confidence_level: Confidence level

    Returns:
        Reason string
    """
    if confidence_level == "High":
        return f"High confidence: Strong evidence quality ({evidence_quality:.2f}), good source diversity ({source_diversity:.2f}), strong agreement ({agreement_score:.2f}), reliable citations ({citation_quality:.2f})"
    elif confidence_level == "Medium":
        return f"Medium confidence: Moderate evidence quality ({evidence_quality:.2f}), source diversity ({source_diversity:.2f}), agreement ({agreement_score:.2f}), citations ({citation_quality:.2f})"
    else:
        return f"Low confidence: Weak evidence quality ({evidence_quality:.2f}), limited source diversity ({source_diversity:.2f}), low agreement ({agreement_score:.2f}), poor citations ({citation_quality:.2f})"


def calculate_confidence_from_sources(
    sources: list[Dict[str, Any]],
    agreement_score: float = 0.0,
    diversity_score: float = 0.0,
) -> Dict[str, Any]:
    """Calculate confidence from source list.

    Args:
        sources: List of sources with quality scores
        agreement_score: Agreement between sources
        diversity_score: Source diversity score

    Returns:
        Dictionary with confidence_score, confidence_level, and reason
    """
    if not sources:
        return {
            "confidence_score": 0.0,
            "confidence_level": "Low",
            "reason": "No sources available",
        }

    # Calculate average evidence quality
    quality_scores = []
    for source in sources:
        quality = source.get("quality_score", 0.5)
        quality_scores.append(quality)

    evidence_quality = sum(quality_scores) / len(quality_scores) if quality_scores else 0.5

    # Calculate citation quality from source reliability
    reliability_scores = []
    for source in sources:
        reliability = source.get("reliability_score", 0.5)
        reliability_scores.append(reliability)

    citation_quality = sum(reliability_scores) / len(reliability_scores) if reliability_scores else 0.5

    return calculate_evidence_confidence(
        evidence_quality=evidence_quality,
        source_diversity=diversity_score,
        agreement_score=agreement_score,
        citation_quality=citation_quality,
    )

"""Inquiry completion gate: need at least three submitted variants."""

from __future__ import annotations

from services.maite.domain.inquiry_service import MIN_VARIANTS_FOR_COMPLETE


def test_min_submitted_variants_constant():
    """Pedagogy rule: complete requires >= 3 submitted variants."""
    assert MIN_VARIANTS_FOR_COMPLETE >= 3

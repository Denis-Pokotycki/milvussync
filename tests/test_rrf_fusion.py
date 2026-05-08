"""Tests for rrf_fusion() — pure function, no Django DB or live services needed."""
import pytest
from sync.views import rrf_fusion


def _doc(pk, **extra):
    return {"pk": pk, "title": f"Title {pk}", **extra}


# ── score calculation ─────────────────────────────────────────────────────────

def test_result_contains_rrf_score():
    keyword  = [_doc("A")]
    semantic = [_doc("A")]
    result = rrf_fusion(keyword, semantic)
    assert "rrf_score" in result[0]


def test_score_formula_with_default_k():
    # A appears at rank 1 in both lists: score = 1/(60+1) + 1/(60+1)
    keyword  = [_doc("A")]
    semantic = [_doc("A")]
    result = rrf_fusion(keyword, semantic)
    expected = round(1.0 / 61 + 1.0 / 61, 6)
    assert result[0]["rrf_score"] == expected


def test_score_formula_with_custom_k():
    keyword  = [_doc("A")]
    semantic = [_doc("A")]
    result = rrf_fusion(keyword, semantic, k=1)
    expected = round(1.0 / 2 + 1.0 / 2, 6)
    assert result[0]["rrf_score"] == expected


# ── ranking ───────────────────────────────────────────────────────────────────

def test_results_ordered_by_score_descending():
    # A only in keyword (rank 1); B only in semantic (rank 1)
    # A and B get equal score; C appears in both at rank 2 → higher combined score
    keyword  = [_doc("A"), _doc("C")]
    semantic = [_doc("B"), _doc("C")]
    result = rrf_fusion(keyword, semantic)
    scores = [r["rrf_score"] for r in result]
    assert scores == sorted(scores, reverse=True)


def test_document_in_both_lists_ranks_higher_than_single_list():
    keyword  = [_doc("BOTH"), _doc("KEYWORD_ONLY")]
    semantic = [_doc("BOTH"), _doc("SEMANTIC_ONLY")]
    result = rrf_fusion(keyword, semantic)
    pks = [r["pk"] for r in result]
    assert pks.index("BOTH") < pks.index("KEYWORD_ONLY")
    assert pks.index("BOTH") < pks.index("SEMANTIC_ONLY")


# ── limit ─────────────────────────────────────────────────────────────────────

def test_limit_is_respected():
    keyword  = [_doc(f"K{i}") for i in range(10)]
    semantic = [_doc(f"S{i}") for i in range(10)]
    result = rrf_fusion(keyword, semantic, limit=3)
    assert len(result) == 3


def test_limit_larger_than_results_returns_all():
    keyword  = [_doc("A")]
    semantic = [_doc("B")]
    result = rrf_fusion(keyword, semantic, limit=100)
    assert len(result) == 2


# ── edge cases ────────────────────────────────────────────────────────────────

def test_empty_both_lists_returns_empty():
    assert rrf_fusion([], []) == []


def test_empty_keyword_list_uses_semantic_only():
    semantic = [_doc("A"), _doc("B")]
    result = rrf_fusion([], semantic)
    assert len(result) == 2
    assert result[0]["pk"] == "A"


def test_empty_semantic_list_uses_keyword_only():
    keyword = [_doc("A"), _doc("B")]
    result = rrf_fusion(keyword, [])
    assert len(result) == 2
    assert result[0]["pk"] == "A"


def test_deduplication_same_pk_in_both_lists():
    keyword  = [_doc("A"), _doc("B")]
    semantic = [_doc("A"), _doc("C")]
    result = rrf_fusion(keyword, semantic)
    pks = [r["pk"] for r in result]
    assert pks.count("A") == 1


def test_extra_fields_from_keyword_are_preserved():
    keyword  = [_doc("A", nut_code="DE600", cpv_codes=["45233000-9"])]
    semantic = [_doc("B")]
    result = rrf_fusion(keyword, semantic)
    a = next(r for r in result if r["pk"] == "A")
    assert a["nut_code"] == "DE600"
    assert a["cpv_codes"] == ["45233000-9"]

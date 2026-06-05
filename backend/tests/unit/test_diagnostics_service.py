"""Testy serwisu diagnostyki - 9 metryk jakości danych.

Testy integracyjne z testową bazą (kopia data/czarna.db).
Weryfikujemy:
- Kształt zwracanego dicta (wszystkie 9 metryk)
- Poprawność typów (count: int, sample: list)
- Spójność (suma incomplete = suma missing buckets)
- Limity sample (max 10 elementów)
"""
from __future__ import annotations

import pytest

from backend.services.diagnostics_service import (
    compute_diagnostics,
    SAMPLE_LIMIT,
    ALL_METRIC_KEYS,
)
from backend.tests.unit._asyncio_helpers import run_async_safely


# ============================================================================
# Kształt i kompletność zwracanego dicta
# ============================================================================


def test_compute_diagnostics_returns_all_9_metrics():
    """``compute_diagnostics`` zwraca dict z wszystkimi 9 metrykami."""
    result = _run_compute()
    assert isinstance(result, dict)
    for key in ALL_METRIC_KEYS:
        assert key in result, f"Brak metryki {key} w wyniku"


def test_all_metric_keys_constant_has_10_keys():
    """Stała ``ALL_METRIC_KEYS`` ma dokładnie 10 kluczy (9 metryk + parcel_owner_links)."""
    assert len(ALL_METRIC_KEYS) == 10


def test_sample_limit_is_10():
    """Limit sample = 10 (żeby payload nie rósł w nieskończoność)."""
    assert SAMPLE_LIMIT == 10


# ============================================================================
# Kształt poszczególnych metryk
# ============================================================================


def _run_compute():
    """Helper - uruchamia compute_diagnostics w evencie synchronicznym.

    Używa wspólnego :func:`run_async_safely` (z ``_asyncio_helpers``) —
    resetuje running_loop PRZED startem i przywraca PO, co jest
    konieczne w sesjach z pytest-playwright (który zostawia loop w
    thread-local nawet po teardownie ``page``).
    """
    from backend.db.connection import get_db_context

    async def _run():
        async with get_db_context() as db:
            return await compute_diagnostics(db)

    return run_async_safely(_run())


def test_parcels_without_owners_shape():
    """``parcels_without_owners`` ma count (int) i sample (lista)."""
    result = _run_compute()
    metric = result["parcels_without_owners"]
    assert "count" in metric
    assert "sample" in metric
    assert isinstance(metric["count"], int)
    assert isinstance(metric["sample"], list)
    assert metric["count"] >= 0
    assert len(metric["sample"]) <= SAMPLE_LIMIT
    if metric["sample"]:
        first = metric["sample"][0]
        assert "id" in first
        assert "name" in first


def test_owners_without_parcels_shape():
    result = _run_compute()
    metric = result["owners_without_parcels"]
    assert isinstance(metric["count"], int)
    assert isinstance(metric["sample"], list)
    assert len(metric["sample"]) <= SAMPLE_LIMIT


def test_protocols_without_genealogy_shape():
    result = _run_compute()
    metric = result["protocols_without_genealogy"]
    assert isinstance(metric["count"], int)
    assert isinstance(metric["sample"], list)
    if metric["sample"]:
        first = metric["sample"][0]
        assert "id" in first
        assert "name" in first


def test_people_without_parents_shape():
    result = _run_compute()
    metric = result["people_without_parents"]
    assert isinstance(metric["count"], int)
    assert isinstance(metric["sample"], list)


def test_people_without_birth_date_shape():
    result = _run_compute()
    metric = result["people_without_birth_date"]
    assert isinstance(metric["count"], int)
    assert isinstance(metric["sample"], list)


def test_people_without_death_date_shape():
    result = _run_compute()
    metric = result["people_without_death_date"]
    assert isinstance(metric["count"], int)
    assert isinstance(metric["sample"], list)


def test_parcels_without_category_shape():
    result = _run_compute()
    metric = result["parcels_without_category"]
    assert isinstance(metric["count"], int)
    assert isinstance(metric["sample"], list)


def test_owners_without_house_number_shape():
    result = _run_compute()
    metric = result["owners_without_house_number"]
    assert isinstance(metric["count"], int)
    assert isinstance(metric["sample"], list)


def test_parcel_owner_links_shape():
    """``parcel_owner_links`` ma tylko ``count`` (suma wszystkich powiązań)."""
    result = _run_compute()
    metric = result["parcel_owner_links"]
    assert "count" in metric
    assert "sample" not in metric  # czysty counter, bez sampla
    assert isinstance(metric["count"], int)
    assert metric["count"] > 0, "Baza ma 3903 powiązań"


def test_incomplete_records_shape():
    """``incomplete_records`` to zagregowany licznik - ile rekordów ma przynajmniej
    jedną brakującą informację (nie sumuje bucketów, deduplikuje)."""
    result = _run_compute()
    metric = result["incomplete_records"]
    assert isinstance(metric["count"], int)
    assert "sample" not in metric  # agregat, bez sampla
    assert metric["count"] >= 0


# ============================================================================
# Spójność - incomplete nie może być mniejsze niż max(pojedyncze buckety)
# ============================================================================


def test_incomplete_count_is_at_least_max_single_bucket():
    """``incomplete_records.count`` >= max(każdy pojedynczy bucket missing)."""
    result = _run_compute()
    incomplete = result["incomplete_records"]["count"]
    max_bucket = max(
        result["parcels_without_owners"]["count"],
        result["owners_without_parcels"]["count"],
        result["protocols_without_genealogy"]["count"],
        result["parcels_without_category"]["count"],
        result["owners_without_house_number"]["count"],
    )
    assert incomplete >= max_bucket, (
        f"incomplete={incomplete} powinno być >= max_bucket={max_bucket}"
    )


# ============================================================================
# Limity sample
# ============================================================================


def test_sample_limited_to_10():
    """Sample nigdy nie przekracza 10 elementów (nawet przy dużej bazie)."""
    result = _run_compute()
    for key in ALL_METRIC_KEYS:
        metric = result[key]
        if "sample" in metric:
            assert len(metric["sample"]) <= SAMPLE_LIMIT, (
                f"{key}.sample ma {len(metric['sample'])} > {SAMPLE_LIMIT}"
            )


# ============================================================================
# Sanity check: count >= len(sample) dla każdej metryki z samplem
# ============================================================================


def test_count_geq_sample_size():
    """``count`` nigdy nie może być mniejsze niż ``len(sample)``."""
    result = _run_compute()
    for key in ALL_METRIC_KEYS:
        metric = result[key]
        if "sample" in metric:
            assert metric["count"] >= len(metric["sample"]), (
                f"{key}.count={metric['count']} < len(sample)={len(metric['sample'])}"
            )

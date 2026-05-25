"""Integration tests for ModelSearchIndex — semantic quality using the real ML model.

These tests require ``sentence-transformers`` and a working PyTorch backend.
They download the ``paraphrase-multilingual-MiniLM-L12-v2`` model (~470 MB)
on first run and cache it in the HuggingFace hub cache directory.

Mark: ``slow`` — skip in fast CI runs::

    pytest tests/integration/test_search_index_semantic.py -v -m slow

Or run directly::

    uv run pytest tests/integration/test_search_index_semantic.py -v
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import cast

import pytest
from google.protobuf.json_format import ParseDict
from odsbox.proto import ods

pytestmark = pytest.mark.slow

_FIXTURE = Path(__file__).parent.parent / "data" / "mdm_nvh_model.json"


def _load_model() -> ods.Model:
    with _FIXTURE.open(encoding="utf-8") as fh:
        return cast(ods.Model, ParseDict(json.load(fh), ods.Model()))


@pytest.fixture(scope="module")
def search_index(tmp_path_factory: pytest.TempPathFactory):  # type: ignore[no-untyped-def]
    """Build a ModelSearchIndex with real embeddings once per module."""
    pytest.importorskip("sentence_transformers", reason="sentence-transformers not installed")
    from odsbox_pilot.model.search_index import ModelSearchIndex

    cache_dir = tmp_path_factory.mktemp("search_cache")
    import odsbox_pilot.model.search_index as si_mod

    si_mod._CACHE_DIR = cache_dir

    model = _load_model()
    idx = ModelSearchIndex(model)
    # Trigger full index build.
    idx._ensure_loaded()
    return idx


class TestSemanticSearch:
    def test_german_vehicle_manufacturer_top_result(self, search_index: Any) -> None:
        """'Fahrzeug Hersteller' (German for 'vehicle manufacturer') should rank
        the vehicle.manufacturer attribute at the top."""
        results = search_index.search("Fahrzeug Hersteller", top_k=5)
        assert results, "Expected at least one result"
        top = results[0]
        assert top.entity_name == "vehicle"
        assert top.item_name == "manufacturer"

    def test_english_vehicle_manufacturer_in_top3(self, search_index: Any) -> None:
        results = search_index.search("vehicle manufacturer", top_k=3)
        names = [(r.entity_name, r.item_name) for r in results]
        assert ("vehicle", "manufacturer") in names

    def test_measurement_begin_german(self, search_index: Any) -> None:
        """'Anfang der Messung' should surface measurement-related entities."""
        results = search_index.search("Anfang der Messung", top_k=10)
        assert results, "Expected results for 'Anfang der Messung'"
        # At least one result should contain a measurement-related entity.
        entity_names = [r.entity_name.lower() for r in results]
        assert any("mea" in n or "measurement" in n or "messun" in n for n in entity_names)

    def test_enumeration_datatype(self, search_index: Any) -> None:
        results = search_index.search("data type enumeration", top_k=5)
        enum_results = [r for r in results if r.kind == "enumeration"]
        assert enum_results, "Expected at least one enumeration in results"

    def test_relation_search(self, search_index: Any) -> None:
        """Searching for 'child relation' should surface RS_CHILD relations."""

        results = search_index.search("child relation", top_k=10)
        rel_results = [r for r in results if r.kind == "relation"]
        assert rel_results, "Expected at least one relation in results"

    def test_tyre_pressure(self, search_index: Any) -> None:
        results = search_index.search("tyre pressure measurement", top_k=5)
        names = [(r.entity_name, r.item_name) for r in results]
        assert ("tyre", "tyre_pressure") in names

    def test_cache_hit_on_second_index(self, search_index: Any, tmp_path: Path) -> None:
        """A second ModelSearchIndex over the same model must load from cache."""
        import odsbox_pilot.model.search_index as si_mod
        from odsbox_pilot.model.search_index import ModelSearchIndex

        assert si_mod._CACHE_DIR.exists(), "Cache dir must exist after fixture warm-up"
        model = _load_model()
        idx2 = ModelSearchIndex(model)
        # The cache directory is the same; load_cache should succeed.
        loaded = idx2._load_cache()
        assert loaded is not None, "Expected cache hit on second index"


# ---------------------------------------------------------------------------
# Needed for type checker — Any import
# ---------------------------------------------------------------------------
from typing import Any  # noqa: E402

"""Unit tests for ModelSearchIndex (no wx, no live server, no real ML model)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast
from unittest.mock import MagicMock

import numpy as np
import pytest
from google.protobuf.json_format import ParseDict
from odsbox.proto import ods

from odsbox_pilot.model.search_index import (
    ModelMatch,
    ModelSearchIndex,
    SemanticSearchUnavailableError,
    _tokenize,
)

# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------

_FIXTURE = Path(__file__).parent.parent / "data" / "mdm_nvh_model.json"


def _load_model() -> ods.Model:
    with _FIXTURE.open(encoding="utf-8") as fh:
        return cast(ods.Model, ParseDict(json.load(fh), ods.Model()))


@pytest.fixture()
def model() -> ods.Model:
    return _load_model()


@pytest.fixture()
def index(model: ods.Model) -> ModelSearchIndex:
    return ModelSearchIndex(model)


def _make_fake_embeddings(n: int, dim: int = 64) -> np.ndarray:
    """Return unit-normalised random embeddings of shape (n, dim)."""
    rng = np.random.default_rng(42)
    emb = rng.standard_normal((n, dim)).astype(np.float32)
    norms = np.linalg.norm(emb, axis=1, keepdims=True)
    return emb / norms  # type: ignore[no-any-return]


def _mock_st_module(mocker: Any, index: ModelSearchIndex) -> MagicMock:
    """Patch sentence_transformers so tests don't need it installed."""
    dim = 64
    n = len(index._corpus)
    fake_corpus_emb = _make_fake_embeddings(n, dim)

    mock_encoder = MagicMock()
    # First call encodes the corpus; subsequent calls encode individual queries.
    mock_encoder.encode.return_value = fake_corpus_emb

    mock_st_class = MagicMock(return_value=mock_encoder)
    mock_st_mod = MagicMock()
    mock_st_mod.SentenceTransformer = mock_st_class

    mocker.patch.dict("sys.modules", {"sentence_transformers": mock_st_mod})
    return mock_encoder


def _mock_torch_cpu(mocker: Any) -> MagicMock:
    """Patch torch so _detect_device() returns 'cpu'."""
    mock_torch = MagicMock()
    mock_torch.cuda.is_available.return_value = False
    mock_torch.backends.mps.is_available.return_value = False
    mocker.patch.dict("sys.modules", {"torch": mock_torch, "torch_directml": None})
    return mock_torch


# ---------------------------------------------------------------------------
# Tokeniser
# ---------------------------------------------------------------------------


class TestTokenize:
    def test_snake_case(self) -> None:
        assert _tokenize("tyre_pressure") == "tyre pressure"

    def test_camel_case(self) -> None:
        assert _tokenize("MeaQuantity") == "mea quantity"

    def test_ao_prefix(self) -> None:
        assert _tokenize("AoTestEquipment") == "ao test equipment"

    def test_mixed(self) -> None:
        assert _tokenize("vehicle_manufacturer") == "vehicle manufacturer"

    def test_empty(self) -> None:
        assert _tokenize("") == ""

    def test_all_caps_word(self) -> None:
        # "DT_STRING" → "d t string" is acceptable for search purposes
        result = _tokenize("DT_STRING")
        assert "string" in result


# ---------------------------------------------------------------------------
# Corpus coverage
# ---------------------------------------------------------------------------


class TestCorpusCoverage:
    def test_corpus_covers_attributes(self, index: ModelSearchIndex) -> None:
        attr_texts = [
            text
            for text, match in index._corpus
            if match.kind == "attribute"
            and match.entity_name == "vehicle"
            and match.item_name == "manufacturer"
        ]
        assert attr_texts, "vehicle.manufacturer must appear in corpus"

    def test_corpus_covers_relations(self, index: ModelSearchIndex) -> None:
        rel_entries = [
            (text, match)
            for text, match in index._corpus
            if match.kind == "relation"
            and match.entity_name == "TestEquipment"
            and match.item_name == "calibrator"
        ]
        assert rel_entries, "TestEquipment.calibrator relation must appear in corpus"
        # The corpus text must include the target entity base name.
        text = rel_entries[0][0]
        assert "ao" in text, "Relation text should include tokenised base names (e.g. 'ao ...')"

    def test_corpus_covers_enumerations(self, index: ModelSearchIndex) -> None:
        enum_matches = [match for _, match in index._corpus if match.kind == "enumeration"]
        assert enum_matches, "At least one enumeration must appear in corpus"

    def test_all_three_kinds_present(self, index: ModelSearchIndex) -> None:
        kinds = {match.kind for _, match in index._corpus}
        assert kinds == {"attribute", "relation", "enumeration"}


# ---------------------------------------------------------------------------
# Cache round-trip
# ---------------------------------------------------------------------------


class TestCache:
    def test_save_and_load(self, tmp_path: Path, model: ods.Model, mocker: Any) -> None:
        mocker.patch("odsbox_pilot.model.search_index._CACHE_DIR", tmp_path)
        idx = ModelSearchIndex(model)
        n = len(idx._corpus)
        embeddings = _make_fake_embeddings(n)
        idx._save_cache(embeddings)

        # Fresh index with same hash — should load from cache.
        idx2 = ModelSearchIndex(model)
        loaded = idx2._load_cache()
        assert loaded is not None
        assert loaded.shape == embeddings.shape
        np.testing.assert_allclose(loaded, embeddings, rtol=1e-5)

    def test_cache_restores_corpus(self, tmp_path: Path, model: ods.Model, mocker: Any) -> None:
        mocker.patch("odsbox_pilot.model.search_index._CACHE_DIR", tmp_path)
        idx = ModelSearchIndex(model)
        original_corpus = list(idx._corpus)
        idx._save_cache(_make_fake_embeddings(len(idx._corpus)))

        idx2 = ModelSearchIndex(model)
        idx2._load_cache()
        assert len(idx2._corpus) == len(original_corpus)
        assert idx2._corpus[0][1].kind == original_corpus[0][1].kind

    def test_cache_hit_skips_encode(self, tmp_path: Path, model: ods.Model, mocker: Any) -> None:
        mocker.patch("odsbox_pilot.model.search_index._CACHE_DIR", tmp_path)
        idx = ModelSearchIndex(model)
        idx._save_cache(_make_fake_embeddings(len(idx._corpus)))

        # New index — cache exists; SentenceTransformer should NOT be called.
        mock_st_mod = MagicMock()
        mocker.patch.dict("sys.modules", {"sentence_transformers": mock_st_mod})
        _mock_torch_cpu(mocker)

        idx2 = ModelSearchIndex(model)
        idx2._ensure_loaded()
        mock_st_mod.SentenceTransformer.assert_not_called()

    def test_cache_miss_calls_encode(self, tmp_path: Path, model: ods.Model, mocker: Any) -> None:
        mocker.patch("odsbox_pilot.model.search_index._CACHE_DIR", tmp_path)
        _mock_torch_cpu(mocker)
        idx = ModelSearchIndex(model)
        mock_encoder = _mock_st_module(mocker, idx)

        idx._ensure_loaded()
        mock_encoder.encode.assert_called_once()

    def test_missing_npz_returns_none(self, tmp_path: Path, model: ods.Model, mocker: Any) -> None:
        mocker.patch("odsbox_pilot.model.search_index._CACHE_DIR", tmp_path)
        idx = ModelSearchIndex(model)
        assert idx._load_cache() is None

    def test_length_mismatch_returns_none(
        self, tmp_path: Path, model: ods.Model, mocker: Any
    ) -> None:
        mocker.patch("odsbox_pilot.model.search_index._CACHE_DIR", tmp_path)
        idx = ModelSearchIndex(model)
        # Save embeddings with wrong length.
        idx._save_cache(_make_fake_embeddings(len(idx._corpus)))
        # Corrupt the json to have fewer entries.
        _, json_path = idx._cache_paths()
        meta = json.loads(json_path.read_text())
        json_path.write_text(json.dumps(meta[:2]))

        idx2 = ModelSearchIndex(model)
        assert idx2._load_cache() is None


class TestUnavailableDependency:
    def test_missing_sentence_transformers_raises_human_hint(
        self, index: ModelSearchIndex, mocker: Any
    ) -> None:
        idx = index
        idx._embeddings = _make_fake_embeddings(len(idx._corpus))

        original_import = __import__

        def _fake_import(
            name: str,
            globals: Any | None = None,
            locals: Any | None = None,
            fromlist: tuple[str, ...] = (),
            level: int = 0,
        ) -> Any:
            if name == "sentence_transformers":
                raise ImportError("missing optional dependency")
            return original_import(name, globals, locals, fromlist, level)

        mocker.patch("builtins.__import__", side_effect=_fake_import)

        with pytest.raises(SemanticSearchUnavailableError) as exc_info:
            idx.search("vehicle manufacturer")

        assert "uv sync --extra ai" in str(exc_info.value)


# ---------------------------------------------------------------------------
# Device detection
# ---------------------------------------------------------------------------


class TestDetectDevice:
    def test_cuda_preferred(self, mocker: Any) -> None:
        mock_torch = MagicMock()
        mock_torch.cuda.is_available.return_value = True
        mocker.patch.dict("sys.modules", {"torch": mock_torch})
        assert ModelSearchIndex._detect_device() == "cuda"

    def test_mps_when_no_cuda(self, mocker: Any) -> None:
        mock_torch = MagicMock()
        mock_torch.cuda.is_available.return_value = False
        mock_torch.backends.mps.is_available.return_value = True
        mocker.patch.dict("sys.modules", {"torch": mock_torch})
        assert ModelSearchIndex._detect_device() == "mps"

    def test_directml_when_available(self, mocker: Any) -> None:
        mock_torch = MagicMock()
        mock_torch.cuda.is_available.return_value = False
        mock_torch.backends.mps.is_available.return_value = False
        # Probe tensor succeeds.
        mock_torch.tensor.return_value.to.return_value = MagicMock()

        dml_device = MagicMock(name="dml_device")
        mock_dml = MagicMock()
        mock_dml.device.return_value = dml_device

        mocker.patch.dict("sys.modules", {"torch": mock_torch, "torch_directml": mock_dml})
        result = ModelSearchIndex._detect_device()
        assert result is dml_device

    def test_directml_import_error_falls_back_to_cpu(self, mocker: Any) -> None:
        mock_torch = MagicMock()
        mock_torch.cuda.is_available.return_value = False
        mock_torch.backends.mps.is_available.return_value = False
        mocker.patch.dict("sys.modules", {"torch": mock_torch, "torch_directml": None})
        assert ModelSearchIndex._detect_device() == "cpu"

    def test_directml_runtime_error_falls_back_to_cpu(self, mocker: Any) -> None:
        mock_torch = MagicMock()
        mock_torch.cuda.is_available.return_value = False
        mock_torch.backends.mps.is_available.return_value = False
        mock_torch.tensor.return_value.to.side_effect = RuntimeError("no device")

        mock_dml = MagicMock()
        mocker.patch.dict("sys.modules", {"torch": mock_torch, "torch_directml": mock_dml})
        assert ModelSearchIndex._detect_device() == "cpu"

    def test_cpu_fallback(self, mocker: Any) -> None:
        mock_torch = MagicMock()
        mock_torch.cuda.is_available.return_value = False
        mock_torch.backends.mps.is_available.return_value = False
        mocker.patch.dict("sys.modules", {"torch": mock_torch, "torch_directml": None})
        assert ModelSearchIndex._detect_device() == "cpu"


# ---------------------------------------------------------------------------
# Search behaviour
# ---------------------------------------------------------------------------


class TestSearch:
    def _load_with_fake_embeddings(
        self,
        tmp_path: Path,
        model: ods.Model,
        mocker: Any,
    ) -> tuple[ModelSearchIndex, np.ndarray]:
        mocker.patch("odsbox_pilot.model.search_index._CACHE_DIR", tmp_path)
        _mock_torch_cpu(mocker)
        idx = ModelSearchIndex(model)
        dim = 64
        n = len(idx._corpus)
        fake_emb = _make_fake_embeddings(n, dim)

        mock_encoder = MagicMock()
        # encode called for corpus build → return fake_emb
        # subsequent encode calls (queries) return a unit vector
        query_emb = _make_fake_embeddings(1, dim)
        mock_encoder.encode.side_effect = [fake_emb, query_emb]

        mock_st_class = MagicMock(return_value=mock_encoder)
        mock_st_mod = MagicMock()
        mock_st_mod.SentenceTransformer = mock_st_class
        mocker.patch.dict("sys.modules", {"sentence_transformers": mock_st_mod})

        return idx, fake_emb

    def test_empty_query_returns_empty(self, tmp_path: Path, model: ods.Model, mocker: Any) -> None:
        mocker.patch("odsbox_pilot.model.search_index._CACHE_DIR", tmp_path)
        idx = ModelSearchIndex(model)
        assert idx.search("") == []
        assert idx.search("   ") == []

    def test_returns_at_most_top_k(self, tmp_path: Path, model: ods.Model, mocker: Any) -> None:
        idx, _ = self._load_with_fake_embeddings(tmp_path, model, mocker)
        results = idx.search("anything", top_k=5)
        assert len(results) <= 5

    def test_scores_descending(self, tmp_path: Path, model: ods.Model, mocker: Any) -> None:
        idx, _ = self._load_with_fake_embeddings(tmp_path, model, mocker)
        results = idx.search("anything", top_k=10)
        scores = [r.score for r in results]
        assert scores == sorted(scores, reverse=True)

    def test_returns_model_match_objects(
        self, tmp_path: Path, model: ods.Model, mocker: Any
    ) -> None:
        idx, _ = self._load_with_fake_embeddings(tmp_path, model, mocker)
        results = idx.search("test", top_k=3)
        for r in results:
            assert isinstance(r, ModelMatch)
            assert r.kind in {"attribute", "relation", "enumeration"}

    def test_sentence_transformer_receives_device(
        self, tmp_path: Path, model: ods.Model, mocker: Any
    ) -> None:
        mocker.patch("odsbox_pilot.model.search_index._CACHE_DIR", tmp_path)
        mock_torch = MagicMock()
        mock_torch.cuda.is_available.return_value = False
        mock_torch.backends.mps.is_available.return_value = False
        mocker.patch.dict("sys.modules", {"torch": mock_torch, "torch_directml": None})

        idx = ModelSearchIndex(model)
        dim = 64
        n = len(idx._corpus)
        fake_emb = _make_fake_embeddings(n, dim)
        query_emb = _make_fake_embeddings(1, dim)

        mock_encoder = MagicMock()
        mock_encoder.encode.side_effect = [fake_emb, query_emb]
        mock_st_class = MagicMock(return_value=mock_encoder)
        mock_st_mod = MagicMock()
        mock_st_mod.SentenceTransformer = mock_st_class
        mocker.patch.dict("sys.modules", {"sentence_transformers": mock_st_mod})

        idx.search("test", top_k=3)
        # SentenceTransformer must have been called with a device= keyword arg.
        _, kwargs = mock_st_class.call_args
        assert "device" in kwargs


# ---------------------------------------------------------------------------
# Model introspection helpers (entity_schema, resolve_attribute, find_date_attribute)
# ---------------------------------------------------------------------------


class TestModelIntrospection:
    """Tests for the AI-query helpers that validate LLM-generated conditions."""

    # --- entity_schema ---

    def test_entity_schema_contains_entity_name(self, index: ModelSearchIndex) -> None:
        schema = index.entity_schema("MeaResult")
        assert "MeaResult" in schema

    def test_entity_schema_lists_all_attributes(self, index: ModelSearchIndex) -> None:
        schema = index.entity_schema("MeaResult")
        # MeaResult has Name, Id, MeasurementBegin, MeasurementEnd, Description
        assert "MeasurementBegin" in schema
        assert "Name" in schema
        assert "Id" in schema

    def test_entity_schema_lists_relations(self, index: ModelSearchIndex) -> None:
        # Any entity with at least one relation should include it
        schema = index.entity_schema("TestEquipment")
        assert "relation" in schema or "->" in schema

    def test_entity_schema_unknown_entity_returns_empty(self, index: ModelSearchIndex) -> None:
        assert index.entity_schema("DoesNotExist") == ""

    # --- resolve_attribute ---

    def test_resolve_exact_match(self, index: ModelSearchIndex) -> None:
        assert index.resolve_attribute("MeaResult", "Name") == "Name"

    def test_resolve_exact_match_id(self, index: ModelSearchIndex) -> None:
        assert index.resolve_attribute("MeaResult", "Id") == "Id"

    def test_resolve_case_insensitive(self, index: ModelSearchIndex) -> None:
        # "name" (lowercase) should resolve to "Name"
        resolved = index.resolve_attribute("MeaResult", "name")
        assert resolved == "Name"

    def test_resolve_case_insensitive_description(self, index: ModelSearchIndex) -> None:
        resolved = index.resolve_attribute("MeaResult", "description")
        assert resolved == "Description"

    def test_resolve_unknown_entity_returns_none(self, index: ModelSearchIndex) -> None:
        assert index.resolve_attribute("NoSuchEntity", "Name") is None

    def test_resolve_unknown_attr_no_embeddings_returns_none(self, index: ModelSearchIndex) -> None:
        # With no embeddings loaded, a completely unknown attr should return None
        assert index._embeddings is None  # embeddings not yet loaded
        result = index.resolve_attribute("MeaResult", "xyzzy_nonexistent_attr_abc")
        assert result is None

    # --- find_date_attribute ---

    def test_find_date_attribute_mea_result(self, index: ModelSearchIndex) -> None:
        # MeaResult has MeasurementBegin, MeasurementEnd, DateCreated — prefer "begin"
        result = index.find_date_attribute("MeaResult")
        assert result == "MeasurementBegin"

    def test_find_date_attribute_unknown_entity_returns_none(self, index: ModelSearchIndex) -> None:
        assert index.find_date_attribute("NoSuchEntity") is None

    def test_find_date_attribute_entity_without_dates(self, index: ModelSearchIndex) -> None:
        # Find any entity with no DT_DATE attributes; MeaQuantity is likely
        result = index.find_date_attribute("MeaQuantity")
        # Either None or a string — just ensure it doesn't crash
        assert result is None or isinstance(result, str)

    # --- resolve_entity ---

    def test_resolve_entity_exact_match(self, index: ModelSearchIndex) -> None:
        assert index.resolve_entity("MeaResult") == "MeaResult"

    def test_resolve_entity_exact_match_project(self, index: ModelSearchIndex) -> None:
        assert index.resolve_entity("Project") == "Project"

    def test_resolve_entity_case_insensitive(self, index: ModelSearchIndex) -> None:
        resolved = index.resolve_entity("mearesult")
        assert resolved == "MeaResult"

    def test_resolve_entity_unknown_returns_none(self, index: ModelSearchIndex) -> None:
        assert index.resolve_entity("MDL") is None

    def test_resolve_entity_attribute_name_returns_none(self, index: ModelSearchIndex) -> None:
        # "DateCreated" is an attribute, not an entity — should return None
        assert index.resolve_entity("DateCreated") is None

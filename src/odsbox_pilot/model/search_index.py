"""Semantic search index over an ODS model (attributes, relations, enumerations).

Uses ``sentence-transformers`` with the multilingual MiniLM model to produce
L2-normalised embeddings; cosine similarity is computed as a dot product.

Embeddings are cached on disk (``~/.ods-pilot/search_cache/``) keyed by a
SHA-256 hash of the serialised model protobuf so the index is only rebuilt
when the server model changes.

Device selection priority (fastest first):
  1. CUDA (NVIDIA GPU)
  2. MPS (Apple Silicon)
  3. DirectML via ``torch-directml`` (Windows Copilot+ NPU/GPU — Qualcomm Snapdragon X,
     AMD Ryzen AI, Intel iGPU/Arc — install with ``uv sync --extra npu``)
  4. CPU (fallback)

Note: ``torch.xpu`` (Intel IPEX) was archived in March 2026 and is not used.
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Literal

import numpy as np
from odsbox.proto import ods

from odsbox_pilot.models import CONFIG_DIR

log = logging.getLogger(__name__)

_MODEL_NAME = "paraphrase-multilingual-MiniLM-L12-v2"
_CACHE_DIR: Path = CONFIG_DIR / "search_cache"

# Matches the boundary between a lowercase letter and an uppercase letter, or
# between two uppercase letters where the second starts a new word (e.g. "XMLParser").
_CAMEL_RE = re.compile(r"(?<=[a-z])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])")


# ---------------------------------------------------------------------------
# Public data types
# ---------------------------------------------------------------------------


@dataclass
class ModelMatch:
    """A single search result referencing an ODS model element."""

    kind: Literal["attribute", "relation", "enumeration"]
    entity_name: str  # empty for enumerations
    entity_base_name: str  # empty for enumerations
    item_name: str  # attribute / relation / enumeration name
    item_base_name: str
    data_type: int  # ods.DataTypeEnum value; 0 for relations & enumerations
    score: float  # cosine similarity in [0, 1]


# ---------------------------------------------------------------------------
# Text helpers
# ---------------------------------------------------------------------------


def _tokenize(name: str) -> str:
    """Split snake_case and CamelCase, lowercase, and join with spaces.

    Examples::

        >>> _tokenize("tyre_pressure")
        'tyre pressure'
        >>> _tokenize("MeaQuantity")
        'mea quantity'
        >>> _tokenize("AoTestEquipment")
        'ao test equipment'
    """
    parts: list[str] = []
    for segment in name.split("_"):
        sub = _CAMEL_RE.sub(" ", segment)
        parts.extend(sub.split())
    return " ".join(p.lower() for p in parts if p)


# ---------------------------------------------------------------------------
# Index
# ---------------------------------------------------------------------------


class ModelSearchIndex:
    """Embedding-based semantic search index for an ODS ``Model``.

    The index is built lazily on the first :meth:`search` call and the
    embeddings are cached on disk so subsequent starts skip the costly
    encoding step as long as the server model has not changed.

    Usage::

        index = ModelSearchIndex(model)
        results = index.search("Fahrzeug Hersteller", top_k=10)
        for match in results:
            print(match.kind, match.entity_name, match.item_name, match.score)
    """

    def __init__(self, model: ods.Model) -> None:
        self._model = model
        self._hash: str = hashlib.sha256(model.SerializeToString()).hexdigest()
        self._corpus: list[tuple[str, ModelMatch]] = self._build_corpus()
        self._embeddings: np.ndarray | None = None
        self._encoder: Any = None  # SentenceTransformer instance, created lazily

    # ------------------------------------------------------------------
    # Corpus construction
    # ------------------------------------------------------------------

    def _build_corpus(self) -> list[tuple[str, ModelMatch]]:
        """Build the list of (text, ModelMatch) pairs from the ODS model."""
        entries: list[tuple[str, ModelMatch]] = []

        for entity in self._model.entities.values():
            e_text = f"{_tokenize(entity.name)} {_tokenize(entity.base_name)}"

            for attr in entity.attributes.values():
                text = f"{e_text} {_tokenize(attr.name)} {_tokenize(attr.base_name)}"
                entries.append(
                    (
                        text,
                        ModelMatch(
                            kind="attribute",
                            entity_name=entity.name,
                            entity_base_name=entity.base_name,
                            item_name=attr.name,
                            item_base_name=attr.base_name,
                            data_type=int(attr.data_type),
                            score=0.0,
                        ),
                    )
                )

            for rel in entity.relations.values():
                text = (
                    f"{e_text} {_tokenize(rel.name)} {_tokenize(rel.base_name)} "
                    f"{_tokenize(rel.entity_name)} {_tokenize(rel.entity_base_name)} "
                    f"{_tokenize(rel.inverse_name)} {_tokenize(rel.inverse_base_name)}"
                )
                entries.append(
                    (
                        text,
                        ModelMatch(
                            kind="relation",
                            entity_name=entity.name,
                            entity_base_name=entity.base_name,
                            item_name=rel.name,
                            item_base_name=rel.base_name,
                            data_type=0,
                            score=0.0,
                        ),
                    )
                )

        for enum in self._model.enumerations.values():
            items_text = " ".join(_tokenize(k) for k in enum.items)
            text = f"{_tokenize(enum.name)} {items_text}"
            entries.append(
                (
                    text,
                    ModelMatch(
                        kind="enumeration",
                        entity_name="",
                        entity_base_name="",
                        item_name=enum.name,
                        item_base_name="",
                        data_type=0,
                        score=0.0,
                    ),
                )
            )

        return entries

    # ------------------------------------------------------------------
    # Disk cache
    # ------------------------------------------------------------------

    def _cache_paths(self) -> tuple[Path, Path]:
        """Return the (.npz, .json) cache file paths for this model hash."""
        _CACHE_DIR.mkdir(parents=True, exist_ok=True)
        base = _CACHE_DIR / self._hash
        return base.with_suffix(".npz"), base.with_suffix(".json")

    def _save_cache(self, embeddings: np.ndarray) -> None:
        npz_path, json_path = self._cache_paths()
        np.savez_compressed(str(npz_path), embeddings=embeddings)
        meta: list[dict[str, Any]] = []
        for text, match in self._corpus:
            d = asdict(match)
            d["text"] = text
            meta.append(d)
        json_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")
        log.debug("Saved search index cache → %s", npz_path)

    def _load_cache(self) -> np.ndarray | None:
        """Try to load cached embeddings; return ``None`` on any failure."""
        npz_path, json_path = self._cache_paths()
        if not npz_path.exists() or not json_path.exists():
            return None
        try:
            data = np.load(str(npz_path))
            embeddings: np.ndarray = data["embeddings"]
            raw: list[dict[str, Any]] = json.loads(json_path.read_text(encoding="utf-8"))
            if len(raw) != len(embeddings):
                log.warning(
                    "Search cache length mismatch (%d vs %d) — rebuilding.",
                    len(raw),
                    len(embeddings),
                )
                return None
            corpus: list[tuple[str, ModelMatch]] = []
            for item in raw:
                corpus.append(
                    (
                        item["text"],
                        ModelMatch(
                            kind=item["kind"],
                            entity_name=item["entity_name"],
                            entity_base_name=item["entity_base_name"],
                            item_name=item["item_name"],
                            item_base_name=item["item_base_name"],
                            data_type=int(item["data_type"]),
                            score=0.0,
                        ),
                    )
                )
            self._corpus = corpus
            log.info("Loaded search index from cache (%s).", npz_path)
            return embeddings
        except Exception:
            log.warning("Failed to load search cache — will rebuild.", exc_info=True)
            return None

    # ------------------------------------------------------------------
    # Device detection
    # ------------------------------------------------------------------

    @staticmethod
    def _detect_device() -> Any:
        """Return the best available compute device for sentence-transformers.

        Priority: CUDA → MPS (Apple Silicon) → DirectML (Windows Copilot+ NPU/GPU) → CPU.

        ``torch-directml`` has no availability boolean; it is probed by attempting to
        move a test tensor to the device.  ``torch.xpu`` (Intel IPEX) was archived in
        March 2026 and is intentionally not included.
        """
        import torch  # noqa: PLC0415

        if torch.cuda.is_available():
            log.info("Semantic search: using CUDA device.")
            return "cuda"

        if torch.backends.mps.is_available():
            log.info("Semantic search: using MPS (Apple Silicon) device.")
            return "mps"

        try:
            import torch_directml  # noqa: PLC0415

            dml = torch_directml.device()
            torch.tensor([1.0]).to(dml)  # probe — raises RuntimeError if unavailable
            log.info("Semantic search: using DirectML (Windows Copilot+ NPU/GPU) device.")
            return dml
        except Exception:  # noqa: BLE001 — ImportError or RuntimeError
            pass

        log.info("Semantic search: using CPU device.")
        return "cpu"

    # ------------------------------------------------------------------
    # Loading and searching
    # ------------------------------------------------------------------

    def _ensure_encoder(self) -> None:
        """Ensure the SentenceTransformer encoder is initialised."""
        if self._encoder is not None:
            return
        from sentence_transformers import SentenceTransformer  # noqa: PLC0415

        device = self._detect_device()
        self._encoder = SentenceTransformer(_MODEL_NAME, device=device)

    def _ensure_loaded(self) -> None:
        """Ensure the embedding model and corpus embeddings are ready."""
        if self._embeddings is not None:
            return

        cached = self._load_cache()
        if cached is not None:
            self._embeddings = cached
            return

        # No cache — encode the full corpus now.
        self._ensure_encoder()
        assert self._encoder is not None  # noqa: S101
        texts = [text for text, _ in self._corpus]
        log.info("Building semantic search index (%d entries) …", len(texts))
        emb: np.ndarray = self._encoder.encode(
            texts,
            normalize_embeddings=True,
            show_progress_bar=False,
            convert_to_numpy=True,
        )
        self._embeddings = emb
        self._save_cache(emb)
        log.info("Search index built and cached.")

    def warm_up(self) -> None:
        """Pre-load embeddings *and* the query encoder.  Blocking — call from a background thread.

        After this returns, :meth:`search` runs without any weight-loading overhead.
        """
        self._ensure_loaded()  # loads/builds embedding matrix
        self._ensure_encoder()  # ensures encoder is ready for query encoding

    def search(self, query: str, top_k: int = 20) -> list[ModelMatch]:
        """Return up to *top_k* :class:`ModelMatch` objects sorted by cosine similarity.

        Returns an empty list for blank queries or empty corpora.
        """
        if not query.strip() or not self._corpus:
            return []

        self._ensure_loaded()
        self._ensure_encoder()
        assert self._embeddings is not None  # noqa: S101

        q_emb: np.ndarray = self._encoder.encode(
            [query],
            normalize_embeddings=True,
            show_progress_bar=False,
            convert_to_numpy=True,
        )[0]

        scores: np.ndarray = self._embeddings @ q_emb
        n = min(top_k, len(scores))
        top_idx = np.argpartition(scores, -n)[-n:]
        top_idx = top_idx[np.argsort(scores[top_idx])[::-1]]

        results: list[ModelMatch] = []
        for i in top_idx:
            _, match = self._corpus[int(i)]
            results.append(
                ModelMatch(
                    kind=match.kind,
                    entity_name=match.entity_name,
                    entity_base_name=match.entity_base_name,
                    item_name=match.item_name,
                    item_base_name=match.item_base_name,
                    data_type=match.data_type,
                    score=float(scores[int(i)]),
                )
            )
        return results

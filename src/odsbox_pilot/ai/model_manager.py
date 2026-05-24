"""Model download and lifecycle management."""

from __future__ import annotations

import logging
from collections.abc import Callable
from pathlib import Path

from odsbox_pilot.models import CONFIG_DIR

log = logging.getLogger(__name__)

DEFAULT_MODEL_ID = "OpenVINO/qwen2.5-1.5b-instruct-int4-ov"
DEFAULT_MODEL_CACHE_DIR = CONFIG_DIR / "models"


class ModelManager:
    """Manage OpenVINO model downloads and local cache."""

    def __init__(self, cache_dir: Path | None = None) -> None:
        """Initialize the model manager.

        Args:
            cache_dir: Local cache directory (defaults to ~/.ods-pilot/models/).
        """
        self._cache_dir = cache_dir or DEFAULT_MODEL_CACHE_DIR
        self._cache_dir.mkdir(parents=True, exist_ok=True)

    def is_downloaded(self, model_id: str) -> bool:
        """Check if a model is already downloaded locally.

        Args:
            model_id: HuggingFace model ID (e.g., "OpenVINO/qwen2.5-1.5b-instruct-int4-ov").

        Returns:
            True if model exists locally, False otherwise.
        """
        model_dir = self._get_model_dir(model_id)
        # Check for required OpenVINO files
        required_files = ["openvino_model.xml", "openvino_model.bin"]
        return all((model_dir / f).exists() for f in required_files)

    def download_model(
        self,
        model_id: str,
        progress_callback: Callable[[float, str], None] | None = None,
    ) -> Path:
        """Download a model from HuggingFace Hub.

        Args:
            model_id: HuggingFace model ID.
            progress_callback: Optional callback(fraction: float, status: str) for progress.

        Returns:
            Path to the downloaded model directory.

        Raises:
            ImportError: If huggingface_hub is not installed.
            RuntimeError: If download fails.
        """
        try:
            from huggingface_hub import snapshot_download
        except ImportError as e:
            msg = (
                "huggingface-hub not installed. Install with:\n"
                "  uv sync --extra ai\n"
                "or:\n"
                "  uv pip install huggingface-hub"
            )
            raise ImportError(msg) from e

        model_dir = self._get_model_dir(model_id)

        if self.is_downloaded(model_id):
            log.info(f"Model {model_id} already downloaded at {model_dir}")
            if progress_callback:
                progress_callback(1.0, "Already downloaded")
            return model_dir

        log.info(f"Downloading model {model_id} to {model_dir}...")
        if progress_callback:
            progress_callback(0.0, "Starting download...")

        try:
            # Download the model
            snapshot_download(
                repo_id=model_id,
                local_dir=str(model_dir),
            )
            log.info(f"Model {model_id} downloaded successfully")
            if progress_callback:
                progress_callback(1.0, "Download complete")
            return model_dir
        except Exception as e:
            msg = f"Failed to download model {model_id}: {e}"
            log.error(msg)
            raise RuntimeError(msg) from e

    def _get_model_dir(self, model_id: str) -> Path:
        """Get local directory path for a model.

        Args:
            model_id: HuggingFace model ID.

        Returns:
            Path to the model directory.
        """
        # Create a safe directory name from model ID
        safe_name = model_id.replace("/", "--")
        return self._cache_dir / safe_name

    def get_model_path(self, model_id: str) -> Path | None:
        """Get path to a downloaded model, or None if not downloaded.

        Args:
            model_id: HuggingFace model ID.

        Returns:
            Path to model directory if downloaded, None otherwise.
        """
        if self.is_downloaded(model_id):
            return self._get_model_dir(model_id)
        return None

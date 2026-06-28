"""Unit tests for ModelManager."""

from __future__ import annotations

from pathlib import Path

from odsbox_pilot.ai.model_manager import ModelManager


class TestModelManager:
    def test_get_model_dir_uses_cache_dir(self, tmp_path: Path) -> None:
        manager = ModelManager(tmp_path)
        assert manager.get_model_dir("OpenVINO/qwen2.5-1.5b-instruct-int4-ov") == (
            tmp_path / "OpenVINO--qwen2.5-1.5b-instruct-int4-ov"
        )

    def test_get_model_path_returns_none_when_files_missing(self, tmp_path: Path) -> None:
        manager = ModelManager(tmp_path)
        assert manager.get_model_path("OpenVINO/qwen2.5-1.5b-instruct-int4-ov") is None

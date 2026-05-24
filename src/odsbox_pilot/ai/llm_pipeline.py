"""OpenVINO GenAI LLM pipeline wrapper for local inference."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)


class OvLlmPipeline:
    """Wrapper around openvino_genai.LLMPipeline for chat-based inference.

    Supports device selection priority: NPU → GPU → CPU.
    Uses OpenAI-style chat messages format.
    """

    def __init__(self, model_dir: Path, device: str = "NPU") -> None:
        """Initialize the pipeline (lazy-loaded on first generate call).

        Args:
            model_dir: Path to the OpenVINO model directory (IR format).
            device: Target device string ("NPU", "GPU", or "CPU").
        """
        self._model_dir = model_dir
        self._device = device
        self._pipeline: Any = None  # openvino_genai.LLMPipeline instance

    def _ensure_loaded(self) -> None:
        """Lazy-load the LLM pipeline on first use."""
        if self._pipeline is not None:
            return

        try:
            import openvino_genai as ov_genai
        except ImportError as e:
            msg = (
                "openvino-genai not installed. Install with:\n"
                "  uv sync --extra ai\n"
                "or:\n"
                "  uv pip install openvino-genai"
            )
            raise ImportError(msg) from e

        # Try devices in priority order
        devices_to_try = []
        if self._device == "NPU":
            devices_to_try = ["NPU", "GPU", "CPU"]
        elif self._device == "GPU":
            devices_to_try = ["GPU", "CPU"]
        else:
            devices_to_try = ["CPU"]

        last_error = None
        for device in devices_to_try:
            try:
                log.info(f"Loading LLM pipeline on {device}...")
                # NPU stateful pipelines default to 1024 prompt tokens; raise
                # the limit so larger schema contexts fit without truncation.
                npu_kwargs: dict[str, int] = (
                    {"MAX_PROMPT_LEN": 2048, "MAX_SEQUENCE_LEN": 3072} if device == "NPU" else {}
                )
                self._pipeline = ov_genai.LLMPipeline(
                    str(self._model_dir),
                    device=device,
                    **npu_kwargs,
                )
                log.info(f"LLM pipeline loaded successfully on {device}")
                self._device = device  # Update to the device that worked
                return
            except Exception as e:
                log.warning(f"Failed to load on {device}: {e}")
                last_error = e
                continue

        # All devices failed
        msg = f"Failed to load LLM pipeline on any device. Last error: {last_error}"
        raise RuntimeError(msg) from last_error

    def generate(
        self,
        messages: list[dict[str, str]],
        max_new_tokens: int = 512,
        temperature: float = 0.7,
        top_p: float = 0.9,
    ) -> str:
        """Generate a response from chat messages.

        Args:
            messages: OpenAI-style chat messages (list of {"role": "...", "content": "..."}).
            max_new_tokens: Maximum number of tokens to generate.
            temperature: Sampling temperature (0 = greedy, higher = more random).
            top_p: Nucleus sampling probability threshold.

        Returns:
            Generated text response (string).
        """
        self._ensure_loaded()

        # Build prompt from messages (simple Qwen-style template)
        prompt_parts: list[str] = []
        for msg in messages:
            role = msg["role"]
            content = msg["content"]
            if role == "system":
                prompt_parts.append(f"<|im_start|>system\n{content}<|im_end|>")
            elif role == "user":
                prompt_parts.append(f"<|im_start|>user\n{content}<|im_end|>")
            elif role == "assistant":
                prompt_parts.append(f"<|im_start|>assistant\n{content}<|im_end|>")

        prompt_parts.append("<|im_start|>assistant\n")
        prompt = "\n".join(prompt_parts)

        # Configure generation
        config = self._pipeline.get_generation_config()
        config.max_new_tokens = max_new_tokens
        config.temperature = temperature
        config.top_p = top_p
        config.do_sample = temperature > 0

        # Generate
        log.debug(f"Generating with prompt length {len(prompt)} chars")
        result = self._pipeline.generate(prompt, config)
        log.debug(f"Generated {len(result)} chars")

        # Cast to str since we know LLMPipeline.generate returns str
        return str(result)

    @property
    def device(self) -> str:
        """Return the active device (may differ from requested if fallback occurred)."""
        return self._device

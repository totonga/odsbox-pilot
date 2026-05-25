"""Shared test fixtures."""

from __future__ import annotations

import pytest


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line("markers", "integration: tests requiring a live ASAM ODS server")
    config.addinivalue_line("markers", "slow: tests that take a long time to run")

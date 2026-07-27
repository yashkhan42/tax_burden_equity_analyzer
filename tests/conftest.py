"""Shared guards for the test suite.

Loading the model may fetch the canonical artifact over the network when none is
on disk. That behaviour is what lets a fresh Streamlit Community Cloud deploy
serve real numbers, but it must never run inside the tests: it would pull 263 MB
on every run, make offline runs fail, and turn a unit test into an integration
test against GitHub.

Fetching is therefore disabled for every test by default. A test that wants to
exercise the fetch path re-enables it and monkeypatches the download, so the
path is still covered without touching the network.
"""

from __future__ import annotations

import pytest

import model_interface as mi


@pytest.fixture(autouse=True)
def _no_artifact_download(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(mi.ARTIFACT_FETCH_ENV, "0")
    mi._load_model.cache_clear()

"""Artifact bootstrap tests use in-memory responses; no network is touched."""

from __future__ import annotations

import hashlib
import io
import json
from pathlib import Path

import pytest

from backend.artifacts import (
    ArtifactBootstrapError,
    bootstrap_artifact,
    download_artifact,
)


class FakeResponse(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.close()


def metadata(path: Path, payload: bytes) -> None:
    path.write_text(
        json.dumps(
            {
                "final_model": {
                    "artifact_sha256": hashlib.sha256(payload).hexdigest()
                }
            }
        )
    )


def test_download_streams_verifies_token_and_promotes_atomically(tmp_path: Path) -> None:
    payload = b"trained-model-bytes" * 100
    metrics = tmp_path / "rf_metrics.json"
    destination = tmp_path / "rf_eff_rate.joblib"
    metadata(metrics, payload)
    seen = {}

    def opener(request, timeout):
        seen["authorization"] = request.get_header("Authorization")
        seen["timeout"] = timeout
        return FakeResponse(payload)

    download_artifact(
        url="https://example.test/model",
        destination=destination,
        metadata_path=metrics,
        token="secret",
        opener=opener,
    )
    assert destination.read_bytes() == payload
    assert not destination.with_name(f"{destination.name}.part").exists()
    assert seen == {"authorization": "Bearer secret", "timeout": 60}


def test_checksum_failure_never_promotes_and_removes_part(tmp_path: Path) -> None:
    expected = b"right"
    metrics = tmp_path / "rf_metrics.json"
    destination = tmp_path / "rf_eff_rate.joblib"
    metadata(metrics, expected)

    with pytest.raises(ArtifactBootstrapError, match="checksum"):
        download_artifact(
            url="https://example.test/model",
            destination=destination,
            metadata_path=metrics,
            opener=lambda request, timeout: FakeResponse(b"wrong"),
        )
    assert not destination.exists()
    assert not destination.with_name(f"{destination.name}.part").exists()


def test_existing_artifact_is_used_without_download(tmp_path: Path, monkeypatch) -> None:
    artifact = tmp_path / "existing.joblib"
    artifact.write_bytes(b"already-here")
    monkeypatch.setenv("TAX_MODEL_PATH", str(artifact))
    monkeypatch.setenv("TAX_MODEL_DOWNLOAD_URL", "https://example.test/not-used")
    assert bootstrap_artifact() == "local"


def test_missing_artifact_without_url_stays_degraded(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("TAX_MODEL_PATH", str(tmp_path / "missing.joblib"))
    monkeypatch.delenv("TAX_MODEL_DOWNLOAD_URL", raising=False)
    assert bootstrap_artifact() is None

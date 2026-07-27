"""Optional, checksum-verified startup bootstrap for the trained artifact."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import BinaryIO, Callable, Literal, Protocol
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_ARTIFACT = ROOT / "models" / "rf_eff_rate.joblib"
DEFAULT_METADATA = ROOT / "models" / "rf_metrics.json"
DOWNLOAD_CHUNK_SIZE = 1024 * 1024

ArtifactSource = Literal["local", "downloaded"]


class DownloadResponse(Protocol):
    def __enter__(self) -> BinaryIO: ...
    def __exit__(self, exc_type, exc_value, traceback) -> None: ...


class ArtifactBootstrapError(RuntimeError):
    """The optional download could not produce verified model bytes."""


def configured_artifact_path() -> Path:
    configured = os.environ.get("TAX_MODEL_PATH")
    return Path(configured).expanduser().resolve() if configured else DEFAULT_ARTIFACT


def configured_download_url(metadata_path: Path = DEFAULT_METADATA) -> str | None:
    """Resolve where the canonical artifact is published.

    ``TAX_MODEL_DOWNLOAD_URL`` wins so a deployment can point at a mirror or a
    pre-release build. Otherwise the URL recorded in the committed model
    metadata is used, which lets a host that installs requirements and runs the
    app -- Streamlit Community Cloud, for one -- obtain the artifact with no
    configuration at all.

    Returns ``None`` when neither source names a URL, leaving the caller to
    degrade rather than guess an address.
    """
    configured = os.environ.get("TAX_MODEL_DOWNLOAD_URL")
    if configured:
        return configured
    try:
        metadata = json.loads(metadata_path.read_text())
    except (FileNotFoundError, OSError, json.JSONDecodeError):
        return None
    url = metadata.get("final_model", {}).get("distribution", {}).get("url")
    return url if isinstance(url, str) and url else None


def download_token() -> str | None:
    """Token for a private release; a public release needs none."""
    return os.environ.get("TAX_MODEL_DOWNLOAD_TOKEN") or os.environ.get("GITHUB_TOKEN")


def expected_artifact_sha256(metadata_path: Path) -> str:
    try:
        metadata = json.loads(metadata_path.read_text())
        expected = metadata["final_model"]["artifact_sha256"]
    except (FileNotFoundError, OSError, json.JSONDecodeError, KeyError, TypeError) as error:
        raise ArtifactBootstrapError(
            "Model metadata is unavailable or does not contain an artifact checksum."
        ) from error
    if not isinstance(expected, str) or len(expected) != 64:
        raise ArtifactBootstrapError("Model metadata contains an invalid artifact checksum.")
    return expected.lower()


def download_artifact(
    *,
    url: str,
    destination: Path,
    metadata_path: Path,
    token: str | None = None,
    opener: Callable[..., DownloadResponse] = urlopen,
) -> None:
    """Stream verified bytes to a sibling temporary file, then promote atomically."""
    expected = expected_artifact_sha256(metadata_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    part = destination.with_name(f"{destination.name}.part")
    headers = {"Accept": "application/octet-stream"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = Request(url, headers=headers)
    digest = hashlib.sha256()

    try:
        with opener(request, timeout=60) as response, part.open("wb") as handle:
            while True:
                chunk = response.read(DOWNLOAD_CHUNK_SIZE)
                if not chunk:
                    break
                digest.update(chunk)
                handle.write(chunk)
            handle.flush()
            os.fsync(handle.fileno())

        actual = digest.hexdigest()
        if actual != expected:
            raise ArtifactBootstrapError(
                "Downloaded model bytes did not match the committed checksum."
            )
        os.replace(part, destination)
    except Exception:
        part.unlink(missing_ok=True)
        raise


def bootstrap_artifact() -> ArtifactSource | None:
    """Use local bytes, optionally download missing bytes, or remain degraded."""
    destination = configured_artifact_path()
    if destination.is_file():
        return "local"

    url = os.environ.get("TAX_MODEL_DOWNLOAD_URL")
    if not url:
        return None
    token = os.environ.get("TAX_MODEL_DOWNLOAD_TOKEN") or os.environ.get("GITHUB_TOKEN")
    download_artifact(
        url=url,
        destination=destination,
        metadata_path=DEFAULT_METADATA,
        token=token,
    )
    return "downloaded"

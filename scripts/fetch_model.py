"""Fetch the one canonical model artifact, verified against committed metadata.

The trained forest is 263 MB and deliberately not committed. Every machine that
rebuilds it locally produces a *behaviourally identical* forest inside a
*differently compressed* file, because joblib output is not byte-reproducible
across machines. That makes the ``artifact_sha256`` in ``models/rf_metrics.json``
meaningless as a shared guarantee unless everyone holds the same bytes.

So one build is canonical and published as a GitHub Release asset. Fetch it with
this script instead of retraining, and the checksum becomes a real guarantee
again: identical bytes everywhere, identical predictions, identical SHAP values.

The download itself is not reimplemented here. ``backend.artifacts`` already
streams to a sibling ``.part`` file, verifies the SHA-256 against the committed
metadata, and promotes atomically only after verification, so a corrupted or
truncated transfer can never land at the destination path. This is a CLI over
that, for people and CI rather than for the API's startup hook.

Usage
-----
    python3 scripts/fetch_model.py              # fetch if missing
    python3 scripts/fetch_model.py --force      # re-fetch even if present
    python3 scripts/fetch_model.py --check      # verify what is on disk, no network

A private release needs a token in ``TAX_MODEL_DOWNLOAD_TOKEN`` or
``GITHUB_TOKEN``; a public release needs none. ``TAX_MODEL_DOWNLOAD_URL``
overrides the URL recorded in the metadata.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from backend.artifacts import (  # noqa: E402
    ArtifactBootstrapError,
    DEFAULT_ARTIFACT,
    DEFAULT_METADATA,
    download_artifact,
    expected_artifact_sha256,
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def resolve_url() -> str:
    configured = os.environ.get("TAX_MODEL_DOWNLOAD_URL")
    if configured:
        return configured
    metadata = json.loads(DEFAULT_METADATA.read_text())
    url = metadata.get("final_model", {}).get("distribution", {}).get("url")
    if not url:
        raise SystemExit(
            "No download URL. Set TAX_MODEL_DOWNLOAD_URL, or record one under "
            "final_model.distribution.url in models/rf_metrics.json."
        )
    return url


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--force", action="store_true", help="re-fetch even if present")
    parser.add_argument("--check", action="store_true", help="verify local bytes only")
    args = parser.parse_args()

    destination = Path(os.environ.get("TAX_MODEL_PATH") or DEFAULT_ARTIFACT)
    expected = expected_artifact_sha256(DEFAULT_METADATA)

    if destination.is_file():
        actual = sha256(destination)
        size_mb = destination.stat().st_size / 1e6
        if actual == expected:
            print(f"Canonical artifact present and verified ({size_mb:.0f} MB)\n  {destination}")
            if not args.force:
                return 0
            print("--force given; re-fetching.")
        else:
            print(
                f"Artifact at {destination} is NOT the canonical build.\n"
                f"  expected {expected}\n  actual   {actual}\n"
                "This is what a local rebuild looks like: same model, different bytes."
            )
            if args.check:
                return 1
            if not args.force:
                print("Re-run with --force to replace it with the canonical bytes.")
                return 1
    elif args.check:
        print(f"No artifact at {destination}.")
        return 1

    url = resolve_url()
    token = os.environ.get("TAX_MODEL_DOWNLOAD_TOKEN") or os.environ.get("GITHUB_TOKEN")
    print(f"Fetching canonical artifact\n  from {url}\n  to   {destination}")
    try:
        download_artifact(
            url=url, destination=destination,
            metadata_path=DEFAULT_METADATA, token=token,
        )
    except ArtifactBootstrapError as error:
        # Raised on a checksum mismatch as well as transport failure; the partial
        # file is already cleaned up, so the destination is never left corrupt.
        print(f"\nDownload failed: {error}", file=sys.stderr)
        if not token:
            print("If the release is private, set GITHUB_TOKEN and retry.", file=sys.stderr)
        return 1
    print(f"Verified and installed ({destination.stat().st_size / 1e6:.0f} MB).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

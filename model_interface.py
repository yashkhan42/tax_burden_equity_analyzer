"""The sole boundary between the page and the trained tax-rate model.

The page supplies reader-answerable profile values. This module alone turns
them into the frozen 16-column tax-unit schema, loads and validates the saved
scikit-learn pipeline, computes predictions and empirical reference values,
and translates encoded Tree SHAP values back to the 16 source features.

The model artifact is intentionally not committed. Importing this module is
therefore always safe; a model-dependent call raises
``ModelArtifactUnavailable`` with an actionable internal message when the
artifact is absent. The page can catch that domain exception and present
reader-facing copy without leaking a path or implementation detail.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import warnings
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import TYPE_CHECKING, Any

import numpy as np
import pandas as pd

from codebook import FILESTAT_LABELS, INCOME_SOURCE_PHRASES, MARST_LABELS


# ===========================================================================
# Frozen tax-unit contract
# ===========================================================================

ROOT = Path(__file__).resolve().parent
PROCESSED_DIR = ROOT / "data" / "processed"
MANIFEST_PATH = PROCESSED_DIR / "freeze_manifest.json"
TRAIN_PATH = PROCESSED_DIR / "train.csv"
TEST_PATH = PROCESSED_DIR / "test.csv"
DEFAULT_MODEL_PATH = ROOT / "models" / "rf_eff_rate.joblib"
DEFAULT_METRICS_PATH = ROOT / "models" / "rf_metrics.json"

MODEL_PATH_ENV = "TAX_MODEL_PATH"
MODEL_METRICS_PATH_ENV = "TAX_MODEL_METRICS_PATH"

# This literal is an independent lock. Loading the list only from the manifest
# would let a changed manifest and a changed CSV silently redefine the app.
FEATURE_COLS: tuple[str, ...] = (
    "unit_inctot",
    "wage_share",
    "business_share",
    "interest_share",
    "dividend_share",
    "retirement_share",
    "socsec_share",
    "rent_share",
    "spouse_income_share",
    "age",
    "nchild",
    "nchlt5",
    "famsize",
    "filing_status",
    "marst",
    "statefip",
)

CATEGORICAL_COLS: tuple[str, ...] = ("filing_status", "marst", "statefip")
NUMERIC_COLS: tuple[str, ...] = tuple(
    col for col in FEATURE_COLS if col not in CATEGORICAL_COLS
)
INT_COLS: frozenset[str] = frozenset(
    {"age", "nchild", "nchlt5", "famsize", *CATEGORICAL_COLS}
)
FLOAT_COLS: frozenset[str] = frozenset(FEATURE_COLS) - INT_COLS

# share column -> profile dollar amount for the primary filer plus dependents
# claimed on this return. Spouse income has no source breakdown in the frozen
# build and is deliberately represented by its own profile key and share.
SHARE_SOURCE: dict[str, str] = {
    "wage_share": "incwage",
    "business_share": "incbus",
    "interest_share": "incint",
    "dividend_share": "incdivid",
    "retirement_share": "incretir",
    "socsec_share": "incss",
    "rent_share": "incrent",
}
SPOUSE_INCOME_KEY = "spouse_income"

FILING_STATUS_LEVELS: tuple[int, ...] = (1, 4, 5)
MARST_LEVELS: tuple[int, ...] = (1, 2, 3, 4, 5, 6)
MARRIED_SPOUSE_PRESENT = 1
STATEFIP_LEVELS: tuple[int, ...] = (
    1, 2, 4, 5, 6, 8, 9, 10, 11, 12, 13, 15, 16, 17, 18, 19, 20, 21, 22, 23,
    24, 25, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35, 36, 37, 38, 39, 40, 41,
    42, 44, 45, 46, 47, 48, 49, 50, 51, 53, 54, 55, 56,
)

AGE_RANGE = (15, 85)
UNIT_INCTOT_RANGE = (0.0, 2_295_804.0)
# Temporary compatibility name for presentation code while its field copy is
# changed from person income to whole-return income.
INCTOT_RANGE = UNIT_INCTOT_RANGE
NCHILD_MAX = 9
NCHLT5_MAX = 5
FAMSIZE_RANGE = (1, 16)
EFF_RATE_RANGE = (-49.99, 33.37)
DISTRIBUTION_BIN_WIDTH = 2.5

QUARANTINE_COLS: frozenset[str] = frozenset(
    {
        "eff_rate", "fedtaxac", "adjginc", "spmfedtaxac", "eitcred",
        "ctccrd", "actccrd", "margtax", "taxinc", "fica",
    }
)
PROFILE_KEYS: frozenset[str] = frozenset(
    {
        "unit_inctot", SPOUSE_INCOME_KEY, "age", "nchild", "nchlt5",
        "famsize", "filing_status", "marst", "statefip",
        *SHARE_SOURCE.values(),
    }
)

# The calls below are live-model calls, never deterministic demo values.
MODEL_IS_STUB = False


class ModelInterfaceError(RuntimeError):
    """Base class for errors at the UI/model boundary."""


class ModelArtifactUnavailable(ModelInterfaceError):
    """The trained artifact or a required runtime dependency is unavailable."""


class ModelContractError(ModelInterfaceError):
    """The artifact, metadata, freeze, or profile violates the locked schema."""


class TwinNotAvailable(ModelInterfaceError):
    """This filer has nothing to flip for the requested comparison.

    Distinct from a failure: the profile is valid and the model is fine, there
    is simply no counterfactual to draw. A filer whose entire income is their
    spouse's has no own income source to move, so a "different dominant source"
    twin would be the same filer relabelled. Returning a zero gap under a
    changed label would state a comparison that was never made, so the caller
    is told instead and can leave that comparison out.
    """


def _read_json(path: Path, description: str) -> dict[str, Any]:
    try:
        return json.loads(path.read_text())
    except FileNotFoundError as error:
        raise ModelArtifactUnavailable(
            f"{description} is missing at {path}. Regenerate the Phase 3 outputs "
            "or point the app at matching files."
        ) from error
    except (OSError, json.JSONDecodeError) as error:
        raise ModelContractError(f"{description} at {path} cannot be read: {error}") from error


@lru_cache(maxsize=1)
def _manifest() -> dict[str, Any]:
    manifest = _read_json(MANIFEST_PATH, "The frozen-data manifest")
    if tuple(manifest.get("feature_cols", ())) != FEATURE_COLS:
        raise ModelContractError(
            "The frozen manifest's feature order no longer matches the locked "
            f"16-feature application contract: {manifest.get('feature_cols')!r}"
        )
    if manifest.get("n_features") != len(FEATURE_COLS):
        raise ModelContractError("The frozen manifest's feature count is inconsistent.")
    return manifest


# The floor is authoritative from the freeze. Evaluate it at import because it
# is also a presentation rule and does not depend on the absent model.
_FROZEN_MANIFEST = _manifest()
INCTOT_SHARE_FLOOR = int(_FROZEN_MANIFEST["share_floor"])


def derive_filing_status(marst: int, head_of_household: bool = False) -> int:
    """Collapse a reader's filing choice to the model's 1/4/5 status levels."""
    if int(marst) == MARRIED_SPOUSE_PRESENT:
        return 1
    return 4 if head_of_household else 5


def derive_filestat(
    marst: int,
    age: int | None = None,
    spouse_65_plus: bool = False,
    head_of_household: bool = False,
) -> int:
    """Compatibility wrapper returning the collapsed filing-status code.

    The 16-feature model no longer contains the old 1/2/3 age split. ``age``
    and ``spouse_65_plus`` are accepted only so the page can migrate its form
    without an import-time break; neither changes the returned 1/4/5 status.
    """
    del age, spouse_65_plus
    return derive_filing_status(marst, head_of_household=head_of_household)


def _build_feature_row(
    profile: dict[str, Any], *, allow_counterfactual: bool
) -> pd.DataFrame:
    """Translate one tax-unit profile to the exact frozen model row.

    ``unit_inctot`` is total pre-tax income for everyone on the return.
    The seven raw source amounts cover the primary filer plus dependents and
    deliberately exclude the spouse. ``spouse_income`` is the spouse's
    non-negative total with no source breakdown, matching the family-residual
    reconstruction used to freeze the training table.
    """
    leaked = QUARANTINE_COLS & set(profile)
    if leaked:
        raise ValueError(
            f"quarantined field(s) {sorted(leaked)} cannot enter a model profile"
        )

    missing = PROFILE_KEYS - set(profile)
    if missing:
        raise ValueError(f"profile is missing required key(s): {sorted(missing)}")

    unit_income = float(profile["unit_inctot"])
    if not math.isfinite(unit_income):
        raise ValueError("unit_inctot must be finite")
    if not UNIT_INCTOT_RANGE[0] <= unit_income <= UNIT_INCTOT_RANGE[1]:
        raise ValueError(
            f"unit_inctot={unit_income} is outside the frozen training range "
            f"{UNIT_INCTOT_RANGE}"
        )

    spouse_income = float(profile[SPOUSE_INCOME_KEY])
    if not math.isfinite(spouse_income) or spouse_income < 0:
        raise ValueError("spouse_income must be a finite, non-negative amount")

    row: dict[str, float | int] = {"unit_inctot": unit_income}
    above_floor = unit_income >= INCTOT_SHARE_FLOOR
    for share, source in SHARE_SOURCE.items():
        amount = float(profile[source])
        if not math.isfinite(amount):
            raise ValueError(f"{source} must be finite")
        row[share] = amount / unit_income if above_floor else 0.0
    row["spouse_income_share"] = spouse_income / unit_income if above_floor else 0.0

    for col in ("age", "nchild", "nchlt5", "famsize", *CATEGORICAL_COLS):
        row[col] = int(profile[col])

    for col, levels in (
        ("filing_status", FILING_STATUS_LEVELS),
        ("marst", MARST_LEVELS),
        ("statefip", STATEFIP_LEVELS),
    ):
        if row[col] not in levels:
            raise ValueError(
                f"{col}={row[col]} is not a level present in the frozen table "
                f"{list(levels)}"
            )

    # These relationships are exact across the frozen table. The twin engine
    # can deliberately relax them to isolate a categorical effect; ordinary
    # predictions cannot accidentally submit an incoherent tax unit.
    if not allow_counterfactual:
        joint_status = int(row["filing_status"]) == 1
        spouse_present = int(row["marst"]) == MARRIED_SPOUSE_PRESENT
        if joint_status != spouse_present:
            raise ValueError(
                "filing_status and marst do not form a combination present in "
                "the frozen table"
            )
        if not joint_status and spouse_income != 0:
            raise ValueError("spouse_income must be 0 for a non-joint return")

    if not AGE_RANGE[0] <= int(row["age"]) <= AGE_RANGE[1]:
        raise ValueError(f"age must be within the frozen range {AGE_RANGE}")
    if not 0 <= int(row["nchild"]) <= NCHILD_MAX:
        raise ValueError(f"nchild must be between 0 and {NCHILD_MAX}")
    if not 0 <= int(row["nchlt5"]) <= min(NCHLT5_MAX, int(row["nchild"])):
        raise ValueError("nchlt5 must be non-negative and cannot exceed nchild")
    if not FAMSIZE_RANGE[0] <= int(row["famsize"]) <= FAMSIZE_RANGE[1]:
        raise ValueError(f"famsize must be within the frozen range {FAMSIZE_RANGE}")

    frame = pd.DataFrame([row], columns=list(FEATURE_COLS)).astype(
        {col: ("int64" if col in INT_COLS else "float64") for col in FEATURE_COLS}
    )
    if list(frame.columns) != list(FEATURE_COLS):
        raise ModelContractError("The constructed feature order drifted.")
    if set(frame.columns) & QUARANTINE_COLS:
        raise ModelContractError("A quarantined field entered the model row.")
    return frame


def build_feature_row(profile: dict[str, Any]) -> pd.DataFrame:
    """Translate an ordinary in-distribution profile to the frozen model row."""
    return _build_feature_row(profile, allow_counterfactual=False)


# ===========================================================================
# Validated artifact and prediction-reference loaders
# ===========================================================================


def _configured_path(env_name: str, default: Path) -> Path:
    configured = os.environ.get(env_name)
    return Path(configured).expanduser().resolve() if configured else default


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


@lru_cache(maxsize=1)
def _metrics() -> dict[str, Any]:
    path = _configured_path(MODEL_METRICS_PATH_ENV, DEFAULT_METRICS_PATH)
    metrics = _read_json(path, "The model metadata")
    inputs = metrics.get("inputs", {})
    if tuple(inputs.get("feature_cols", ())) != FEATURE_COLS:
        raise ModelContractError(
            "The model metadata was trained with a different feature order."
        )
    manifest = _manifest()
    if inputs.get("train.csv_sha256") != manifest["sha256"]["train.csv"]:
        raise ModelContractError(
            "The model metadata and authoritative training freeze have different hashes."
        )
    if inputs.get("test.csv_sha256") != manifest["sha256"]["test.csv"]:
        raise ModelContractError(
            "The model metadata and authoritative test freeze have different hashes."
        )
    if metrics.get("encoding", {}).get("categorical") != list(CATEGORICAL_COLS):
        raise ModelContractError("The model metadata has a different categorical order.")
    return metrics


def _require_model_dependency() -> tuple[Any, str]:
    try:
        import joblib
        import sklearn
    except ImportError as error:
        raise ModelArtifactUnavailable(
            "The modeling runtime is not installed. Install requirements.txt "
            "before loading the trained artifact."
        ) from error
    return joblib, sklearn.__version__


def _validate_model(model: Any, metrics: dict[str, Any]) -> None:
    if not hasattr(model, "named_steps"):
        raise ModelContractError("The artifact is not the expected fitted pipeline.")
    if not {"encode", "rf"} <= set(model.named_steps):
        raise ModelContractError("The artifact lacks the expected encode/rf pipeline steps.")

    seen = tuple(str(value) for value in getattr(model, "feature_names_in_", ()))
    if seen != FEATURE_COLS:
        raise ModelContractError(
            f"The fitted pipeline expects {seen!r}, not the locked feature order."
        )

    encoder = model.named_steps["encode"]
    transformers = {name: (transformer, tuple(cols)) for name, transformer, cols in encoder.transformers_}
    if "onehot" not in transformers or "passthrough" not in transformers:
        raise ModelContractError("The fitted encoder's transformer layout is unexpected.")
    if transformers["onehot"][1] != CATEGORICAL_COLS:
        raise ModelContractError("The artifact one-hot encodes different columns or order.")
    if transformers["passthrough"][1] != NUMERIC_COLS:
        raise ModelContractError("The artifact passes through different numeric columns or order.")

    onehot = encoder.named_transformers_["onehot"]
    expected_categories = metrics["encoding"]["categories"]
    actual_categories = {
        col: [int(value) for value in categories]
        for col, categories in zip(CATEGORICAL_COLS, onehot.categories_)
    }
    if actual_categories != expected_categories:
        raise ModelContractError("The artifact's one-hot category levels have drifted.")

    output_names = tuple(str(name) for name in encoder.get_feature_names_out())
    if len(output_names) != int(metrics["encoding"]["n_encoded_columns"]):
        raise ModelContractError("The artifact's encoded feature count has drifted.")
    if getattr(model.named_steps["rf"], "n_features_in_", None) != len(output_names):
        raise ModelContractError("The forest and encoder disagree on feature count.")


METRIC_TOLERANCE = 1e-3

# Hosts that install requirements and run the app, with no build step and no
# writable image to bake a 263 MB file into -- Streamlit Community Cloud is the
# one this project deploys to -- have nowhere to put the artifact ahead of time.
# Fetching it on first use is the only way such a host can serve real numbers.
ARTIFACT_FETCH_ENV = "TAX_MODEL_FETCH"


def _artifact_fetch_enabled() -> bool:
    """Fetching is on by default; ``TAX_MODEL_FETCH=0`` turns it off.

    An air-gapped or offline deployment can disable the network entirely and
    still get the honest "no artifact" degraded state rather than a stall.
    """
    return os.environ.get(ARTIFACT_FETCH_ENV, "1").strip().lower() not in {"0", "false", "no"}


# Streamlit serves every browser session from one process, so two readers
# arriving at a cold app would otherwise start two downloads writing the same
# sibling ".part" file and race to promote it. One at a time; whoever loses the
# race finds the file already there and returns.
_FETCH_LOCK = __import__("threading").Lock()


def prepare_artifact() -> bool:
    """Ensure the trained artifact is on disk, fetching it if needed.

    Safe and cheap to call repeatedly, and safe to call from a background
    thread: it performs no rendering and raises nothing. Returns whether an
    artifact is present afterwards, so a caller may warm the file while the
    reader is still filling in the form instead of making them wait after they
    ask a question.
    """
    path = _configured_path(MODEL_PATH_ENV, DEFAULT_MODEL_PATH)
    if path.is_file():
        return True
    _fetch_canonical_artifact(path)
    return path.is_file()


def _fetch_canonical_artifact(destination: Path) -> None:
    """Best-effort download of the canonical artifact when none is on disk.

    Deliberately quiet about failure: the caller raises
    :class:`ModelArtifactUnavailable` when the file is still missing, and the
    page already renders a reader-facing degraded state for exactly that. A
    download problem must not surface as a stack trace on someone's screen.

    ``backend.artifacts`` is imported lazily so that importing this module stays
    free of any dependency on the HTTP layer, and so an import failure here is
    just one more reason the artifact is unavailable.
    """
    if not _artifact_fetch_enabled():
        return
    try:
        from backend.artifacts import (
            configured_download_url,
            download_artifact,
            download_token,
        )

        metadata_path = _configured_path(MODEL_METRICS_PATH_ENV, DEFAULT_METRICS_PATH)
        url = configured_download_url(metadata_path)
        if not url:
            return
        with _FETCH_LOCK:
            if destination.is_file():
                return  # another session won the race and already promoted it
            download_artifact(
                url=url,
                destination=destination,
                metadata_path=metadata_path,
                token=download_token(),
            )
    except Exception as error:  # noqa: BLE001 - degrade, never crash the page
        warnings.warn(
            f"The canonical model artifact could not be fetched: {error}",
            RuntimeWarning,
            stacklevel=2,
        )


def _verify_rebuilt_artifact(model: Any, metrics: dict[str, Any]) -> dict[str, float]:
    """Establish artifact identity by behaviour when its bytes are not a match.

    A joblib file is **not byte-reproducible across machines**. The checksum in
    ``rf_metrics.json`` is written by whichever machine last ran the training
    notebook, so a teammate who rebuilds from the same seed and the same frozen
    data gets an identical forest inside a differently-compressed file. Byte
    equality therefore answers "which machine wrote this?", not "is this the
    documented model?" -- and enforcing it makes every local rebuild fail.

    Reproducing the logged test metrics answers the question that actually
    matters. Combined with ``_validate_model`` (pipeline shape, feature order,
    one-hot levels, encoded width) and the scikit-learn version check, a forest
    that scores the frozen, hash-verified test set to within ``METRIC_TOLERANCE``
    of the logged R^2 and MAE is the documented model.

    Network integrity is unaffected: ``backend.artifacts.download_artifact``
    verifies the checksum while streaming and refuses to promote mismatched
    bytes, so downloaded artifacts are still byte-checked before they are ever
    written to disk. This fallback only admits a locally built file.
    """
    manifest = _manifest()
    _validate_frozen_csv(TEST_PATH, manifest["sha256"]["test.csv"])
    test = pd.read_csv(TEST_PATH)

    predicted = np.asarray(model.predict(test.loc[:, list(FEATURE_COLS)]), dtype=float)
    observed = np.asarray(test[manifest["target"]], dtype=float)
    if not np.isfinite(predicted).all():
        raise ModelContractError("The artifact produced a non-finite test prediction.")

    residual = observed - predicted
    r2 = float(1 - (residual**2).sum() / ((observed - observed.mean()) ** 2).sum())
    mae = float(np.abs(residual).mean())

    logged = metrics.get("metrics", {}).get("test", {})
    for name, got, want in (("R2", r2, logged.get("R2")), ("MAE", mae, logged.get("MAE"))):
        if want is None:
            raise ModelContractError(f"The model metadata has no logged test {name}.")
        if abs(got - float(want)) > METRIC_TOLERANCE:
            raise ModelContractError(
                "The artifact is not the model its metadata describes: it scores "
                f"test {name} {got:.4f}, but the metadata logs {float(want):.4f}."
            )
    return {"R2": r2, "MAE": mae}


@lru_cache(maxsize=1)
def _load_model() -> Any:
    """Load once, refusing mismatched versions, schema, encoding, or behaviour.

    Byte equality with the committed checksum is the fast path. When it fails,
    the artifact is admitted only if it reproduces the logged test metrics --
    see :func:`_verify_rebuilt_artifact` for why bytes alone cannot decide this.
    """
    path = _configured_path(MODEL_PATH_ENV, DEFAULT_MODEL_PATH)
    if not path.is_file():
        _fetch_canonical_artifact(path)
    if not path.is_file():
        raise ModelArtifactUnavailable(
            f"No trained artifact exists at {path} and it could not be fetched. "
            "Run notebooks/train_random_forest.ipynb to produce "
            "models/rf_eff_rate.joblib, run scripts/fetch_model.py to download "
            "the canonical build, or set TAX_MODEL_PATH."
        )

    metrics = _metrics()
    expected_hash = metrics.get("final_model", {}).get("artifact_sha256")
    if not expected_hash:
        raise ModelContractError("The model metadata has no artifact checksum.")
    bytes_match = _sha256(path) == expected_hash

    joblib, sklearn_version = _require_model_dependency()
    trained_version = str(metrics["final_model"]["sklearn_version"])
    if sklearn_version != trained_version:
        raise ModelContractError(
            f"The artifact was trained with scikit-learn {trained_version}, "
            f"but the runtime has {sklearn_version}."
        )

    try:
        model = joblib.load(path)
    except Exception as error:
        raise ModelArtifactUnavailable(f"The trained artifact could not be loaded: {error}") from error
    _validate_model(model, metrics)
    if not bytes_match:
        scored = _verify_rebuilt_artifact(model, metrics)
        warnings.warn(
            "The model artifact does not match the checksum in its metadata, but "
            f"reproduces the logged test metrics (R2 {scored['R2']:.4f}, MAE "
            f"{scored['MAE']:.4f}) and is being used. This is expected for a locally "
            "rebuilt artifact: joblib files are not byte-reproducible across machines.",
            RuntimeWarning,
            stacklevel=2,
        )
    return model


@dataclass(frozen=True)
class PredictionReference:
    sorted_predictions: np.ndarray
    distribution: tuple[tuple[float, float], ...]
    share_exactly_zero: float
    share_negative: float


def _validate_frozen_csv(path: Path, expected_hash: str) -> None:
    if not path.is_file():
        raise ModelArtifactUnavailable(f"The frozen reference table is missing at {path}.")
    actual = _sha256(path)
    if actual != expected_hash:
        raise ModelContractError(
            f"The frozen reference table hash drifted (expected {expected_hash}, got {actual})."
        )


def _histogram(predictions: np.ndarray) -> tuple[tuple[float, float], ...]:
    width = DISTRIBUTION_BIN_WIDTH
    lo = min(0.0, math.floor(float(predictions.min()) / width) * width)
    hi = max(width, math.ceil(float(predictions.max()) / width) * width + width)
    edges = np.arange(lo, hi + width / 2, width, dtype=float)
    counts, _ = np.histogram(predictions, bins=edges)
    shares = counts / len(predictions)
    return tuple((float(start), float(share)) for start, share in zip(edges[:-1], shares))


@lru_cache(maxsize=1)
def _load_prediction_reference() -> PredictionReference:
    """Predict the frozen training population once for percentile/chart use."""
    manifest = _manifest()
    _validate_frozen_csv(TRAIN_PATH, manifest["sha256"]["train.csv"])
    train = pd.read_csv(TRAIN_PATH)
    expected_columns = list(FEATURE_COLS) + [manifest["target"], manifest["weight_retained"]]
    if list(train.columns) != expected_columns:
        raise ModelContractError("The frozen training table's columns or order drifted.")

    predictions = np.asarray(
        _load_model().predict(train.loc[:, list(FEATURE_COLS)]), dtype=float
    )
    if predictions.shape != (manifest["rows"]["train"],):
        raise ModelContractError("The prediction reference has an unexpected row count.")
    if not np.isfinite(predictions).all():
        raise ModelContractError("The model produced a non-finite training prediction.")
    predictions.sort()
    return PredictionReference(
        sorted_predictions=predictions,
        distribution=_histogram(predictions),
        share_exactly_zero=float(np.mean(predictions == 0.0)),
        share_negative=float(np.mean(predictions < 0.0)),
    )


# These three values are public historical APIs used by app.py/charts.py.
# Module-level __getattr__ keeps them lazy: importing the page does not require
# the intentionally absent 275 MB artifact.
if TYPE_CHECKING:
    RATE_DISTRIBUTION: tuple[tuple[float, float], ...]
    SHARE_EXACTLY_ZERO: float
    SHARE_NEGATIVE: float


def __getattr__(name: str) -> Any:
    reference_fields = {
        "RATE_DISTRIBUTION": "distribution",
        "SHARE_EXACTLY_ZERO": "share_exactly_zero",
        "SHARE_NEGATIVE": "share_negative",
    }
    if name in reference_fields:
        return getattr(_load_prediction_reference(), reference_fields[name])
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


# ===========================================================================
# Prediction, percentile, and source-feature SHAP
# ===========================================================================


def predict_rate(profile: dict[str, Any]) -> float:
    """Predict effective federal tax rate in percentage points."""
    prediction = float(_load_model().predict(build_feature_row(profile))[0])
    if not math.isfinite(prediction):
        raise ModelContractError("The model produced a non-finite prediction.")
    return prediction


def get_percentile(rate: float) -> float:
    """Empirical midrank of ``rate`` among frozen-training model predictions."""
    value = float(rate)
    if not math.isfinite(value):
        raise ValueError("rate must be finite")
    predictions = _load_prediction_reference().sorted_predictions
    n = len(predictions)
    if value < predictions[0]:
        return 0.0
    if value > predictions[-1]:
        return 100.0

    left = int(np.searchsorted(predictions, value, side="left"))
    right = int(np.searchsorted(predictions, value, side="right"))
    if right > left:
        rank = (left + right - 1) / 2
        return float(100 * rank / max(n - 1, 1))

    lo, hi = left - 1, left
    fraction = (value - predictions[lo]) / (predictions[hi] - predictions[lo])
    rank = lo + fraction
    return float(100 * rank / max(n - 1, 1))


@dataclass
class Explanation:
    """SHAP contributions collapsed from 73 encoded columns to 16 inputs."""

    base_values: float
    values: list[float]
    data: list[float]
    feature_names: list[str] = field(default_factory=lambda: list(FEATURE_COLS))

    @property
    def predicted(self) -> float:
        return self.base_values + sum(self.values)


@lru_cache(maxsize=1)
def _load_shap_explainer() -> Any:
    try:
        import shap
    except ImportError as error:
        raise ModelArtifactUnavailable(
            "SHAP is not installed. Install requirements.txt before requesting explanations."
        ) from error
    return shap.TreeExplainer(_load_model().named_steps["rf"])


def _one_row_shap_values(encoded: np.ndarray) -> tuple[float, np.ndarray]:
    result = _load_shap_explainer()(encoded, check_additivity=True)
    values = np.asarray(result.values, dtype=float)
    if values.ndim == 3 and values.shape[-1] == 1:
        values = values[..., 0]
    if values.ndim == 2:
        values = values[0]
    if values.ndim != 1:
        raise ModelContractError(f"Unexpected SHAP value shape {values.shape}.")

    base = np.asarray(result.base_values, dtype=float).reshape(-1)
    if base.size != 1:
        raise ModelContractError(f"Unexpected SHAP baseline shape {base.shape}.")
    return float(base[0]), values


def _collapse_encoded_contributions(values: np.ndarray) -> dict[str, float]:
    metrics = _metrics()
    collapsed = {col: 0.0 for col in FEATURE_COLS}
    offset = 0
    for col in CATEGORICAL_COLS:
        width = len(metrics["encoding"]["categories"][col])
        collapsed[col] = float(values[offset : offset + width].sum())
        offset += width
    for col in NUMERIC_COLS:
        collapsed[col] = float(values[offset])
        offset += 1
    if offset != len(values):
        raise ModelContractError(
            f"SHAP returned {len(values)} encoded columns; expected {offset}."
        )
    return collapsed


def get_shap_explanation(profile: dict[str, Any]) -> Explanation:
    """Explain one prediction, returning contributions in raw feature order."""
    frame = build_feature_row(profile)
    model = _load_model()
    encoded = np.asarray(model.named_steps["encode"].transform(frame), dtype=float)
    base, encoded_values = _one_row_shap_values(encoded)
    collapsed = _collapse_encoded_contributions(encoded_values)
    explanation = Explanation(
        base_values=base,
        values=[collapsed[col] for col in FEATURE_COLS],
        data=[float(frame.iloc[0][col]) for col in FEATURE_COLS],
        feature_names=list(FEATURE_COLS),
    )

    predicted = float(model.named_steps["rf"].predict(encoded)[0])
    if not math.isclose(explanation.predicted, predicted, abs_tol=1e-5):
        raise ModelContractError(
            "Collapsed SHAP contributions do not add back to the model prediction."
        )
    return explanation


# ===========================================================================
# Twin counterfactuals
# ===========================================================================

TWIN_FLIP_ATTRIBUTES: tuple[str, ...] = (
    "filing_status",
    "marital_status",
    "dominant_income_source",
    "dependents",
)


def _flip_profile(
    profile: dict[str, Any], flip_attribute: str
) -> tuple[dict[str, Any], str, str]:
    if flip_attribute not in TWIN_FLIP_ATTRIBUTES:
        raise ValueError(
            f"{flip_attribute!r} is not a permitted twin flip; allowed values are "
            f"{list(TWIN_FLIP_ATTRIBUTES)}"
        )
    # Validate the base before changing it. The twin itself may intentionally
    # combine categorical levels not observed together so a single model input
    # can be isolated; the encoder has seen every individual level.
    build_feature_row(profile)
    twin = dict(profile)

    if flip_attribute == "filing_status":
        current = int(profile["filing_status"])
        from_label = FILESTAT_LABELS[current]
        # For a non-joint filer, compare the two coherent non-joint choices.
        # A joint filer moves to filing alone while the remaining economics
        # stay fixed, which is the isolated intervention this twin promises.
        twin["filing_status"] = 5 if current in (1, 4) else 4
        return twin, from_label, FILESTAT_LABELS[int(twin["filing_status"])]

    if flip_attribute == "marital_status":
        current = int(profile["marst"])
        married = current == MARRIED_SPOUSE_PRESENT
        twin["marst"] = 6 if married else MARRIED_SPOUSE_PRESENT
        # The fixed-economics twin uses the ordinary single-filer category
        # when moving away from a joint return.  Inferring head-of-household
        # from child count would add an unasked-for tax-status assumption.
        twin["filing_status"] = derive_filing_status(int(twin["marst"]))
        return twin, MARST_LABELS[current], MARST_LABELS[int(twin["marst"])]

    if flip_attribute == "dominant_income_source":
        amounts = {source: float(profile[source]) for source in SHARE_SOURCE.values()}
        source = max(amounts, key=amounts.get)
        moved = amounts[source]
        # A spouse's income has no source breakdown in the frozen build, so it
        # cannot be recomposed. When it is the largest part of the return, or
        # when there is simply nothing positive to move, no honest twin exists:
        # every own-source amount would stay exactly where it is and the gap
        # would be zero under a label claiming the composition had changed.
        if moved <= 0 or float(profile[SPOUSE_INCOME_KEY]) > moved:
            raise TwinNotAvailable(
                "this filer has no own income source large enough to recompose"
            )
        target = "incdivid" if source == "incwage" else "incwage"
        twin[source] = amounts[source] - moved
        twin[target] = amounts[target] + moved
        return twin, _income_label(source), _income_label(target)

    current_children = int(profile["nchild"])
    if current_children > 0:
        twin["nchild"] = 0
        twin["nchlt5"] = 0
        adult_floor = 1 + (
            1 if int(profile["marst"]) == MARRIED_SPOUSE_PRESENT else 0
        )
        twin["famsize"] = max(adult_floor, int(profile["famsize"]) - current_children)
    else:
        twin["nchild"] = 2
        adult_floor = 1 + (
            1 if int(profile["marst"]) == MARRIED_SPOUSE_PRESENT else 0
        )
        twin["famsize"] = max(int(profile["famsize"]), adult_floor + 2)
    return twin, _children_label(current_children), _children_label(int(twin["nchild"]))


def _income_label(source: str) -> str:
    return f"mostly from {INCOME_SOURCE_PHRASES[source]}"


def _children_label(n: int) -> str:
    return "no children" if n == 0 else f"{n} {'child' if n == 1 else 'children'}"


def available_flips(profile: dict[str, Any]) -> tuple[str, ...]:
    """Which comparisons can actually be drawn for this filer.

    Not every filer has every twin. Offering a comparison that cannot be made
    and reporting the failure afterwards is worse than not offering it, so a
    caller building a menu should build it from this rather than from
    :data:`TWIN_FLIP_ATTRIBUTES`. Requires no model.
    """
    available = []
    for attribute in TWIN_FLIP_ATTRIBUTES:
        try:
            _flip_profile(profile, attribute)
        except TwinNotAvailable:
            continue
        available.append(attribute)
    return tuple(available)


def get_twin(
    profile: dict[str, Any], flip_attribute: str
) -> tuple[float, float, float]:
    """Return base rate, twin rate, and signed twin-minus-base gap."""
    twin_profile, _, _ = _flip_profile(profile, flip_attribute)
    model = _load_model()
    base_rate = float(model.predict(build_feature_row(profile))[0])
    twin_frame = _build_feature_row(twin_profile, allow_counterfactual=True)
    twin_rate = float(model.predict(twin_frame)[0])
    if not math.isfinite(base_rate) or not math.isfinite(twin_rate):
        raise ModelContractError("The model produced a non-finite twin prediction.")
    return base_rate, twin_rate, twin_rate - base_rate


def describe_flip(profile: dict[str, Any], flip_attribute: str) -> tuple[str, str]:
    """Return reader-facing labels for the before and after twin states."""
    _, from_label, to_label = _flip_profile(profile, flip_attribute)
    return from_label, to_label

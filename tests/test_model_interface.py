"""Contract tests for the tax-unit UI/model boundary.

These do not require the 275 MB artifact. Artifact-backed prediction and SHAP
are integration-tested only when the locally generated model is available.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

import model_interface as mi


ROOT = Path(__file__).resolve().parent.parent


def profile(**overrides) -> dict:
    values = {
        "unit_inctot": 100_000,
        "spouse_income": 30_000,
        "incwage": 60_000,
        "incbus": -2_000,
        "incint": 1_000,
        "incdivid": 5_000,
        "incretir": 0,
        "incss": 0,
        "incrent": 1_000,
        "age": 42,
        "nchild": 2,
        "nchlt5": 1,
        "famsize": 4,
        "filing_status": 1,
        "marst": 1,
        "statefip": 36,
    }
    values.update(overrides)
    return values


def test_locked_schema_matches_the_authoritative_manifest() -> None:
    manifest = json.loads((ROOT / "data" / "processed" / "freeze_manifest.json").read_text())
    assert list(mi.FEATURE_COLS) == manifest["feature_cols"]
    assert mi.INCTOT_SHARE_FLOOR == manifest["share_floor"]


def test_feature_row_reconstructs_the_eight_tax_unit_shares() -> None:
    frame = mi.build_feature_row(profile())
    assert list(frame.columns) == list(mi.FEATURE_COLS)
    assert frame["unit_inctot"].dtype == "float64"
    assert all(frame[col].dtype == "float64" for col in mi.FLOAT_COLS)
    assert all(frame[col].dtype == "int64" for col in mi.INT_COLS)

    row = frame.iloc[0]
    assert row["wage_share"] == pytest.approx(0.60)
    assert row["business_share"] == pytest.approx(-0.02)
    assert row["interest_share"] == pytest.approx(0.01)
    assert row["dividend_share"] == pytest.approx(0.05)
    assert row["rent_share"] == pytest.approx(0.01)
    assert row["spouse_income_share"] == pytest.approx(0.30)


def test_all_shares_are_zero_below_the_frozen_floor() -> None:
    frame = mi.build_feature_row(
        profile(unit_inctot=999, spouse_income=5_000, incwage=20_000)
    )
    share_cols = [*mi.SHARE_SOURCE, "spouse_income_share"]
    assert frame.loc[0, share_cols].eq(0.0).all()


def test_spouse_income_may_exceed_unit_income_but_cannot_be_negative() -> None:
    # The freeze contains nine above-floor rows with this relationship because
    # other sources carry offsetting losses; rejecting it would invent a rule.
    row = mi.build_feature_row(profile(unit_inctot=10_000, spouse_income=12_000))
    assert row.loc[0, "spouse_income_share"] == pytest.approx(1.2)
    with pytest.raises(ValueError, match="non-negative"):
        mi.build_feature_row(profile(spouse_income=-1))


def test_collapsed_filing_status_has_only_the_three_frozen_levels() -> None:
    assert mi.derive_filing_status(1) == 1
    assert mi.derive_filing_status(6, head_of_household=True) == 4
    assert mi.derive_filing_status(6, head_of_household=False) == 5


def test_ordinary_profiles_enforce_the_exact_joint_relationship() -> None:
    with pytest.raises(ValueError, match="combination present"):
        mi.build_feature_row(profile(filing_status=5, marst=1, spouse_income=0))
    with pytest.raises(ValueError, match="non-joint"):
        mi.build_feature_row(profile(filing_status=5, marst=6, spouse_income=10))


def test_marital_twin_keeps_return_economics_fixed() -> None:
    base = profile()
    twin, before, after = mi._flip_profile(base, "marital_status")
    assert before != after
    assert twin["marst"] == 6
    assert twin["filing_status"] == 5
    fixed = {
        "unit_inctot",
        "spouse_income",
        *mi.SHARE_SOURCE.values(),
        "age",
        "nchild",
        "nchlt5",
        "famsize",
        "statefip",
    }
    assert all(twin[key] == base[key] for key in fixed)
    # This generated row is deliberately outside the ordinary joint/spouse
    # lock. Only the twin engine may submit it.
    with pytest.raises(ValueError, match="non-joint"):
        mi.build_feature_row(twin)
    counterfactual = mi._build_feature_row(twin, allow_counterfactual=True)
    assert list(counterfactual.columns) == list(mi.FEATURE_COLS)


def test_filing_twin_changes_only_filing_status() -> None:
    base = profile()
    twin, _, _ = mi._flip_profile(base, "filing_status")
    changed = {key for key in base if twin[key] != base[key]}
    assert changed == {"filing_status"}
    assert twin["filing_status"] == 5
    assert twin["spouse_income"] == base["spouse_income"]


def test_nonjoint_filing_twin_stays_within_nonjoint_choices() -> None:
    base = profile(spouse_income=0, filing_status=5, marst=6, famsize=3)
    twin, _, _ = mi._flip_profile(base, "filing_status")
    assert twin["filing_status"] == 4
    assert twin["marst"] == 6


def test_dependents_twin_keeps_household_counts_coherent() -> None:
    married = profile(nchild=0, nchlt5=0, famsize=2)
    with_children, _, _ = mi._flip_profile(married, "dependents")
    assert with_children["nchild"] == 2
    assert with_children["famsize"] == 4

    without_children, _, _ = mi._flip_profile(profile(), "dependents")
    assert without_children["nchild"] == 0
    assert without_children["nchlt5"] == 0
    assert without_children["famsize"] == 2


def test_encoded_shap_values_collapse_to_the_16_source_features() -> None:
    encoded = np.arange(73, dtype=float)
    collapsed = mi._collapse_encoded_contributions(encoded)
    assert list(collapsed) == list(mi.FEATURE_COLS)
    assert collapsed["filing_status"] == pytest.approx(encoded[0:3].sum())
    assert collapsed["marst"] == pytest.approx(encoded[3:9].sum())
    assert collapsed["statefip"] == pytest.approx(encoded[9:60].sum())
    assert collapsed["unit_inctot"] == pytest.approx(encoded[60])
    assert collapsed["famsize"] == pytest.approx(encoded[72])


def test_absent_model_is_a_lazy_domain_error(monkeypatch, tmp_path) -> None:
    missing = tmp_path / "missing.joblib"
    monkeypatch.setenv(mi.MODEL_PATH_ENV, str(missing))
    mi._load_model.cache_clear()
    with pytest.raises(mi.ModelArtifactUnavailable, match="No trained artifact"):
        mi._load_model()
    mi._load_model.cache_clear()


class _StubForest:
    """Stands in for the fitted pipeline so these stay artifact-free."""

    def __init__(self, predictions: np.ndarray) -> None:
        self._predictions = predictions

    def predict(self, frame):  # noqa: ANN001 - mirrors the sklearn signature
        assert list(frame.columns) == list(mi.FEATURE_COLS)
        return self._predictions


def _frozen_test_targets() -> np.ndarray:
    import pandas as pd

    return np.asarray(
        pd.read_csv(mi.TEST_PATH)[mi._manifest()["target"]], dtype=float
    )


def test_rebuilt_artifact_is_admitted_when_it_reproduces_logged_metrics() -> None:
    """A locally rebuilt artifact has different bytes but identical behaviour."""
    observed = _frozen_test_targets()
    scored = mi._verify_rebuilt_artifact(
        _StubForest(observed), {"metrics": {"test": {"R2": 1.0, "MAE": 0.0}}}
    )
    assert scored["R2"] == pytest.approx(1.0)
    assert scored["MAE"] == pytest.approx(0.0, abs=1e-12)


def test_artifact_that_misses_the_logged_metrics_is_rejected() -> None:
    """Different bytes are tolerated; a different *model* is not."""
    observed = _frozen_test_targets()
    with pytest.raises(mi.ModelContractError, match="not the model its metadata describes"):
        mi._verify_rebuilt_artifact(
            _StubForest(observed), {"metrics": {"test": {"R2": 0.9005, "MAE": 1.277}}}
        )


def test_rebuilt_artifact_check_requires_logged_metrics() -> None:
    observed = _frozen_test_targets()
    with pytest.raises(mi.ModelContractError, match="no logged test"):
        mi._verify_rebuilt_artifact(_StubForest(observed), {"metrics": {"test": {}}})


def test_non_finite_predictions_are_rejected() -> None:
    observed = _frozen_test_targets()
    broken = observed.copy()
    broken[0] = np.nan
    with pytest.raises(mi.ModelContractError, match="non-finite"):
        mi._verify_rebuilt_artifact(
            _StubForest(broken), {"metrics": {"test": {"R2": 1.0, "MAE": 0.0}}}
        )


# ---------------------------------------------------------------------------
# Canonical-artifact fetch (what makes a fresh cloud deploy work)
# ---------------------------------------------------------------------------


def test_fetch_is_skipped_when_disabled(monkeypatch, tmp_path) -> None:
    """conftest disables fetching, so a missing artifact must not hit the network."""
    import backend.artifacts as artifacts

    def _explode(**_kwargs):
        raise AssertionError("download must not be attempted when fetching is disabled")

    monkeypatch.setattr(artifacts, "download_artifact", _explode)
    monkeypatch.setenv(mi.MODEL_PATH_ENV, str(tmp_path / "absent.joblib"))
    mi._load_model.cache_clear()
    with pytest.raises(mi.ModelArtifactUnavailable, match="No trained artifact"):
        mi._load_model()
    mi._load_model.cache_clear()


def test_missing_artifact_is_fetched_from_the_recorded_url(monkeypatch, tmp_path) -> None:
    import backend.artifacts as artifacts

    destination = tmp_path / "fetched.joblib"
    calls: dict[str, object] = {}

    def _record(*, url, destination, metadata_path, token=None):  # noqa: ANN001
        calls.update(url=url, destination=destination, token=token)
        destination.write_bytes(b"not a real forest")

    monkeypatch.setattr(artifacts, "download_artifact", _record)
    monkeypatch.setenv(mi.ARTIFACT_FETCH_ENV, "1")
    monkeypatch.delenv("TAX_MODEL_DOWNLOAD_URL", raising=False)
    monkeypatch.setenv(mi.MODEL_PATH_ENV, str(destination))
    mi._load_model.cache_clear()

    # The stub writes bytes that are not a pipeline, so loading still fails --
    # what matters is that the fetch was attempted against the recorded release.
    with pytest.raises(mi.ModelInterfaceError):
        mi._load_model()
    mi._load_model.cache_clear()

    assert "releases/download" in str(calls["url"])
    assert calls["destination"] == destination


def test_a_failed_fetch_degrades_instead_of_crashing(monkeypatch, tmp_path) -> None:
    """A download problem must reach the reader as the normal unavailable state."""
    import backend.artifacts as artifacts

    def _fail(**_kwargs):
        raise artifacts.ArtifactBootstrapError("release is unreachable")

    monkeypatch.setattr(artifacts, "download_artifact", _fail)
    monkeypatch.setenv(mi.ARTIFACT_FETCH_ENV, "1")
    monkeypatch.setenv(mi.MODEL_PATH_ENV, str(tmp_path / "absent.joblib"))
    mi._load_model.cache_clear()

    with pytest.warns(RuntimeWarning, match="could not be fetched"):
        with pytest.raises(mi.ModelArtifactUnavailable, match="could not be fetched"):
            mi._load_model()
    mi._load_model.cache_clear()


def test_download_url_falls_back_to_committed_metadata(monkeypatch) -> None:
    """A host with no configuration still finds the canonical release."""
    from backend.artifacts import configured_download_url

    monkeypatch.setenv("TAX_MODEL_DOWNLOAD_URL", "https://example.test/override.joblib")
    assert configured_download_url() == "https://example.test/override.joblib"

    monkeypatch.delenv("TAX_MODEL_DOWNLOAD_URL", raising=False)
    url = configured_download_url()
    assert url is not None and "releases/download" in url


# ---------------------------------------------------------------------------
# Twin availability (a comparison that cannot be drawn must not be invented)
# ---------------------------------------------------------------------------


def test_income_source_twin_refuses_when_the_spouse_dominates() -> None:
    """The spouse's income has no source breakdown, so it cannot be recomposed.

    Previously this returned the filer unchanged while labelling the comparison
    as paycheck-to-investments, reporting a zero gap for a flip that never
    happened.
    """
    all_spouse = profile(
        spouse_income=100_000, incwage=0, incbus=0, incint=0,
        incdivid=0, incretir=0, incss=0, incrent=0,
    )
    with pytest.raises(mi.TwinNotAvailable):
        mi._flip_profile(all_spouse, "dominant_income_source")
    assert "dominant_income_source" not in mi.available_flips(all_spouse)


def test_income_source_twin_refuses_when_nothing_is_positive() -> None:
    nothing_to_move = profile(
        spouse_income=0, incwage=0, incbus=0, incint=0,
        incdivid=0, incretir=0, incss=0, incrent=0,
    )
    with pytest.raises(mi.TwinNotAvailable):
        mi._flip_profile(nothing_to_move, "dominant_income_source")


def test_an_ordinary_filer_keeps_every_comparison() -> None:
    wage_heavy = profile(spouse_income=0, filing_status=5, marst=6, incwage=90_000)
    assert mi.available_flips(wage_heavy) == mi.TWIN_FLIP_ATTRIBUTES
    twin, before, after = mi._flip_profile(wage_heavy, "dominant_income_source")
    assert twin["incwage"] == 0
    assert twin["incdivid"] == pytest.approx(90_000 + wage_heavy["incdivid"])
    assert before != after


def test_a_twin_changes_only_the_intended_fields() -> None:
    """§5.2's requirement: hold every feature constant, flip exactly one."""
    base = profile(spouse_income=0, filing_status=5, marst=6)
    expected = {
        "filing_status": {"filing_status"},
        "marital_status": {"marst", "filing_status"},
        "dominant_income_source": {"incwage", "incdivid"},
        "dependents": {"nchild", "nchlt5", "famsize"},
    }
    for attribute, allowed in expected.items():
        twin, _, _ = mi._flip_profile(base, attribute)
        changed = {k for k in base if base[k] != twin[k]}
        assert changed <= allowed, f"{attribute} also changed {changed - allowed}"
        assert changed, f"{attribute} changed nothing"

"""HTTP contract tests with every model call mocked at the public boundary."""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

import model_interface as mi
import backend.main as backend_main
from backend.main import create_app


def profile() -> dict:
    return {
        "totalIncome": 64_000,
        "spouseIncome": 0,
        "income": {
            "wages": 58_000,
            "business": 0,
            "interest": 1_000,
            "dividends": 5_000,
            "retirement": 0,
            "socialSecurity": 0,
            "rent": 0,
        },
        "age": 42,
        "childrenAtHome": 0,
        "childrenUnderFive": 0,
        "householdSize": 1,
        "maritalStatus": "never_married",
        "filingChoice": "single",
        "state": "New York",
    }


@pytest.fixture
def app():
    application = create_app(warm_on_startup=False)
    application.state.readiness.set(True, "local")
    return application


@pytest.fixture
def client(app):
    with TestClient(app) as test_client:
        yield test_client


def test_health_reports_ready_and_degraded_without_paths() -> None:
    application = create_app(warm_on_startup=False)
    with TestClient(application) as test_client:
        response = test_client.get("/healthz")
        assert response.status_code == 503
        assert response.json() == {
            "status": "degraded",
            "modelReady": False,
            "artifactSource": None,
        }

        application.state.readiness.set(True, "downloaded")
        response = test_client.get("/healthz")
        assert response.status_code == 200
        assert response.json() == {
            "status": "ready",
            "modelReady": True,
            "artifactSource": "downloaded",
        }


def test_only_the_locked_http_routes_are_declared() -> None:
    application = create_app(warm_on_startup=False)
    assert {route.path for route in application.routes} == {
        "/healthz",
        "/api/v1/predict",
        "/api/v1/percentile",
        "/api/v1/contribution",
        "/api/v1/twin",
    }


def test_successful_startup_warm_marks_downloaded_artifact_ready(monkeypatch) -> None:
    monkeypatch.setattr(backend_main, "bootstrap_artifact", lambda: "downloaded")
    monkeypatch.setattr(backend_main, "warm_model", lambda: None)
    application = create_app()
    with TestClient(application) as test_client:
        response = test_client.get("/healthz")
    assert response.status_code == 200
    assert response.json()["artifactSource"] == "downloaded"


def test_degraded_model_request_is_safe_and_path_free() -> None:
    application = create_app(warm_on_startup=False)
    with TestClient(application) as test_client:
        response = test_client.post("/api/v1/predict", json={"profile": profile()})
    assert response.status_code == 503
    assert response.json() == {
        "detail": {
            "code": "model_unavailable",
            "message": "The analysis service is not ready yet.",
        }
    }


def test_invalid_profile_returns_safe_422(client: TestClient) -> None:
    invalid = profile()
    invalid["childrenUnderFive"] = 2
    response = client.post("/api/v1/predict", json={"profile": invalid})
    assert response.status_code == 422
    assert response.json() == {
        "detail": {
            "code": "invalid_profile",
            "message": "Some profile details are invalid.",
        }
    }


def test_predict_maps_semantic_profile_and_preserves_negative(
    client: TestClient, monkeypatch
) -> None:
    seen = {}

    def fake_predict(raw):
        seen.update(raw)
        return -7.14

    monkeypatch.setattr(mi, "predict_rate", fake_predict)
    response = client.post("/api/v1/predict", json={"profile": profile()})
    assert response.status_code == 200
    assert response.json() == {
        "rate": -7.1,
        "display": "−7.1%",
        "isNegative": True,
        "framing": (
            "This is a predicted average for filers with these characteristics — "
            "not a calculation of anyone's own tax bill."
        ),
    }
    assert seen["unit_inctot"] == 64_000
    assert seen["spouse_income"] == 0
    assert seen["filing_status"] == 5
    assert seen["marst"] == 6
    assert seen["statefip"] == 36
    assert "wage_share" not in seen


def test_percentile_returns_unweighted_prediction_reference(
    client: TestClient, monkeypatch
) -> None:
    monkeypatch.setattr(mi, "predict_rate", lambda raw: 8.64)
    monkeypatch.setattr(mi, "get_percentile", lambda rate: 63.6)
    monkeypatch.setitem(mi.__dict__, "RATE_DISTRIBUTION", ((-2.5, 0.1), (0.0, 0.9)))
    monkeypatch.setitem(mi.__dict__, "SHARE_EXACTLY_ZERO", 0.02)
    monkeypatch.setitem(mi.__dict__, "SHARE_NEGATIVE", 0.1)

    response = client.post("/api/v1/percentile", json={"profile": profile()})
    assert response.status_code == 200
    payload = response.json()
    assert payload["markerRate"] == 8.64
    assert payload["displayRate"] == "8.6%"
    assert payload["percentile"] == 63.6
    assert payload["belowCount"] == 64
    assert payload["bins"] == [
        {"start": -2.5, "share": 0.1},
        {"start": 0.0, "share": 0.9},
    ]
    assert "survey examples used for comparison" in payload["summary"]
    assert "whole country" not in payload["summary"]


def test_contribution_shapes_plain_english_and_fixes_false_calm_state(
    client: TestClient, monkeypatch
) -> None:
    explanation = SimpleNamespace(
        base_values=5.0,
        predicted=5.2,
        feature_names=["statefip"],
        values=[0.2],
        data=[36.0],
    )
    monkeypatch.setattr(mi, "get_shap_explanation", lambda raw: explanation)
    response = client.post("/api/v1/contribution", json={"profile": profile()})
    assert response.status_code == 200
    assert response.json() == {
        "baseline": 5.0,
        "predicted": 5.2,
        "reasons": [],
        "remainder": 0.2,
        "nothingStandsOut": False,
        "summary": (
            "No single named reason stands out, but the smaller effects together "
            "move the predicted rate."
        ),
    }


def test_twin_gap_matches_the_two_printed_rates(client: TestClient, monkeypatch) -> None:
    monkeypatch.setattr(mi, "get_twin", lambda raw, change: (8.64, 7.05, -1.59))
    monkeypatch.setattr(
        mi,
        "describe_flip",
        lambda raw, change: (
            "filing as a single filer",
            "married, filing together",
        ),
    )
    response = client.post(
        "/api/v1/twin",
        json={"profile": profile(), "comparison": "filing"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["changed"] == "how they file"
    assert payload["changedLabel"] == "How they file"
    assert payload["a"] == {
        "label": "filing as a single filer",
        "rate": 8.6,
        "display": "8.6%",
    }
    assert payload["b"] == {
        "label": "married, filing together",
        "rate": 7.0,
        "display": "7.0%",
    }
    assert payload["gapPoints"] == -1.6
    assert payload["gapMoney"] == "About $1,000 a year at this income."
    assert "one generated comparison" in payload["comparisonNote"]


def test_model_contract_error_is_mapped_to_same_safe_503(
    client: TestClient, monkeypatch
) -> None:
    def fail(raw):
        raise mi.ModelContractError("/private/path and internal_feature")

    monkeypatch.setattr(mi, "predict_rate", fail)
    response = client.post("/api/v1/predict", json={"profile": profile()})
    assert response.status_code == 503
    body = response.json()
    assert body["detail"]["code"] == "model_unavailable"
    assert "/private" not in str(body)
    assert "internal_feature" not in str(body)

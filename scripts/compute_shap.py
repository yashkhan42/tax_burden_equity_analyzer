"""Phase 4 batch: exact Tree SHAP over a sample of the frozen test set.

README §5.1 requires a *global* SHAP output (feature-importance summary +
dependence plots) alongside the per-filer waterfall. Global output needs SHAP
values for many filers, and exact TreeSHAP on this forest costs ~1.7 s/filer
(500 trees, 5.87M leaves, mean depth 42; cost scales with depth^2 per tree).

That makes the batch a long-running, one-time, offline job, so it lives here
rather than inside a notebook cell:

  * **Checkpointed** — each chunk is written to disk as it completes, so an
    interrupted run resumes instead of restarting.
  * **Resumable** — re-running skips chunks already on disk.
  * **Deterministic** — the row sample is drawn with a fixed seed and recorded,
    so the notebook explains exactly the filers this script scored.

Parallelism is deliberately not used. Measured on this machine: process-based
workers each need ~2.1 GB resident (8 GB total, so ~2 fit) and must re-pickle a
275 MB model, making 6 workers *slower* than serial; threads give no speedup
because SHAP's C++ core holds the GIL.

Usage
-----
    python3 scripts/compute_shap.py --rows 4000
    python3 scripts/compute_shap.py --rows 4000 --resume   # after interruption
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.metrics import mean_absolute_error, r2_score

ROOT = Path(__file__).resolve().parent.parent
PROCESSED = ROOT / "data" / "processed"
MODELS = ROOT / "models"
OUT = ROOT / "reports" / "shap"
CHUNKS = OUT / "chunks"

RANDOM_STATE = 42
CHUNK_SIZE = 100  # ~3 min per checkpoint at ~1.7 s/row


def verify_inputs() -> tuple[dict, dict]:
    """Gate the run on data integrity and *functional* model identity.

    The frozen CSVs are byte-verified against the freeze manifest (§3.5).

    The model artifact is verified by behaviour, not by checksum. A joblib file
    is not byte-reproducible across machines -- the committed rf_metrics.json
    records a checksum written on a teammate's machine (fit_seconds 8.2) while a
    locally rebuilt artifact differs (fit_seconds 26.4) even though both are the
    same forest from the same seed and the same frozen data. Comparing
    hyperparameters and reproducing the logged test metrics establishes that
    this artifact *is* the documented model; comparing bytes would only
    establish which machine wrote it.
    """
    manifest = json.loads((PROCESSED / "freeze_manifest.json").read_text())
    metrics = json.loads((MODELS / "rf_metrics.json").read_text())

    import hashlib

    for name in ("train.csv", "test.csv"):
        digest = hashlib.sha256((PROCESSED / name).read_bytes()).hexdigest()
        if digest != manifest["sha256"][name]:
            raise SystemExit(f"{name} does not match freeze_manifest.json; refusing to run.")

    model = joblib.load(MODELS / "rf_eff_rate.joblib")
    rf = model.named_steps["rf"]
    logged = metrics["final_model"]["hyperparameters"]
    for key in ("n_estimators", "max_depth", "min_samples_leaf", "max_features", "random_state"):
        if str(logged.get(key)) != str(rf.get_params().get(key)):
            raise SystemExit(
                f"hyperparameter {key} differs from rf_metrics.json "
                f"({logged.get(key)!r} logged, {rf.get_params().get(key)!r} loaded)."
            )

    test = pd.read_csv(PROCESSED / "test.csv")
    pred = model.predict(test[manifest["feature_cols"]])
    got = {"R2": round(r2_score(test.eff_rate, pred), 4),
           "MAE": round(mean_absolute_error(test.eff_rate, pred), 4)}
    want = metrics["metrics"]["test"]
    if abs(got["R2"] - want["R2"]) > 1e-4 or abs(got["MAE"] - want["MAE"]) > 1e-4:
        raise SystemExit(f"model does not reproduce logged test metrics: {got} vs {want}")

    print(f"Inputs verified. Model reproduces logged test metrics {got}.")
    return manifest, metrics


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--rows", type=int, default=4000)
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()

    import shap

    manifest, _ = verify_inputs()
    CHUNKS.mkdir(parents=True, exist_ok=True)

    model = joblib.load(MODELS / "rf_eff_rate.joblib")
    rf, encoder = model.named_steps["rf"], model.named_steps["encode"]

    test = pd.read_csv(PROCESSED / "test.csv")
    feature_cols = manifest["feature_cols"]

    # Fixed-seed sample. test.csv deciles are equal-sized by construction, so a
    # simple random draw already yields ~rows/10 filers per income decile --
    # representative for global rankings without stratification distorting the
    # population mean|SHAP|.
    rng = np.random.default_rng(RANDOM_STATE)
    sample_idx = np.sort(rng.choice(len(test), size=args.rows, replace=False))

    # Chunks on disk are only reusable if they describe the same sample. Without
    # this guard, `--resume` after a run with a different --rows would silently
    # stitch together chunks explaining different filers.
    run_config = {"rows": int(args.rows), "random_state": RANDOM_STATE,
                  "chunk_size": CHUNK_SIZE, "source": "data/processed/test.csv"}
    config_path = OUT / "run_config.json"
    if config_path.exists():
        previous = json.loads(config_path.read_text())
        if previous != run_config:
            if args.resume:
                raise SystemExit(
                    f"cannot resume: existing chunks were computed for {previous}, "
                    f"but this run requests {run_config}. Delete "
                    f"{CHUNKS.relative_to(ROOT)} to start fresh."
                )
            for stale in CHUNKS.glob("shap_*.npy"):
                stale.unlink()
            print(f"Config changed {previous} -> {run_config}; cleared stale chunks.")
    config_path.write_text(json.dumps(run_config, indent=2) + "\n")
    np.save(OUT / "sample_index.npy", sample_idx)

    X_raw = test.iloc[sample_idx][feature_cols]
    X_enc = np.asarray(encoder.transform(X_raw), dtype=float)

    explainer = shap.TreeExplainer(rf)
    baseline = float(np.asarray(explainer.expected_value).reshape(-1)[0])
    (OUT / "baseline.json").write_text(json.dumps({
        "expected_value": baseline,
        "meaning": "average predicted eff_rate over the model's training distribution; "
                   "the starting point of every waterfall (README §5.1)",
        "n_rows": int(args.rows),
        "random_state": RANDOM_STATE,
        "encoded_columns": list(encoder.get_feature_names_out()),
    }, indent=2) + "\n")

    n_chunks = int(np.ceil(len(X_enc) / CHUNK_SIZE))
    print(f"Explaining {len(X_enc):,} filers in {n_chunks} chunks of {CHUNK_SIZE}. "
          f"Baseline (expected_value) = {baseline:.4f}")

    t_start = time.time()
    done = 0
    for c in range(n_chunks):
        path = CHUNKS / f"shap_{c:04d}.npy"
        lo, hi = c * CHUNK_SIZE, min((c + 1) * CHUNK_SIZE, len(X_enc))
        if args.resume and path.exists():
            print(f"  chunk {c + 1}/{n_chunks} already on disk, skipping")
            continue
        t0 = time.time()
        values = explainer.shap_values(X_enc[lo:hi], check_additivity=True)
        np.save(path, np.asarray(values, dtype=float))
        done += hi - lo
        dt = time.time() - t0
        rate = (time.time() - t_start) / max(done, 1)
        remaining = (len(X_enc) - hi) * rate / 60
        print(f"  chunk {c + 1}/{n_chunks} ({hi - lo} rows) {dt:5.1f}s "
              f"| {rate:.2f} s/row | ~{remaining:.0f} min left", flush=True)

    # Assemble once every chunk exists.
    parts = [np.load(CHUNKS / f"shap_{c:04d}.npy") for c in range(n_chunks)]
    shap_values = np.vstack(parts)
    np.save(OUT / "shap_values_encoded.npy", shap_values)
    np.save(OUT / "X_encoded.npy", X_enc)
    X_raw.to_csv(OUT / "X_raw.csv", index=False)

    # Additivity is the correctness property that makes a waterfall legitimate:
    # baseline + sum(contributions) must equal the model's own prediction.
    pred = rf.predict(X_enc)
    drift = np.abs(shap_values.sum(axis=1) + baseline - pred).max()
    print(f"\nSaved {shap_values.shape} to {OUT.relative_to(ROOT)}")
    print(f"Additivity check: max |baseline + sum(SHAP) - prediction| = {drift:.2e}")
    if drift > 1e-4:
        raise SystemExit("additivity violated; SHAP output is not trustworthy.")
    print(f"Total wall time: {(time.time() - t_start) / 60:.1f} min")


if __name__ == "__main__":
    main()

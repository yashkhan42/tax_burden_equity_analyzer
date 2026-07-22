"""The single boundary between the Streamlit UI and the model.

Everything the demo knows about the model lives in this file. `app.py` imports
only the public names below; it never imports scikit-learn or shap, never opens
a model artifact, and never reconstructs a feature row itself.

STATUS
------
Phase 3 (Random Forest) is not finished, so the four model calls return
*deterministic placeholder values*. Each is marked ``STUB`` with a TODO naming
what replaces it. `MODEL_IS_STUB` is True while that is the case; the UI reads
that flag and says so on screen. Wiring the real model in means editing this
file and flipping that flag — no Streamlit module changes.

    predict_rate(profile)                 -> float          STUB
    get_percentile(rate)                  -> float          STUB
    get_shap_explanation(profile)         -> Explanation    STUB
    get_twin(profile, flip_attribute)     -> (float, float, float)  STUB

    build_feature_row(profile)            -> pd.DataFrame   REAL — do not stub
    derive_filestat(...)                  -> int            REAL
    describe_flip(profile, attribute)     -> (str, str)     REAL

THE PROFILE DICT
----------------
The UI speaks in things a person can answer; the model speaks in the 15 frozen
columns. `build_feature_row` is the translation, and it is the only place that
translation happens. A profile has these keys:

    inctot     int   total personal income, dollars (may be negative)
    incwage    int   wages and salary
    incbus     int   business income (may be negative — losses)
    incint     int   interest
    incdivid   int   dividends
    incretir   int   retirement income
    incss      int   social security
    incrent    int   rent (may be negative — losses)
    age        int   15-85 in the frozen table (topcoded at 85)
    nchild     int   own children in household
    nchlt5     int   own children under 5
    famsize    int   family members in household
    marst      int   IPUMS marital status code, 1-6
    statefip   int   state FIPS code
    filestat   int   tax filer status code, 1-5

The seven raw income amounts are inputs to this module and are NOT model
columns — the model sees only their shares of `inctot`.

SCHEMA PROVENANCE
-----------------
Every constant below is read off the frozen artifacts, not off the README:

    data/processed/freeze_manifest.json   feature list, order, share floor, seed
    data/processed/train.csv              dtypes, level sets, value ranges

Three places where the README's prose disagrees with the frozen table, with the
frozen table winning:

 1. README §3.4 says income shares are guarded when ``inctot <= 0``. The frozen
    table zeroes all seven shares when ``inctot < 1000`` (1,629 of 48,984 train
    rows). Using the README's rule would hand the model feature values it never
    saw in training.
 2. README §3.4 mislabels filestat codes 2 and 3 as separate filers; they are
    joint filers. See the note in codebook.py.
 3. README §3.4 lists `educ`, `empstat`, `sex` and others as optional features.
    None are in the frozen table, so none are collected or constructed here.
"""

from __future__ import annotations

import math
from bisect import bisect_left
from dataclasses import dataclass, field

import pandas as pd

from codebook import FILESTAT_LABELS, INCOME_SOURCE_PHRASES, MARST_LABELS

# ===========================================================================
# Frozen schema — from freeze_manifest.json and train.csv
# ===========================================================================

#: The 15 model columns, in the exact order of freeze_manifest.json's
#: ``feature_cols`` (which is also the column order of train.csv).
FEATURE_COLS: tuple[str, ...] = (
    "inctot",
    "wage_share",
    "business_share",
    "interest_share",
    "dividend_share",
    "retirement_share",
    "socsec_share",
    "rent_share",
    "age",
    "nchild",
    "nchlt5",
    "famsize",
    "filestat",
    "marst",
    "statefip",
)

#: Columns that read back from train.csv as int64 / float64 respectively.
INT_COLS: frozenset[str] = frozenset(
    {"inctot", "age", "nchild", "nchlt5", "famsize", "filestat", "marst", "statefip"}
)
FLOAT_COLS: frozenset[str] = frozenset(FEATURE_COLS) - INT_COLS

#: share column -> the raw dollar amount it is derived from.
SHARE_SOURCE: dict[str, str] = {
    "wage_share": "incwage",
    "business_share": "incbus",
    "interest_share": "incint",
    "dividend_share": "incdivid",
    "retirement_share": "incretir",
    "socsec_share": "incss",
    "rent_share": "incrent",
}

#: Below this total income every share is set to 0.0 rather than divided.
#: freeze_manifest.json -> "inctot_share_floor". This is the guard README §3.3
#: asks for; the frozen table's floor is wider than the README's ``<= 0``.
INCTOT_SHARE_FLOOR = 1000

#: Level sets observed in train.csv. Anything outside these is off-distribution
#: for the model and is rejected rather than silently predicted on.
FILESTAT_LEVELS: tuple[int, ...] = (1, 2, 3, 4, 5)
MARST_LEVELS: tuple[int, ...] = (1, 2, 3, 4, 5, 6)
MARRIED_SPOUSE_PRESENT = 1  # the marst level that pins filestat to {1, 2, 3}
STATEFIP_LEVELS: tuple[int, ...] = (
    1, 2, 4, 5, 6, 8, 9, 10, 11, 12, 13, 15, 16, 17, 18, 19, 20, 21, 22, 23,
    24, 25, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35, 36, 37, 38, 39, 40, 41,
    42, 44, 45, 46, 47, 48, 49, 50, 51, 53, 54, 55, 56,
)

#: Observed ranges in train.csv, used by the UI to bound its widgets so a
#: submitted profile stays inside the region the model was fit on.
AGE_RANGE = (15, 85)          # 85 is topcoded
INCTOT_RANGE = (-9_999, 2_108_379)
NCHILD_MAX = 9
NCHLT5_MAX = 5
FAMSIZE_RANGE = (1, 16)

#: Observed target range in train.csv. Negative rates are real (12.2% of rows,
#: refundable credits exceeding tax owed) and are never clipped at zero — this
#: bound only keeps a placeholder from wandering outside the target's support.
EFF_RATE_RANGE = (-49.99, 33.37)

#: README §3.4 quarantine list. These are the target, its components, and
#: post-tax outputs. They can never be collected from a user or constructed as
#: a feature; `build_feature_row` raises if one appears in a profile.
QUARANTINE_COLS: frozenset[str] = frozenset(
    {
        "eff_rate", "fedtaxac", "adjginc", "spmfedtaxac", "eitcred",
        "ctccrd", "actccrd", "margtax", "taxinc", "fica",
    }
)

#: Profile keys `build_feature_row` requires.
PROFILE_KEYS: frozenset[str] = frozenset(
    {"inctot", "age", "nchild", "nchlt5", "famsize", "filestat", "marst", "statefip"}
    | set(SHARE_SOURCE.values())
)

#: True while the four model calls are placeholders. The UI keys its
#: "not yet connected" banner off this — set it False when the real model is
#: wired in and the banner disappears on its own.
MODEL_IS_STUB = True


# ===========================================================================
# Profile -> model input (REAL — this is the contract, not a placeholder)
# ===========================================================================


def derive_filestat(
    marst: int,
    age: int,
    spouse_65_plus: bool = False,
    head_of_household: bool = False,
) -> int:
    """Return the `filestat` code implied by marital status, age and children.

    In the frozen table `filestat` is not free of `marst` — the two are locked
    together, exactly, across all 48,984 train rows:

        marst == 1 (married, spouse present) <=> filestat in {1, 2, 3}
            both spouses under 65      -> 1   (16,201 rows)
            exactly one spouse 65+     -> 2   (1,574 rows)
            both spouses 65+           -> 3   (3,732 rows)
        marst != 1                     -> filestat in {4, 5}

    So the married branch is fully determined once we know whether each spouse
    has reached 65, and `spouse_65_plus` is the only extra fact the UI has to
    ask for. The unmarried branch is *not* determined: among unmarried filers
    with children, 61% file as head of household and 39% file as single, so the
    caller passes `head_of_household` explicitly rather than having it guessed.
    """
    if marst == MARRIED_SPOUSE_PRESENT:
        both_65 = (age >= 65) + bool(spouse_65_plus)
        return {0: 1, 1: 2, 2: 3}[both_65]
    return 4 if head_of_household else 5


def build_feature_row(profile: dict) -> pd.DataFrame:
    """Turn a profile dict into the one-row frame the model expects.

    Guarantees, all of which are asserted rather than assumed:

    * exactly `FEATURE_COLS`, in that order — no extra columns, none missing;
    * dtypes matching train.csv (int64 for counts, codes and dollars; float64
      for the seven shares);
    * shares computed with the frozen table's floor rule, so a low-income
      profile produces the same feature values the model trained on;
    * no quarantined column can enter, by construction and by check.

    Raises `ValueError` on anything it cannot build faithfully. A wrong feature
    row produces a confident wrong prediction, which is worse than an error.
    """
    leaked = QUARANTINE_COLS & set(profile)
    if leaked:
        raise ValueError(
            f"quarantined column(s) {sorted(leaked)} present in profile — these are "
            "the target or post-tax outputs (README §3.4) and can never be an input"
        )

    missing = PROFILE_KEYS - set(profile)
    if missing:
        raise ValueError(f"profile is missing required key(s): {sorted(missing)}")

    inctot = int(profile["inctot"])
    row: dict[str, float | int] = {"inctot": inctot}

    # Income-composition shares. Below the floor the denominator is too small
    # for a share to mean anything ($50 of income against $500 of interest is
    # 1000%), so the frozen build sets all seven to 0.0 — reproduced exactly.
    # This is also the ``inctot <= 0`` division guard: a zero or negative
    # inctot is below the floor, so no division is ever attempted.
    above_floor = inctot >= INCTOT_SHARE_FLOOR
    for share, source in SHARE_SOURCE.items():
        amount = float(profile[source])
        row[share] = amount / inctot if above_floor else 0.0

    for col in ("age", "nchild", "nchlt5", "famsize", "filestat", "marst", "statefip"):
        row[col] = int(profile[col])

    for col, levels in (
        ("filestat", FILESTAT_LEVELS),
        ("marst", MARST_LEVELS),
        ("statefip", STATEFIP_LEVELS),
    ):
        if row[col] not in levels:
            raise ValueError(
                f"{col}={row[col]} is not a level present in the frozen table "
                f"{list(levels)} — the model has never seen it"
            )

    frame = pd.DataFrame([row], columns=list(FEATURE_COLS))
    frame = frame.astype({c: ("int64" if c in INT_COLS else "float64") for c in FEATURE_COLS})

    assert list(frame.columns) == list(FEATURE_COLS), "feature order drifted"
    assert not (set(frame.columns) & QUARANTINE_COLS), "quarantined column in X"
    return frame


# ===========================================================================
# STUB — model calls
# ===========================================================================

# Mean `eff_rate` over train.csv (5.3104). Stands in for the SHAP baseline,
# which is the model's average prediction over the training set.
STUB_BASELINE = 5.3104

# Coefficients for the placeholder rate. Chosen so the demo shows a plausible,
# internally consistent surface — progressive in income, discounted for capital
# and social-security income, discounted for dependents into the negative tail.
# They encode nobody's findings and must not be quoted anywhere.
_STUB_INCOME_SLOPE = 13.4
_STUB_INCOME_PIVOT = 4.176  # log10 dollars where the income term crosses zero
_STUB_SHARE_WEIGHTS = {
    "wage_share": 0.8,
    "business_share": 1.4,
    "interest_share": -1.2,
    "dividend_share": -6.5,
    "retirement_share": -3.5,
    "socsec_share": -9.0,
    "rent_share": -1.0,
}
_STUB_FILESTAT_WEIGHTS = {1: -1.6, 2: -1.8, 3: -2.0, 4: -2.4, 5: 0.0}


def _stub_terms(frame: pd.DataFrame) -> dict[str, float]:
    """Per-feature contributions of the placeholder surface, in rate points.

    They sum to ``predicted - STUB_BASELINE`` by construction, which is what
    makes the placeholder explanation chart internally consistent.
    """
    r = frame.iloc[0]
    dollars = min(max(int(r["inctot"]), INCTOT_SHARE_FLOOR), INCTOT_RANGE[1])
    income_only = _STUB_INCOME_SLOPE * (math.log10(dollars) - _STUB_INCOME_PIVOT)

    terms: dict[str, float] = {"inctot": income_only - STUB_BASELINE}
    for share, weight in _STUB_SHARE_WEIGHTS.items():
        terms[share] = weight * float(r[share])
    terms["filestat"] = _STUB_FILESTAT_WEIGHTS[int(r["filestat"])]
    terms["marst"] = -0.4 if int(r["marst"]) == MARRIED_SPOUSE_PRESENT else 0.0
    terms["nchild"] = -2.2 * min(int(r["nchild"]), 3)
    terms["nchlt5"] = -0.7 * int(r["nchlt5"])
    terms["famsize"] = -0.2 * max(0, int(r["famsize"]) - 2)
    terms["age"] = -1.3 if int(r["age"]) >= 65 else 0.0
    # The placeholder is deliberately flat in geography: federal rates do not
    # vary by state by construction. The real model may still find a signal
    # here through what state correlates with.
    terms["statefip"] = 0.0

    # Keep the placeholder inside the target's observed support. The lower
    # bound is the observed minimum (-49.99), NOT zero: negative rates are a
    # real outcome for 12.2% of filers and are never clipped away (§3.3).
    raw = STUB_BASELINE + sum(terms.values())
    clamped = min(max(raw, EFF_RATE_RANGE[0]), EFF_RATE_RANGE[1])
    terms["inctot"] += clamped - raw
    return terms


def predict_rate(profile: dict) -> float:
    """Predicted average effective federal tax rate, in percent.

    STUB — returns a deterministic placeholder, not a prediction. It builds the
    real feature row first, so a schema mistake surfaces here rather than after
    the model lands.

    TODO(phase 3): replace the body below with

        model = _load_model()                     # joblib artifact + encoder
        return float(model.predict(build_feature_row(profile))[0])

    keeping `build_feature_row` exactly as it is, and set MODEL_IS_STUB = False.
    """
    frame = build_feature_row(profile)
    return STUB_BASELINE + sum(_stub_terms(frame).values())


# Shape of the `eff_rate` distribution over train.csv (48,984 rows), as
# (bin_start, share_of_filers) in 2.5-point bins. The UI draws this so the
# reader sees the real shape rather than an assumed bell: a long negative tail
# from refundable credits, a hard spike at zero, and a short right tail.
#
# TODO(phase 3): recompute over the model's predictions, alongside the
# percentile knots below. Predictions are less dispersed than outcomes, so the
# real curve will be narrower than this one.
RATE_DISTRIBUTION: tuple[tuple[float, float], ...] = (
    (-50.0, 0.00149), (-47.5, 0.00316), (-45.0, 0.00306), (-42.5, 0.00253),
    (-40.0, 0.00257), (-37.5, 0.00247), (-35.0, 0.00351), (-32.5, 0.00318),
    (-30.0, 0.00351), (-27.5, 0.00323), (-25.0, 0.00388), (-22.5, 0.00408),
    (-20.0, 0.00423), (-17.5, 0.00482), (-15.0, 0.00441), (-12.5, 0.00635),
    (-10.0, 0.01533), (-7.5, 0.01378), (-5.0, 0.01627), (-2.5, 0.02019),
    (0.0, 0.14382), (2.5, 0.10744), (5.0, 0.17277), (7.5, 0.17044),
    (10.0, 0.10209), (12.5, 0.08631), (15.0, 0.05165), (17.5, 0.02333),
    (20.0, 0.01006), (22.5, 0.00267), (25.0, 0.00292), (27.5, 0.00253),
    (30.0, 0.00131), (32.5, 0.00057),
)
DISTRIBUTION_BIN_WIDTH = 2.5

#: Two facts the distribution chart annotates, because both surprise people.
SHARE_EXACTLY_ZERO = 0.0853   # owe precisely nothing: about 1 filer in 12
SHARE_NEGATIVE = 0.1221       # get more back than they pay: about 1 in 8

# Empirical percentiles of `eff_rate` over train.csv (48,984 rows), as
# (rate, percentile) knots. Note the flat run at 0.0 spanning p15-p20: a real
# mass of filers owe exactly nothing.
PERCENTILE_KNOTS: tuple[tuple[float, float], ...] = (
    (-49.99, 0), (-40.31, 1), (-31.36, 2), (-12.56, 5), (-2.65, 10),
    (0.00, 15), (0.00, 20), (2.04, 25), (3.40, 30), (5.51, 40),
    (6.93, 50), (8.11, 60), (9.53, 70), (10.87, 75), (12.02, 80),
    (13.35, 85), (14.81, 90), (17.16, 95), (20.02, 98), (22.48, 99),
    (33.37, 100),
)


def get_percentile(rate: float) -> float:
    """Where `rate` sits in the distribution of filers, 0-100.

    STUB — interpolates the *actual* `eff_rate` distribution of train.csv,
    which is a stand-in for the distribution of the model's *predicted* rates.
    The two differ: a regression's predictions are less dispersed than the
    outcome, so this placeholder overstates how extreme a percentile looks at
    the tails.

    TODO(phase 3): recompute the knots from the model's predictions over
    train.csv (predict once at build time, persist the percentile grid beside
    the model artifact) and read them here instead of the literal above.
    """
    rates = [k[0] for k in PERCENTILE_KNOTS]
    pcts = [k[1] for k in PERCENTILE_KNOTS]

    if rate <= rates[0]:
        return 0.0
    if rate >= rates[-1]:
        return 100.0

    i = bisect_left(rates, rate)
    if rates[i] == rate:
        # Flat run (many filers at the same rate) — report its midpoint.
        j = i
        while j + 1 < len(rates) and rates[j + 1] == rate:
            j += 1
        return (pcts[i] + pcts[j]) / 2

    lo_rate, hi_rate = rates[i - 1], rates[i]
    lo_pct, hi_pct = pcts[i - 1], pcts[i]
    fraction = (rate - lo_rate) / (hi_rate - lo_rate)
    return lo_pct + fraction * (hi_pct - lo_pct)


@dataclass
class Explanation:
    """A SHAP-shaped explanation.

    Attribute names mirror `shap.Explanation` (`base_values`, `values`,
    `data`, `feature_names`) so that when TreeExplainer output replaces this,
    the chart in app.py reads the same attributes and does not change.
    """

    base_values: float
    values: list[float]
    data: list[float]
    feature_names: list[str] = field(default_factory=lambda: list(FEATURE_COLS))

    @property
    def predicted(self) -> float:
        """Baseline plus every contribution — where the waterfall lands."""
        return self.base_values + sum(self.values)


def get_shap_explanation(profile: dict) -> Explanation:
    """Per-feature attribution for this profile, in rate points.

    STUB — decomposes the placeholder surface of `predict_rate` into its own
    terms. It is arithmetic on a made-up function, not an attribution of a
    learned model, and no conclusion may be drawn from it.

    TODO(phase 4): replace with

        explainer = shap.TreeExplainer(model)     # cached module-level
        return explainer(build_feature_row(profile))

    and, if the model one-hot encodes the categoricals, collapse the encoded
    columns back to their source feature here so the chart stays readable.
    """
    frame = build_feature_row(profile)
    terms = _stub_terms(frame)
    return Explanation(
        base_values=STUB_BASELINE,
        values=[terms[c] for c in FEATURE_COLS],
        data=[float(frame.iloc[0][c]) for c in FEATURE_COLS],
        feature_names=list(FEATURE_COLS),
    )


# ---------------------------------------------------------------------------
# Twin comparison (README §5.2)
# ---------------------------------------------------------------------------

#: The four attributes §5.2 names as flippable, and nothing else. `get_twin`
#: rejects anything outside this set: a flip of some other attribute is not a
#: counterfactual this project has agreed to make a claim about.
TWIN_FLIP_ATTRIBUTES: tuple[str, ...] = (
    "filing_status",
    "marital_status",
    "dominant_income_source",
    "dependents",
)

# Reader-facing names for these four live in codebook.TWIN_FLIP_LABELS —
# nothing in this module writes copy.


def _flip_profile(profile: dict, flip_attribute: str) -> tuple[dict, str, str]:
    """Build the twin: copy the profile, change exactly one attribute.

    Returns ``(twin_profile, from_label, to_label)``. Both `get_twin` and
    `describe_flip` go through here, so the number on screen and the sentence
    describing it can never disagree.

    Flip rules — each is a choice the twin engine owns, stated explicitly:

    * filing_status — single <-> married filing jointly, with `marst` held
      fixed. In the frozen table those two always move together, so the twin is
      off-distribution by design: that is the point, it isolates the tax
      treatment from the marriage itself. Head of household flips to single.
    * marital_status — never married <-> married with spouse present, and
      `filestat` follows, because in the data it always does.
    * dominant_income_source — moves the dollars of the largest income
      component into another component, holding `inctot` fixed. Wage-dominant
      profiles become dividend-dominant; everything else becomes wage-dominant.
    * dependents — 0 children <-> 2 children. `nchlt5` follows down to 0 when
      children go to 0 (it cannot exceed `nchild`).
    """
    if flip_attribute not in TWIN_FLIP_ATTRIBUTES:
        raise ValueError(
            f"{flip_attribute!r} is not a permitted twin flip; README §5.2 allows "
            f"only {list(TWIN_FLIP_ATTRIBUTES)}"
        )

    twin = dict(profile)

    if flip_attribute == "filing_status":
        current = int(profile["filestat"])
        from_label = FILESTAT_LABELS[current]
        if current in (1, 2, 3):
            twin["filestat"] = 5
        else:
            twin["filestat"] = derive_filestat(
                MARRIED_SPOUSE_PRESENT, int(profile["age"]), spouse_65_plus=False
            )
        return twin, from_label, FILESTAT_LABELS[twin["filestat"]]

    if flip_attribute == "marital_status":
        current = int(profile["marst"])
        married = current == MARRIED_SPOUSE_PRESENT
        twin["marst"] = 6 if married else MARRIED_SPOUSE_PRESENT
        twin["filestat"] = derive_filestat(
            twin["marst"],
            int(profile["age"]),
            spouse_65_plus=False,
            head_of_household=int(profile["nchild"]) > 0,
        )
        return twin, MARST_LABELS[current], MARST_LABELS[twin["marst"]]

    if flip_attribute == "dominant_income_source":
        amounts = {src: float(profile[src]) for src in SHARE_SOURCE.values()}
        source = max(amounts, key=lambda k: amounts[k])
        target = "incdivid" if source == "incwage" else "incwage"
        moved = amounts[source]
        twin[source] = amounts[source] - moved
        twin[target] = amounts[target] + moved
        return twin, _income_label(source), _income_label(target)

    # dependents
    current_children = int(profile["nchild"])
    if current_children > 0:
        twin["nchild"] = 0
        twin["nchlt5"] = 0  # mechanically implied, not a second flip
    else:
        twin["nchild"] = 2
    # NOTE(phase 5): `famsize` is held constant here so that exactly one
    # attribute moves. In the frozen table famsize tracks nchild almost
    # perfectly (mean famsize is 2.03 at 0 children, 3.04 at 1, 4.02 at 2), so
    # the twin engine's owner should decide whether the honest counterfactual
    # moves famsize too. Whichever way that lands, change it here only.
    return twin, _children_label(current_children), _children_label(twin["nchild"])


def _income_label(source: str) -> str:
    return f"mostly from {INCOME_SOURCE_PHRASES[source]}"


def _children_label(n: int) -> str:
    return "no children" if n == 0 else f"{n} {'child' if n == 1 else 'children'}"


def get_twin(profile: dict, flip_attribute: str) -> tuple[float, float, float]:
    """Rates for a filer and their counterfactual twin, and the gap between.

    Returns ``(base_rate, twin_rate, gap)`` in rate points, where
    ``gap = twin_rate - base_rate``.

    STUB — both rates come from `predict_rate`, which is itself a placeholder,
    so the gap is a placeholder gap. The flip logic in `_flip_profile` is real
    and is what the Phase 5 engine should keep.

    TODO(phase 5): once `predict_rate` calls the model this function is already
    correct — it needs no change beyond whatever `_flip_profile` decides about
    famsize. Confirm with the twin-engine owner that the flip rules above match
    the counterfactuals the writeup claims.
    """
    twin_profile, _, _ = _flip_profile(profile, flip_attribute)
    base_rate = predict_rate(profile)
    twin_rate = predict_rate(twin_profile)
    return base_rate, twin_rate, twin_rate - base_rate


def describe_flip(profile: dict, flip_attribute: str) -> tuple[str, str]:
    """Human labels for what a flip changes: ``(from_label, to_label)``.

    `get_twin` returns three floats and so cannot say what it flipped. The UI
    needs to name the counterfactual it is showing, and asking here — rather
    than re-deriving it in app.py — keeps the label and the number in step.
    """
    _, from_label, to_label = _flip_profile(profile, flip_attribute)
    return from_label, to_label

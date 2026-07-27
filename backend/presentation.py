"""Turn public model-interface results into the locked display contracts."""

from __future__ import annotations

import model_interface as mi
from codebook import (
    FILESTAT_LABELS,
    INCOME_SOURCE_PHRASES,
    MARST_LABELS,
    SHARED_ATTRIBUTES_MOVED_BY,
    SHARED_ATTRIBUTE_LABELS,
    SHARED_ATTRIBUTE_ORDER,
    STATE_NAMES,
    TWIN_FLIP_LABELS,
    age_phrase,
    children_phrase,
    household_phrase,
    phrase_for,
)

from .schemas import (
    ContributionResponse,
    DistributionBin,
    PercentileResponse,
    PredictResponse,
    Reason,
    TaxProfile,
    TwinAttribute,
    TwinComparison,
    TwinResponse,
    TwinSide,
)


FRAMING = (
    "This is a predicted average for filers with these characteristics — not a "
    "calculation of anyone's own tax bill."
)
MIN_REASON = 0.15
MAX_REASONS = 5
NEGLIGIBLE_GAP = 0.05

COMPARISON_TO_MODEL = {
    TwinComparison.filing: "filing_status",
    TwinComparison.marital: "marital_status",
    TwinComparison.income_source: "dominant_income_source",
    TwinComparison.dependents: "dependents",
}
CHANGED_LABELS = {
    TwinComparison.filing: "How they file",
    TwinComparison.marital: "Marital status",
    TwinComparison.income_source: "Where the money comes from",
    TwinComparison.dependents: "Children at home",
}


def rounded_one(value: float) -> float:
    rounded = round(float(value), 1)
    return 0.0 if rounded == 0 else rounded


def format_rate(value: float) -> str:
    rounded = rounded_one(value)
    return f"{'−' if rounded < 0 else ''}{abs(rounded):.1f}%"


def _rounded_money(amount: float) -> float:
    magnitude = abs(amount)
    step = 10 if magnitude < 1_000 else (100 if magnitude < 10_000 else 1_000)
    return round(amount / step) * step


def money(amount: float) -> str:
    value = _rounded_money(amount)
    return f"−${abs(value):,.0f}" if value < 0 else f"${value:,.0f}"


def predict(profile: TaxProfile) -> PredictResponse:
    rate = float(mi.predict_rate(profile.to_model_profile()))
    displayed = rounded_one(rate)
    return PredictResponse(
        rate=displayed,
        display=format_rate(displayed),
        isNegative=displayed < 0,
        framing=FRAMING,
    )


def percentile(profile: TaxProfile) -> PercentileResponse:
    raw = profile.to_model_profile()
    rate = float(mi.predict_rate(raw))
    rank = float(mi.get_percentile(rate))
    below = min(100, max(0, round(rank)))
    if below >= 99:
        summary = (
            "Among the survey examples used for comparison, fewer than one "
            "in 100 has a higher predicted rate."
        )
    elif below <= 1:
        summary = (
            "Among the survey examples used for comparison, fewer than one "
            "in 100 has a lower predicted rate."
        )
    else:
        summary = (
            "Among the survey examples used for comparison, "
            f"about {below} in 100 have a lower predicted rate and "
            f"about {100 - below} are higher."
        )
    return PercentileResponse(
        markerRate=rate,
        displayRate=format_rate(rate),
        percentile=round(rank, 1),
        belowCount=below,
        bins=[
            DistributionBin(start=float(start), share=float(share))
            for start, share in mi.RATE_DISTRIBUTION
        ],
        binWidth=float(mi.DISTRIBUTION_BIN_WIDTH),
        shareExactlyZero=float(mi.SHARE_EXACTLY_ZERO),
        shareNegative=float(mi.SHARE_NEGATIVE),
        domain=(-52.0, 36.0),
        summary=summary,
    )


def contribution(profile: TaxProfile) -> ContributionResponse:
    explanation = mi.get_shap_explanation(profile.to_model_profile())
    kept: list[tuple[str, float]] = []
    rest = 0.0
    for name, value, given in zip(
        explanation.feature_names, explanation.values, explanation.data
    ):
        words = phrase_for(name, given)
        if words and abs(float(value)) >= MIN_REASON:
            kept.append((words, float(value)))
        else:
            rest += float(value)

    kept.sort(key=lambda pair: abs(pair[1]), reverse=True)
    if len(kept) > MAX_REASONS:
        rest += sum(value for _, value in kept[MAX_REASONS:])
        kept = kept[:MAX_REASONS]

    baseline = float(explanation.base_values)
    predicted = float(explanation.predicted)
    nothing = not kept and abs(predicted - baseline) < NEGLIGIBLE_GAP
    remainder = rounded_one(rest)
    remainder_value = None if remainder == 0.0 else remainder
    reasons = [Reason(text=text, points=rounded_one(value)) for text, value in kept]

    if nothing:
        summary = (
            "Nothing about this filer stands out; their predicted rate is close "
            "to the model's typical prediction."
        )
    elif reasons:
        summary = (
            "The strongest profile details explain most of why this estimate "
            "differs from the typical prediction."
        )
    else:
        summary = (
            "No single named reason stands out, but the smaller effects together "
            "move the predicted rate."
        )

    return ContributionResponse(
        baseline=rounded_one(baseline),
        predicted=rounded_one(predicted),
        reasons=reasons,
        remainder=remainder_value,
        nothingStandsOut=nothing,
        summary=summary,
    )


def _dominant_income_phrase(raw: dict) -> str:
    if float(raw["unit_inctot"]) < mi.INCTOT_SHARE_FLOOR:
        return "too little income to say"
    amounts = {source: float(raw[source]) for source in mi.SHARE_SOURCE.values()}
    largest = max(amounts, key=amounts.get)
    if float(raw["spouse_income"]) > amounts[largest]:
        return "mostly from a spouse's income"
    if amounts[largest] <= 0:
        return "too little income to say"
    return f"mostly from {INCOME_SOURCE_PHRASES[largest]}"


def _shared_attributes(raw: dict, model_comparison: str) -> list[TwinAttribute]:
    values = {
        "income": f"roughly {money(raw['unit_inctot'])} a year",
        "source": _dominant_income_phrase(raw),
        "age": age_phrase(raw["age"]),
        "children": children_phrase(raw["nchild"], raw["nchlt5"]),
        "household": household_phrase(raw["famsize"]),
        "marital": MARST_LABELS[raw["marst"]],
        "filing": FILESTAT_LABELS[raw["filing_status"]],
        "state": STATE_NAMES[raw["statefip"]],
    }
    moved = set(SHARED_ATTRIBUTES_MOVED_BY[model_comparison])
    return [
        TwinAttribute(label=SHARED_ATTRIBUTE_LABELS[name], value=values[name])
        for name in SHARED_ATTRIBUTE_ORDER
        if name not in moved
    ]


def twin(profile: TaxProfile, comparison: TwinComparison) -> TwinResponse:
    raw = profile.to_model_profile()
    model_comparison = COMPARISON_TO_MODEL[comparison]
    base_rate, twin_rate, raw_gap = mi.get_twin(raw, model_comparison)
    from_label, to_label = mi.describe_flip(raw, model_comparison)
    base_displayed = rounded_one(base_rate)
    twin_displayed = rounded_one(twin_rate)
    displayed_gap = rounded_one(twin_displayed - base_displayed)
    changed = TWIN_FLIP_LABELS[model_comparison]

    gap_money = None
    if (
        abs(displayed_gap) >= 0.1
        and float(raw["unit_inctot"]) >= mi.INCTOT_SHARE_FLOOR
    ):
        annual = abs(raw_gap) / 100 * float(raw["unit_inctot"])
        gap_money = f"About {money(annual)} a year at this income."

    if abs(displayed_gap) < NEGLIGIBLE_GAP:
        summary = (
            f"Either way — {from_label} or {to_label} — the predicted rate is "
            f"essentially the same at {format_rate(base_displayed)}."
        )
    else:
        direction = "higher" if displayed_gap > 0 else "lower"
        summary = (
            f"Changing {changed} from {from_label} to {to_label} makes the "
            f"predicted rate {abs(displayed_gap):.1f} points {direction}."
        )
        if min(base_displayed, twin_displayed) < 0 < max(
            base_displayed, twin_displayed
        ):
            summary += " One side pays; the other is paid."

    return TwinResponse(
        changed=changed,
        changedLabel=CHANGED_LABELS[comparison],
        a=TwinSide(
            label=from_label,
            rate=base_displayed,
            display=format_rate(base_displayed),
        ),
        b=TwinSide(
            label=to_label,
            rate=twin_displayed,
            display=format_rate(twin_displayed),
        ),
        shared=_shared_attributes(raw, model_comparison),
        gapPoints=displayed_gap,
        gapMoney=gap_money,
        summary=summary,
        comparisonNote=(
            "This is one generated comparison with the return's economics held "
            "fixed, not a finding about all filers."
        ),
    )


def warm_model() -> None:
    """Exercise every public model path so readiness means all endpoints work."""
    profile = TaxProfile(
        totalIncome=64_000,
        spouseIncome=0,
        income={
            "wages": 64_000,
            "business": 0,
            "interest": 0,
            "dividends": 0,
            "retirement": 0,
            "socialSecurity": 0,
            "rent": 0,
        },
        age=42,
        childrenAtHome=0,
        childrenUnderFive=0,
        householdSize=1,
        maritalStatus="never_married",
        filingChoice="single",
        state="New York",
    )
    raw = profile.to_model_profile()
    rate = mi.predict_rate(raw)
    mi.get_percentile(rate)
    mi.get_shap_explanation(raw)
    mi.get_twin(raw, "filing_status")

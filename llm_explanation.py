"""
llm_explanation.py — Plain-English explanations of a filer's predicted tax rate.

Additive layer: reads the SHAP output the model already produces
(reports/shap/shap_explanations.json) and turns one filer's explanation into
a short paragraph a non-expert can read.

Two modes:
  - template  (default): rule-based sentences, no API key, always works.
  - llm       (optional): sends the same facts to an LLM for smoother prose,
                          falls back to template if anything goes wrong.
"""

# ---- 1. Human-readable names for the model's internal feature codes ----
FEATURE_LABELS = {
    "unit_inctot": "total household income",
    "wage_share": "share of income from wages",
    "business_share": "share of income from business",
    "interest_share": "share of income from interest",
    "dividend_share": "share of income from dividends",
    "retirement_share": "share of income from retirement",
    "socsec_share": "share of income from Social Security",
    "rent_share": "share of income from rent",
    "spouse_income_share": "a second earner on the return",
    "age": "age",
    "nchild": "number of children",
    "nchlt5": "number of young children",
    "famsize": "household size",
    "filing_status": "filing status",
    "marst": "marital status",
    "statefip": "state",
}

FILING_STATUS = {1: "married filing jointly", 4: "head of household", 5: "single"}


def _describe_feature(feature, value):
    """Turn one feature + its value into a readable phrase."""
    if feature == "filing_status":
        return FILING_STATUS.get(int(value), "their filing status")
    if feature == "unit_inctot":
        return f"their income of ${int(value):,}"
    if feature == "nchild":
        n = int(value)
        return "having no children" if n == 0 else f"having {n} child{'ren' if n != 1 else ''}"
    if feature.endswith("_share"):
        pct = round(value * 100)
        return f"{FEATURE_LABELS.get(feature, feature)} ({pct}%)"
    return FEATURE_LABELS.get(feature, feature)


def build_facts(explanation):
    """Pull the key numbers out of one archetype/sample entry."""
    baseline = explanation["baseline"]
    predicted = explanation["predicted"]
    reasons = explanation["reasons"]
    ups = [r for r in reasons if r["points"] > 0]
    downs = [r for r in reasons if r["points"] < 0]
    return {"baseline": baseline, "predicted": predicted, "ups": ups, "downs": downs}


# ---- 2. TEMPLATE explainer (always available) ----
def explain_template(explanation):
    f = build_facts(explanation)
    parts = []
    parts.append(
        f"This filer's predicted effective tax rate is {f['predicted']:.1f}%, "
        f"compared with an average of {f['baseline']:.1f}% across all filers."
    )
    if f["downs"]:
        top = max(f["downs"], key=lambda r: abs(r["points"]))
        parts.append(
            f"The biggest factor lowering their rate is {_describe_feature(top['feature'], top['value'])}, "
            f"which pulls it down by about {abs(top['points']):.1f} points."
        )
    if f["ups"]:
        top = max(f["ups"], key=lambda r: r["points"])
        parts.append(
            f"Working the other way, {_describe_feature(top['feature'], top['value'])} "
            f"raises it by about {top['points']:.1f} points."
        )
    return " ".join(parts)


# ---- 3. LLM explainer (optional upgrade, safe fallback) ----
def explain_llm(explanation, model="gpt-4o-mini"):
    """Try the LLM; on any failure, fall back to the template."""
    try:
        from openai import OpenAI
        client = OpenAI()  # reads OPENAI_API_KEY from environment
        f = build_facts(explanation)
        facts_lines = [
            f"- Average rate across filers: {f['baseline']:.1f}%",
            f"- This filer's predicted rate: {f['predicted']:.1f}%",
        ]
        for r in explanation["reasons"]:
            direction = "raises" if r["points"] > 0 else "lowers"
            facts_lines.append(
                f"- {_describe_feature(r['feature'], r['value'])} {direction} the rate "
                f"by {abs(r['points']):.1f} points"
            )
        prompt = (
            "You are explaining a tax model's prediction to someone with no tax or "
            "statistics background. Using ONLY the facts below, write 2-3 short, "
            "clear sentences. Do not use jargon like SHAP, feature, or model. "
            "Do not invent numbers.\n\n" + "\n".join(facts_lines)
        )
        resp = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=180,
            temperature=0.3,
        )
        return resp.choices[0].message.content.strip()
    except Exception:
        # API missing, no key, network down — never break the demo.
        return explain_template(explanation)


def explain(explanation, use_llm=False):
    """Main entry point. use_llm=False is the safe default."""
    return explain_llm(explanation) if use_llm else explain_template(explanation)


# ---- quick manual test ----
if __name__ == "__main__":
    import json, sys
    path = sys.argv[1] if len(sys.argv) > 1 else "reports/shap/shap_explanations.json"
    data = json.load(open(path))
    for name, exp in data["archetypes"].items():
        print(f"\n=== {name} ===")
        print(explain(exp, use_llm=False))
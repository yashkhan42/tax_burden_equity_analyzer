"""The page a reader sees.

Presentation only. Every number comes from `model_interface`, which is the one
and only path to the model; nothing here imports a modelling library, opens a
model file, or reads the survey. Everything drawn by Altair comes from
`charts`, everything drawn by React comes through `viz`, and every word a
reader can see comes from here or from `codebook`.

Three rules this file follows without exception.

**Form first, results after.** Nothing is worked out until the reader has
described someone and asked for the rate. After that first ask, the page is
live: changing anything in the tool updates it in place, with no second
button press, because a reader who has already committed once should not have
to keep committing.

**One idea per moment.** Four short chapters with a wide silence between them,
not a dashboard. Each chapter says one thing, shows one thing, and stops.

**Nothing internal reaches the screen.** No file names, no module names, no
column names, no codes, no acronyms. That rule extends past the page to the
two React components: everything crossing that boundary is finished English
and pre-rounded numbers. The components render what they are given; they never
decide what a number means or how many decimals it deserves.
"""

import threading

import streamlit as st

import charts
import model_interface as mi
import page_style
import viz
from codebook import (
    FILESTAT_LABELS,
    FILING_CHOICE_LABELS,
    INCOME_COMPONENT_LABELS,
    INCOME_SOURCE_PHRASES,
    MARST_LABELS,
    SHARED_ATTRIBUTES_MOVED_BY,
    SHARED_ATTRIBUTE_LABELS,
    SHARED_ATTRIBUTE_ORDER,
    STATE_NAMES,
    TWIN_FLIP_LABELS,
    TWIN_FLIP_QUESTIONS,
    age_phrase,
    children_phrase,
    household_phrase,
    in_words,
    phrase_for,
)

st.set_page_config(
    page_title="Where the tax falls",
    layout="wide",
    initial_sidebar_state="collapsed",
)


@st.cache_resource(show_spinner=False)
def _warm_the_predictor() -> None:
    """Start fetching the trained predictor while the reader reads.

    On a host that installs requirements and runs this file, the predictor is
    not on disk when the page first opens. Fetching it takes about twenty
    seconds. Doing that on the reader's first question would answer a lever
    they just pulled with a long silence; doing it here, in the background,
    spends that time while they are still reading and filling in the form.

    The thread only puts a file in place -- it draws nothing and decides
    nothing -- so this stays a page that asks the model boundary for numbers
    and never touches a model itself. If it fails, or has not finished when the
    reader asks, the ordinary path simply waits or shows the ordinary
    unavailable notice; nothing here changes what a reader sees.
    """
    threading.Thread(target=mi.prepare_artifact, daemon=True).start()


_warm_the_predictor()

# ---------------------------------------------------------------------------
# Constants that are design decisions, not incidentals
# ---------------------------------------------------------------------------

#: Vertical rhythm. Chapters are separated by roughly three times the gap used
#: inside one, which is what makes them read as chapters rather than as rows.
#: Streamlit adds margins of its own between elements, so these land within a
#: few pixels rather than exactly — an accepted cost of not owning the page.
CHAPTER_GAP = 96
BLOCK_GAP = 32
FIGURE_GAP = 16

#: The sentence that stays with every number on the page.
FRAMING = (
    "This is a predicted average for filers with these characteristics — not a "
    "calculation of anyone's own tax bill."
)

#: Reasons smaller than this are dropped from chapter three and folded into the
#: single closing row instead. Below a sixth of a point nothing is being
#: explained, only decorated.
MIN_REASON = 0.15

#: At most five reasons are shown. The sixth and beyond join the closing row,
#: so nothing is silently dropped.
MAX_REASONS = 5

#: A gap this small is not a difference, and drawing it as one would invent a
#: finding out of rounding.
NEGLIGIBLE_GAP = 0.05


def theme_type() -> str:
    """Which mode the reader is in, so charts and components can match it.

    A sandboxed component cannot see the host page's colours, so the mode
    travels with every payload. Dark is the fallback because the page opens
    dark and an unknown answer should look like the common case.
    """
    try:
        return st.context.theme.type or "dark"
    except Exception:
        return "dark"


def space(pixels: int) -> None:
    """An explicit vertical gap. The only way to hold rhythm without CSS."""
    st.container(height=pixels, border=False)


# ---------------------------------------------------------------------------
# Money, rounded once and formatted twice
# ---------------------------------------------------------------------------


def _rounded(amount: float) -> float:
    """Money to a deliberate magnitude — never to false precision."""
    magnitude = abs(amount)
    step = 10 if magnitude < 1_000 else (100 if magnitude < 10_000 else 1_000)
    return round(amount / step) * step


def money(amount: float) -> str:
    """Rounded money, plain. For anything that is not Streamlit markdown."""
    value = _rounded(amount)
    return f"−${abs(value):,.0f}" if value < 0 else f"${value:,.0f}"


def escape_dollars(text: str) -> str:
    """Make a string safe to hand to Streamlit markdown.

    Streamlit reads ``$…$`` as mathematics, so an unescaped pair of dollar
    signs in one paragraph silently swallows every word between them. The React
    components are not markdown and must be given the unescaped form, which is
    why escaping happens here at the point of printing rather than at the point
    of formatting.
    """
    return text.replace("$", "\\$")


def dominant_income_phrase(filer: dict) -> str:
    """Where most of the money came from, in words.

    Below the point where income is too small for a composition to mean
    anything, the honest answer is that there is no answer — the same rule the
    frozen data uses, read from there rather than restated here.
    """
    if float(filer["unit_inctot"]) < mi.INCTOT_SHARE_FLOOR:
        return "too little income to say"
    amounts = {source: float(filer[source]) for source in mi.SHARE_SOURCE.values()}
    largest = max(amounts, key=lambda source: amounts[source])
    if float(filer["spouse_income"]) > amounts[largest]:
        return "mostly from a spouse's income"
    if amounts[largest] <= 0:
        return "too little income to say"
    return f"mostly from {INCOME_SOURCE_PHRASES[largest]}"


# ---------------------------------------------------------------------------
# The model, asked once per distinct question
# ---------------------------------------------------------------------------
# Chapter four invites the reader to try one comparison after another, so these
# results are remembered. Flipping the comparison then costs one new answer
# instead of four, which is the difference between a page that feels like it is
# thinking and one that feels like it already knows.


def _key(filer: dict) -> tuple:
    return tuple(sorted(filer.items()))


@st.cache_data(show_spinner=False)
def rate_for(key: tuple) -> float:
    return mi.predict_rate(dict(key))


@st.cache_data(show_spinner=False)
def reasons_for(key: tuple):
    return mi.get_shap_explanation(dict(key))


@st.cache_data(show_spinner=False)
def standing_for(rate: float) -> float:
    return mi.get_percentile(rate)


@st.cache_data(show_spinner=False)
def twin_for(key: tuple, change: str) -> tuple[float, float, float]:
    return mi.get_twin(dict(key), change)


@st.cache_data(show_spinner=False)
def twin_labels_for(key: tuple, change: str) -> tuple[str, str]:
    return mi.describe_flip(dict(key), change)


# ===========================================================================
# The page opening: website first, tool second
# ===========================================================================

st.html(page_style.site_header(theme_type()))
hero_copy, hero_argument = st.columns(2, gap="large", vertical_alignment="top")
with hero_copy:
    st.html(page_style.hero_copy(theme_type()))
with hero_argument:
    st.html(page_style.hero_argument(theme_type()))

if mi.MODEL_IS_STUB:
    st.html(
        page_style.notice(
            theme_type(),
            "Everything below is a stand-in.",
            (
                "The part of this project that learns from the survey is still "
                "being built, so these figures test the experience rather than "
                "report a result."
            ),
        )
    )


# ===========================================================================
# The tool: everything about this return
# ===========================================================================

st.html(
    page_style.section_heading(
        theme_type(),
        "The tool",
        "Build a comparison",
        anchor="build-a-comparison",
        lead=(
            "Start with the whole return, then describe where the non-spouse "
            "income comes from and who lives in the household."
        ),
    )
)

with st.container(border=True):
    st.html(
        page_style.form_group(
            theme_type(),
            "The return",
            "Annual amounts before federal tax. Use the same year for every field.",
        )
    )
    income_col, relationship_col, filing_col = st.columns(
        3, gap="large", vertical_alignment="bottom"
    )
    with income_col:
        total_income = st.number_input(
            "Total income on the return",
            min_value=int(mi.UNIT_INCTOT_RANGE[0]),
            max_value=int(mi.UNIT_INCTOT_RANGE[1]),
            value=64_000,
            step=1_000,
            help=(
                "Income for everyone represented on the return, including a "
                "spouse and any dependents claimed."
            ),
            key="unit_income",
        )
    with relationship_col:
        marital_status = st.selectbox(
            "Marital status",
            options=mi.MARST_LEVELS,
            index=mi.MARST_LEVELS.index(6),
            format_func=lambda code: MARST_LABELS[code],
            key="marital_status",
        )

    married = marital_status == mi.MARRIED_SPOUSE_PRESENT
    filing_alone_choice = 5
    if married:
        with filing_col:
            spouse_income = st.number_input(
                "Spouse's total income",
                min_value=0,
                value=0,
                step=1_000,
                help=(
                    "Enter the spouse's whole annual income here. Leave it out "
                    "of the source amounts below."
                ),
                key="spouse_income",
            )
        filing_status = mi.derive_filing_status(int(marital_status))
        st.caption(
            "Married couples living together are represented as filing "
            "together, matching the ordinary combinations in the survey."
        )
    else:
        spouse_income = 0
        with filing_col:
            filing_alone_choice = st.radio(
                "How they file",
                options=[4, 5],
                index=1,
                format_func=lambda code: FILING_CHOICE_LABELS[code],
                help=(
                    "A person supporting children or another qualifying "
                    "relative may be able to file as head of household."
                ),
                key="filing_choice",
            )
        filing_status = mi.derive_filing_status(
            int(marital_status),
            head_of_household=filing_alone_choice == 4,
        )

    space(BLOCK_GAP)
    st.html(
        page_style.form_group(
            theme_type(),
            "Where the non-spouse income comes from",
            (
                "Enter these amounts for the person described here and any "
                "dependents they claim. Leave out their spouse's income."
            ),
        )
    )
    source_row_one = st.columns(4, gap="large", vertical_alignment="bottom")
    with source_row_one[0]:
        wage_income = st.number_input(
            INCOME_COMPONENT_LABELS["incwage"].capitalize(),
            min_value=0,
            value=58_000,
            step=1_000,
            key="income_wage",
        )
    with source_row_one[1]:
        business_income = st.number_input(
            INCOME_COMPONENT_LABELS["incbus"].capitalize(),
            min_value=-500_000,
            value=0,
            step=1_000,
            help="A business loss belongs here as a negative amount.",
            key="income_business",
        )
    with source_row_one[2]:
        interest_income = st.number_input(
            INCOME_COMPONENT_LABELS["incint"].capitalize(),
            min_value=0,
            value=1_000,
            step=500,
            key="income_interest",
        )
    with source_row_one[3]:
        dividend_income = st.number_input(
            INCOME_COMPONENT_LABELS["incdivid"].capitalize(),
            min_value=0,
            value=5_000,
            step=1_000,
            key="income_dividend",
        )

    source_row_two = st.columns(4, gap="large", vertical_alignment="bottom")
    with source_row_two[0]:
        retirement_income = st.number_input(
            INCOME_COMPONENT_LABELS["incretir"].capitalize(),
            min_value=0,
            value=0,
            step=1_000,
            key="income_retirement",
        )
    with source_row_two[1]:
        social_security_income = st.number_input(
            INCOME_COMPONENT_LABELS["incss"].capitalize(),
            min_value=0,
            value=0,
            step=1_000,
            key="income_social_security",
        )
    with source_row_two[2]:
        rent_income = st.number_input(
            INCOME_COMPONENT_LABELS["incrent"].capitalize(),
            min_value=-500_000,
            value=0,
            step=1_000,
            help="A rental loss belongs here as a negative amount.",
            key="income_rent",
        )
    with source_row_two[3]:
        st.caption(
            "These amounts do not have to add up exactly to the return total. "
            "Losses and income outside these groups can leave a difference."
        )

    space(BLOCK_GAP)
    st.html(
        page_style.form_group(
            theme_type(),
            "The household",
            "Use the household as it stood during the year represented above.",
        )
    )
    household_fields = st.columns(5, gap="large", vertical_alignment="bottom")
    with household_fields[0]:
        age = st.number_input(
            "Age",
            min_value=mi.AGE_RANGE[0],
            max_value=mi.AGE_RANGE[1],
            value=42,
            key="age",
        )
    with household_fields[1]:
        children = st.number_input(
            "Own children at home",
            min_value=0,
            max_value=mi.NCHILD_MAX,
            value=0,
            key="children",
        )

    under_five_max = min(mi.NCHLT5_MAX, int(children))
    if "under_five" not in st.session_state:
        st.session_state["under_five"] = 0
    elif st.session_state["under_five"] > under_five_max:
        st.session_state["under_five"] = under_five_max
    with household_fields[2]:
        under_five = st.number_input(
            "How many are under five",
            min_value=0,
            max_value=under_five_max,
            disabled=children == 0,
            key="under_five",
        )

    household_floor = int(children) + 1 + (1 if married else 0)
    household_minimum = max(mi.FAMSIZE_RANGE[0], household_floor)
    if "household_size" not in st.session_state:
        st.session_state["household_size"] = household_minimum
    elif st.session_state["household_size"] < household_minimum:
        st.session_state["household_size"] = household_minimum
    with household_fields[3]:
        household_size = st.number_input(
            "People in the household",
            min_value=household_minimum,
            max_value=mi.FAMSIZE_RANGE[1],
            key="household_size",
        )

    states_by_name = sorted(mi.STATEFIP_LEVELS, key=lambda code: STATE_NAMES[code])
    with household_fields[4]:
        state = st.selectbox(
            "State",
            options=states_by_name,
            index=states_by_name.index(36),
            format_func=lambda code: STATE_NAMES[code],
            help="Federal tax is the same everywhere; this is included for context.",
            key="state",
        )

    space(BLOCK_GAP)
    if st.button("Show the rate", type="primary", width="stretch"):
        st.session_state["asked"] = True

filer = {
    "unit_inctot": float(total_income),
    "spouse_income": float(spouse_income),
    "incwage": float(wage_income),
    "incbus": float(business_income),
    "incint": float(interest_income),
    "incdivid": float(dividend_income),
    "incretir": float(retirement_income),
    "incss": float(social_security_income),
    "incrent": float(rent_income),
    "age": int(age),
    "nchild": int(children),
    "nchlt5": int(under_five),
    "famsize": int(household_size),
    "filing_status": int(filing_status),
    "marst": int(marital_status),
    "statefip": int(state),
}

st.html(page_style.reading_key(theme_type()))


# ===========================================================================
# What crosses the boundary to the two components
# ===========================================================================
# Everything below is display-shaped by the time it leaves this file: finished
# English, numbers already rounded to the precision they will be read at, lists
# already sorted, filtered and cut to length. Nothing internal travels — no
# codes, no identifiers, no raw values a component would have to interpret.


def shared_attributes(filer: dict, change: str) -> list[dict]:
    """The facts held constant, in display order, as finished English.

    This list is the whole argument of chapter four. Two dots on a chart show
    that two numbers differ; only the printed sameness shows that everything
    else was held still, which is the premise the comparison rests on.

    Whatever the comparison moves is left out, because listing it as unchanged
    would be false on its face.
    """
    values = {
        "income": f"roughly {money(filer['unit_inctot'])} a year",
        "source": dominant_income_phrase(filer),
        "age": age_phrase(filer["age"]),
        "children": children_phrase(filer["nchild"], filer["nchlt5"]),
        "household": household_phrase(filer["famsize"]),
        "marital": MARST_LABELS[filer["marst"]],
        "filing": FILESTAT_LABELS[filer["filing_status"]],
        "state": STATE_NAMES[filer["statefip"]],
    }
    moved = set(SHARED_ATTRIBUTES_MOVED_BY[change])
    return [
        {"label": SHARED_ATTRIBUTE_LABELS[name], "value": values[name]}
        for name in SHARED_ATTRIBUTE_ORDER
        if name not in moved
    ]


def twin_props(filer: dict, change: str) -> dict:
    """Everything the twin comparison needs, already written and rounded."""
    base_rate, twin_rate, gap = twin_for(_key(filer), change)
    from_label, to_label = twin_labels_for(_key(filer), change)
    displayed_base = round(base_rate, 1)
    displayed_twin = round(twin_rate, 1)
    # The printed gap must be the arithmetic a reader can do from the two
    # printed rates, even when their unrounded values straddle rounding bins.
    gap_points = round(displayed_twin - displayed_base, 1)

    # Money is only translated when it would not mislead. A gap that rounds to
    # nothing translates to a dollar figure that is pure noise, and an income
    # too small to take a share of translates to nothing meaningful at all.
    gap_money = None
    if (
        abs(gap_points) >= 0.1
        and float(filer["unit_inctot"]) >= mi.INCTOT_SHARE_FLOOR
    ):
        annual = abs(gap) / 100 * float(filer["unit_inctot"])
        gap_money = f"About {money(annual)} a year at this income."

    return {
        "changed": TWIN_FLIP_LABELS[change],
        "a": {
            "label": from_label,
            "rate": displayed_base,
            "display": charts.fmt_rate(base_rate),
        },
        "b": {
            "label": to_label,
            "rate": displayed_twin,
            "display": charts.fmt_rate(twin_rate),
        },
        "shared": shared_attributes(filer, change),
        "gapPoints": gap_points,
        "gapMoney": gap_money,
        "isPlaceholder": mi.MODEL_IS_STUB,
    }


def reason_props(explanation) -> dict:
    """The ranked reasons, already English, ranked, cut and rounded.

    Anything too small to matter, and anything past the fifth, is added into
    one closing figure rather than dropped — a list that quietly loses part of
    its own total is worse than a longer list.
    """
    kept: list[tuple[str, float]] = []
    rest = 0.0
    for name, value, given in zip(
        explanation.feature_names, explanation.values, explanation.data
    ):
        words = phrase_for(name, given)
        if words and abs(value) >= MIN_REASON:
            kept.append((words, float(value)))
        else:
            rest += float(value)

    kept.sort(key=lambda pair: abs(pair[1]), reverse=True)
    if len(kept) > MAX_REASONS:
        rest += sum(value for _, value in kept[MAX_REASONS:])
        kept = kept[:MAX_REASONS]

    remainder = round(rest, 1)
    return {
        "baseline": round(explanation.base_values, 1),
        "predicted": round(explanation.predicted, 1),
        "reasons": [{"text": words, "points": round(value, 1)} for words, value in kept],
        "remainder": remainder if remainder != 0.0 else None,
        "nothingStandsOut": not kept,
        "isPlaceholder": mi.MODEL_IS_STUB,
    }


# ===========================================================================
# The four result chapters
# ===========================================================================


def chapter(number: str, title: str) -> None:
    """Open one scroll chapter with the design system's full 96 px rhythm."""
    st.html(page_style.section_heading(theme_type(), number, title.capitalize()))


def opening() -> None:
    """Before anything has been asked for. Never a blank page."""
    st.markdown(
        "Describe a return above, then choose **Show the "
        "rate**. You will get what they pay, where that sits among everyone "
        "else, what moved it, and what happens when one thing about them "
        "changes."
    )
    space(FIGURE_GAP)
    st.caption(FRAMING)


# ---------------------------------------------------------------------------
# 01 — what they pay
# ---------------------------------------------------------------------------


def chapter_one(rate: float) -> None:
    chapter("01", "what they pay")
    figure, reading = st.columns(2, gap="large", vertical_alignment="center")
    with figure:
        st.altair_chart(
            charts.headline_number(rate, theme_type()), theme=None, width="stretch"
        )
    with reading:
        if rate >= 0:
            st.markdown(
                f"A filer like this pays about **{abs(rate):.1f} percent** of "
                "their income in federal income tax."
            )
        else:
            st.markdown(
                f"A filer like this ends the year **{abs(rate):.1f} percent of "
                "their income ahead** — they get back more than they pay in."
            )
            space(BLOCK_GAP)
            st.markdown(
                "A rate below zero is not a mistake and not an edge case. "
                "Credits meant to support low-paid work and children can come "
                "to more than the tax owed, and the difference is paid out. "
                f"About {round(mi.SHARE_NEGATIVE * 100)} in every hundred "
                "predicted rates fall below zero."
            )

        space(FIGURE_GAP)
        st.caption(FRAMING)


# ---------------------------------------------------------------------------
# 02 — where it sits
# ---------------------------------------------------------------------------


def chapter_two(rate: float) -> None:
    chapter("02", "where it sits")
    figure, reading = st.columns(2, gap="large", vertical_alignment="center")
    with figure:
        st.altair_chart(
            charts.distribution(rate, theme_type()), theme=None, width="stretch"
        )
    with reading:
        below = round(standing_for(rate))
        zero_share = mi.SHARE_EXACTLY_ZERO * 100
        zero_words = (
            "fewer than one in every 100"
            if zero_share < 0.5
            else f"about {round(zero_share)} in every 100"
        )
        if below >= 99:
            st.markdown(
                "Out of every 100 filers, fewer than one pays a larger share of "
                "their income than this."
            )
        elif below <= 1:
            st.markdown(
                "Out of every 100 filers, fewer than one pays a smaller share "
                "of their income than this."
            )
        else:
            st.markdown(
                f"Out of every 100 filers, about **{below}** pay a smaller "
                f"share of their income than this, and about **{100 - below}** "
                "pay more."
            )

        space(FIGURE_GAP)
        st.caption(
            "The shape behind the line is the whole country. The column "
            "standing on its own is the filers who owe precisely nothing — "
            f"{zero_words}. Everyone in the shaded band to its left, about "
            f"{mi.SHARE_NEGATIVE * 100:.0f} in every 100, got back more than "
            "they paid."
        )


# ---------------------------------------------------------------------------
# 03 — what moved it
# ---------------------------------------------------------------------------


def reasons_in_words(props: dict) -> None:
    """What chapter three says when the picture cannot be drawn.

    Not a placeholder and not an apology: the same ranking, the same wording
    and the same figures, set as a list instead of as bars. A reader who only
    ever sees this has not been told less.
    """
    if props["nothingStandsOut"]:
        return  # the calm sentence above has already said everything there is

    st.markdown(
        f"A typical filer pays about **{charts.fmt_rate(props['baseline'])}** of "
        "their income. This one comes out at "
        f"**{charts.fmt_rate(props['predicted'])}**. These are the things that "
        "made the difference, largest first."
    )

    up = [r for r in props["reasons"] if r["points"] > 0]
    down = [r for r in props["reasons"] if r["points"] < 0]

    if up:
        space(BLOCK_GAP)
        st.markdown("**Pushed the rate up**")
        st.markdown(
            "\n".join(
                f"- {r['text']} — {abs(r['points']):.1f} points up" for r in up
            )
        )
    if down:
        space(BLOCK_GAP)
        st.markdown("**Pushed the rate down**")
        st.markdown(
            "\n".join(
                f"- {r['text']} — {abs(r['points']):.1f} points down" for r in down
            )
        )

    if props["remainder"] is not None:
        direction = "up" if props["remainder"] > 0 else "down"
        space(FIGURE_GAP)
        st.caption(
            "Everything else together moved it "
            f"{abs(props['remainder']):.1f} points {direction}."
        )


def chapter_three(explanation) -> None:
    chapter("03", "what moved it")
    props = reason_props(explanation)
    reading, figure = st.columns(2, gap="large", vertical_alignment="top")

    with reading:
        if props["nothingStandsOut"]:
            st.markdown(
                "Nothing about this filer stands out. Their rate is close to "
                "what the typical filer pays, and no single thing moved it far."
            )
        else:
            count = len(props["reasons"])
            verb = "accounts" if count == 1 else "account"
            st.markdown(
                f"{in_words(count).capitalize()} "
                f"{'thing' if count == 1 else 'things'} {verb} for most of the "
                "distance between this filer and a typical one, and the largest "
                f"of them is {props['reasons'][0]['text']}."
            )

    with figure:
        if not viz.render(
            "contribution", mode=theme_type(), key="reasons", **props
        ):
            reasons_in_words(props)

        if not props["nothingStandsOut"]:
            space(FIGURE_GAP)
            st.caption(
                "Each figure is how far one thing moved the rate, starting "
                f"from the {charts.fmt_rate(props['baseline'])} of income a "
                "typical filer pays. They are listed one at a time for "
                "readability; in reality they lean on each other, which is why "
                "the list closes with everything that is left."
            )


# ---------------------------------------------------------------------------
# 04 — the same filer, one thing changed
# ---------------------------------------------------------------------------


def twin_in_words(props: dict) -> None:
    """What chapter four says when the picture cannot be drawn.

    The two rates, the distance between them, and the printed sameness — which
    is the part that actually carries the argument, and the part a fallback
    most easily loses.
    """
    a, b = props["a"], props["b"]
    gap = props["gapPoints"]

    if abs(gap) < 0.1:
        st.markdown(
            f"Either way — {a['label']} or {b['label']} — the rate is "
            f"essentially the same, at about **{a['display']}** of income. "
            "Changing this one thing does not move it."
        )
    else:
        direction = "more" if gap > 0 else "less"
        st.markdown(
            f"As they are — {a['label']} — the rate is **{a['display']}** of "
            f"income. Change nothing but {props['changed']}, to {b['label']}, "
            f"and it is **{b['display']}**: **{abs(gap):.1f} points "
            f"{direction}**."
        )
        if (a["rate"] < 0) != (b["rate"] < 0):
            space(FIGURE_GAP)
            st.markdown(
                "The two sit on opposite sides of zero. One pays tax; the other "
                "is paid. That is a different claim from one paying more than "
                "the other, and it is worth saying out loud."
            )

    space(BLOCK_GAP)
    held = "; ".join(
        f"{item['label'].lower()}, {item['value']}" for item in props["shared"]
    )
    st.caption(escape_dollars(f"Held exactly the same on both sides: {held}."))

    if props["gapMoney"] is not None:
        space(FIGURE_GAP)
        st.caption(
            f"{escape_dollars(props['gapMoney'])} The same money, treated "
            "differently."
        )


def chapter_four(filer: dict) -> None:
    chapter("04", "the same filer, one thing changed")
    reading, figure = st.columns(2, gap="large", vertical_alignment="top")

    def question_for(change: str) -> str:
        if (
            change == "marital_status"
            and int(filer["marst"]) == mi.MARRIED_SPOUSE_PRESENT
        ):
            return "What if they were not married?"
        if change == "dependents" and int(filer["nchild"]) > 0:
            return "What if there were no children at home?"
        return TWIN_FLIP_QUESTIONS[change]

    with reading:
        st.markdown(
            "Everything about this filer stays exactly as it is except one "
            "thing. The distance between the two is what that one thing is "
            "worth. This is one comparison, not a finding about the country."
        )
        space(FIGURE_GAP)
        # Only comparisons that can actually be drawn for this filer are
        # offered. A filer whose income is entirely their spouse's has no own
        # source to recompose, and a menu entry that answers with an apology is
        # worse than one that was never there.
        choices = mi.available_flips(filer)
        change = st.selectbox(
            "Change one thing",
            options=choices,
            format_func=question_for,
            key="change_one_thing",
            label_visibility="collapsed",
        ) if choices else None

    with figure:
        if change is None:
            st.markdown(
                "There is nothing to hold constant and change for this filer."
            )
        else:
            props = twin_props(filer, change)
            if not viz.render("twin", mode=theme_type(), key="twin", **props):
                twin_in_words(props)


# ---------------------------------------------------------------------------


def results(filer: dict) -> None:
    try:
        rate = rate_for(_key(filer))
        explanation = reasons_for(_key(filer))
        chapter_one(rate)
        chapter_two(rate)
        chapter_three(explanation)
        chapter_four(filer)
    except mi.ModelArtifactUnavailable:
        space(CHAPTER_GAP)
        st.html(
            page_style.notice(
                theme_type(),
                "The analysis is not available in this copy.",
                (
                    "The trained predictor has not been supplied to the app. "
                    "The experience is ready, but it cannot produce rates until "
                    "the project team adds the matching trained model."
                ),
            )
        )
    except mi.ModelContractError:
        space(CHAPTER_GAP)
        st.html(
            page_style.notice(
                theme_type(),
                "The analysis was stopped.",
                (
                    "The trained predictor and its expected data do not match. "
                    "No estimate is shown because a mismatched estimate could "
                    "look convincing while being wrong."
                ),
            )
        )
    except ValueError:
        space(CHAPTER_GAP)
        st.html(
            page_style.notice(
                theme_type(),
                "This return falls outside the comparison.",
                (
                    "Those details do not describe an ordinary combination in "
                    "the survey, so there is no responsible estimate to show. "
                    "Adjust the return above and try again."
                ),
            )
        )


if st.session_state.get("asked"):
    results(filer)
else:
    opening()


# ===========================================================================
# Method and scope
# ===========================================================================

st.html(
    page_style.section_heading(
        theme_type(),
        "Method",
        "What this does — and does not — claim",
        anchor="method",
    )
)
source, validation, appearance = st.columns(3, gap="large", vertical_alignment="top")
with source:
    st.caption(
        "**Where this comes from** — a United States Census survey of 61,231 "
        "tax filers, covering money earned in 2023. Rate means federal income "
        "tax, after credits, as a share of the income counted for tax. It does "
        "not include payroll tax, state tax or sales tax."
    )
    if mi.MODEL_IS_STUB:
        st.caption(
            "**What is still missing** — every figure above is a placeholder "
            "while the part of this project that learns from the survey is "
            "built. When that is finished, this note disappears on its own."
        )
with validation:
    st.caption(
        "**How it will be checked** — against the tax figures the Internal "
        "Revenue Service publishes for 2023, income band by income band. The "
        "survey and the tax authority are separate sources, and no number on "
        "this page ever mixes the two."
    )
with appearance:
    st.caption(
        "**Appearance** — this page opens dark. There is a fully authored "
        "light version in the menu at the top right of the window. After "
        "choosing Light or Dark there, choose Rerun in the same menu so the "
        "charts and comparison panels receive the new palette too."
    )

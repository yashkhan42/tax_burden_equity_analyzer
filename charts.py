"""The two things Altair still draws, and the type rules they follow.

Two of the four pictures this page once drew have moved to React — the ranked
reasons and the twin comparison. What is left is what Altair genuinely does
better than a component: one enormous numeral, and one static distribution.

Colour is not authored here. `design/tokens.json` is the single source of
truth for every hex value and both font stacks; this module reads it and
nothing else. A colour written into this file that disagrees with that one is
a defect, so none are written here.

Type rules, applied in both charts:

* **Figures are monospace.** Every numeral a reader might set against another
  numeral uses the mono stack, which gives fixed-width digits, so 8.6 and 11.2
  align on the decimal instead of drifting. Words stay in the sans.
* **One accent per chart, spent on the reader.** Their rate, their marker.
  Everything else is the neutral `shape` and `muted` roles.
* **Direction never rests on colour.** Which side of zero a mark sits on, and
  the words printed beside it, carry the direction first.
* **The count axis is dropped.** "How many filers" in absolute numbers is not
  a question anyone asked; the silhouette answers the one they did ask.

Two Altair 6 traps are avoided here deliberately, both having cost a day
already:

1. In a layered chart, ``axis=None`` on one layer's x encoding suppresses the
   shared x axis for *every* layer. Secondary layers therefore inherit the
   axis by simply not mentioning it.
2. ``alt.X(...).scale`` cannot be read back off an `alt.X` object. Every scale
   is hoisted into a variable first and that variable is reused.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

import altair as alt
import pandas as pd

import model_interface as mi

_TOKENS_PATH = Path(__file__).parent / "design" / "tokens.json"


@lru_cache(maxsize=1)
def tokens() -> dict:
    """The design tokens, read once per process."""
    return json.loads(_TOKENS_PATH.read_text())


def palette(theme_type: str | None) -> dict[str, str]:
    """The eight colour roles for the reader's current mode.

    Dark is the default because the page is: a reader who has never opened the
    appearance menu is in dark mode, and an unknown mode is treated as that
    rather than as an error.
    """
    t = tokens()
    return t.get(theme_type or "dark", t["dark"])


def mono() -> str:
    return tokens()["fontMono"]


def sans() -> str:
    return tokens()["fontSans"]


def fmt_rate(rate: float, decimals: int = 1) -> str:
    """A rate as a reader sees it: one decimal, typographic minus, per cent.

    The minus is U+2212, not a hyphen — it is the width of a digit, so a
    column of rates stays aligned whether or not any of them is negative.
    """
    return f"{'−' if rate < 0 else ''}{abs(rate):.{decimals}f}%"


def _style(chart: alt.LayerChart, p: dict[str, str]) -> alt.LayerChart:
    """Shared furniture: transparent ground, hairline axes, mono figures."""
    return (
        chart.configure(background="transparent")
        .configure_view(stroke=None)
        .configure_axis(
            labelFont=mono(),
            labelFontSize=12,
            labelColor=p["muted"],
            titleFont=sans(),
            titleFontSize=12,
            titleColor=p["muted"],
            titleFontWeight="normal",
            domainColor=p["hairline"],
            tickColor=p["hairline"],
            gridColor=p["hairline"],
            labelFlush=False,
        )
    )


# ---------------------------------------------------------------------------
# 1. The headline number
# ---------------------------------------------------------------------------


def headline_number(rate: float, theme_type: str | None) -> alt.Chart:
    """The rate, set at the one display size on the page.

    Drawn rather than written because Streamlit's text elements cannot be given
    a monospace face at display size without injecting CSS, and no CSS is
    injected in this project. The same number is repeated as ordinary prose
    immediately beneath, so this is never the only copy of it — a screen reader
    gets the sentence.

    Negative rates are set identically: same face, same weight, same colour. A
    minus sign, and nothing else, marks the difference. Styling a negative rate
    as a warning would misrepresent a legitimate outcome for one filer in
    eight.
    """
    p = palette(theme_type)
    text = (
        alt.Chart(pd.DataFrame({"v": [fmt_rate(rate)]}))
        .mark_text(
            font=mono(),
            fontSize=72,
            fontWeight=400,
            color=p["ink"],
            align="left",
            baseline="middle",
            x=2,
            y=48,
        )
        .encode(text="v:N")
    )
    return (
        text.properties(height=96, width="container")
        .configure(background="transparent")
        .configure_view(stroke=None)
    )


# ---------------------------------------------------------------------------
# 2. Where that sits among everyone else
# ---------------------------------------------------------------------------

#: Half-width, in rate points, of the column standing for "exactly nothing".
#: It is a point mass, not an interval, so its width is a drawing decision
#: rather than a measurement — narrow enough to read as a single value.
_ZERO_HALF = 0.6

#: Clear space on each side of that column. This is the whole reason the
#: chapter works: about one filer in twelve owes precisely nothing, and merging
#: that spike into the bin beside it hides a real finding inside an ordinary
#: bar. The gap is what makes it a separate fact rather than a tall bar.
_ZERO_GAP = 0.35

_ZERO_EDGE = _ZERO_HALF + _ZERO_GAP


def _histogram_rows() -> tuple[list[dict], float]:
    """The fixed bins, with the exact-zero mass carved out of its own bin.

    `RATE_DISTRIBUTION` bins on 2.5 points, so the bin starting at zero holds
    both the filers who owe precisely nothing and the filers who owe a little.
    Those are different facts, so the share that owes precisely nothing is
    lifted out into its own column and the remainder of that bin is drawn
    beside it, shortened by exactly what was removed. No filer is counted
    twice and none is lost.

    The bin ending at zero is pulled back to leave clear space on the left of
    the column. It holds only negative rates, so nothing is misplaced by it.
    """
    width = mi.DISTRIBUTION_BIN_WIDTH
    rows: list[dict] = []
    for start, share in mi.RATE_DISTRIBUTION:
        end = start + width
        if start == 0.0:
            rows.append(
                {"x": _ZERO_EDGE, "x2": end, "share": share - mi.SHARE_EXACTLY_ZERO}
            )
        elif end == 0.0:
            rows.append({"x": start, "x2": -_ZERO_EDGE, "share": share})
        else:
            rows.append({"x": start, "x2": end, "share": share})
    tallest = max(max(r["share"] for r in rows), mi.SHARE_EXACTLY_ZERO)
    return rows, tallest


def distribution(rate: float, theme_type: str | None) -> alt.LayerChart:
    """The whole country as a shape, with one line for the reader.

    Deliberately not a bell and deliberately not a smoothed density. The real
    distribution has a long negative tail, a hard spike at exactly nothing, and
    a short right tail; a smoother renders the spike as a bump with width,
    which is a lie about a point mass. Fixed bins are the honest primitive.

    Three things are drawn that a plain histogram would not have:

    * the exact-zero column, standing clear of its neighbours on both sides;
    * the negative region, shaded and named in words, because "below zero"
      means something specific here and the shape alone will not say it;
    * one accent rule for the reader, which is the only chromatic mark.

    Degradation, all three cases handled rather than hoped for: a very high
    rate flips its label inward so it cannot be clipped at the right edge; a
    negative rate lands inside the shaded region, which is exactly where the
    explanation for it already sits; a rate at or near zero would collide with
    the exact-zero column, so its rule is drawn starting above that column
    instead of through it.
    """
    p = palette(theme_type)
    rows, tallest = _histogram_rows()
    headroom = tallest * 1.35

    x_scale = alt.Scale(domain=[-52.0, 36.0], nice=False)
    y_scale = alt.Scale(domain=[0.0, headroom], nice=False)

    x = alt.X(
        "x:Q",
        scale=x_scale,
        axis=alt.Axis(
            title="percent of income paid in federal income tax",
            values=[-50, -25, 0, 10, 20, 30],
            format="d",
            titlePadding=12,
            grid=False,
        ),
    )
    # Every secondary layer inherits this. It must never be given axis=None:
    # in a layered chart that suppresses the shared x axis for all layers.
    x_plain = alt.X("x:Q", scale=x_scale)
    y = alt.Y("y:Q", scale=y_scale, axis=None)

    # Every vertical extent is carried as a real column rather than as a bare
    # datum. A datum-only y encoding gives that layer no scale of its own, and
    # in a layered chart the merge of a scaleless y against a scaled one is
    # where this drawing silently collapsed to nothing once already.
    def floors(frame: pd.DataFrame) -> pd.DataFrame:
        frame = frame.copy()
        frame["base"] = 0.0
        return frame

    # The negative region, named rather than merely coloured. `surface` is the
    # role for a block that is raised off the ground without meaning anything
    # on its own; the sentence printed on top of it is what carries the fact.
    region = (
        alt.Chart(
            pd.DataFrame(
                {"x": [-52.0], "x2": [-_ZERO_EDGE], "y": [headroom], "base": [0.0]}
            )
        )
        .mark_rect(color=p["surface"])
        .encode(x=x_plain, x2="x2:Q", y=y, y2="base:Q")
    )

    bars = (
        alt.Chart(floors(pd.DataFrame(rows).rename(columns={"share": "y"})))
        .mark_bar(color=p["shape"], stroke=None)
        .encode(x=x, x2="x2:Q", y=y, y2="base:Q")
    )

    zero_column = (
        alt.Chart(
            pd.DataFrame(
                {
                    "x": [-_ZERO_HALF],
                    "x2": [_ZERO_HALF],
                    "y": [mi.SHARE_EXACTLY_ZERO],
                    "base": [0.0],
                }
            )
        )
        .mark_bar(color=p["shape"], stroke=None)
        .encode(x=x_plain, x2="x2:Q", y=y, y2="base:Q")
    )

    def words(at: float, text: str, align: str, height: float) -> alt.Chart:
        return (
            alt.Chart(pd.DataFrame({"x": [at], "t": [text], "y": [height]}))
            .mark_text(
                font=sans(),
                fontSize=12,
                color=p["muted"],
                align=align,
                baseline="middle",
            )
            .encode(x=x_plain, y=y, text="t:N")
        )

    got_back = words(-51.0, "got more back than they paid", "left", tallest * 0.34)
    owed_nothing = words(
        -1.6, "owed exactly nothing", "right", mi.SHARE_EXACTLY_ZERO + tallest * 0.14
    )

    # A rate sitting on the exact-zero column would draw a rule straight down
    # the middle of it. Start the rule above the column instead, so both marks
    # stay readable and neither pretends to be the other.
    on_the_column = abs(rate) <= _ZERO_EDGE
    rule_bottom = mi.SHARE_EXACTLY_ZERO * 1.06 if on_the_column else 0.0
    marker = (
        alt.Chart(
            pd.DataFrame(
                {"x": [rate], "y": [headroom * 0.9], "base": [rule_bottom]}
            )
        )
        .mark_rule(color=p["accent"], strokeWidth=2.5)
        .encode(x=x_plain, y=y, y2="base:Q")
    )

    # Flipped inward at the right edge so an extreme rate cannot clip.
    anchor = "left" if rate < 18 else "right"
    label = (
        alt.Chart(pd.DataFrame({"x": [rate], "t": ["this filer"], "y": [headroom * 0.95]}))
        .mark_text(
            font=sans(),
            fontSize=12,
            color=p["accent"],
            align=anchor,
            dx=7 if anchor == "left" else -7,
            baseline="middle",
        )
        .encode(x=x_plain, y=y, text="t:N")
    )

    layered = alt.layer(
        region, bars, zero_column, got_back, owed_nothing, marker, label
    ).properties(height=210, width="container")
    return _style(layered, p)

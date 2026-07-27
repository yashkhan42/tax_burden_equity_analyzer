"""Website-scale presentation primitives for the Streamlit shell.

This module owns no application state and knows nothing about the model.  It
only turns the authoritative design tokens into small, self-contained pieces
of semantic HTML.  The HTML styles its own nodes; it never reaches into
Streamlit's private DOM, so a Streamlit upgrade cannot silently break the page
through a renamed internal selector.

Colour and type come from ``design/tokens.json``.  Type sizes, line heights and
space come from ``design/DESIGN_SYSTEM.md`` and use only its fixed scales.
"""

from __future__ import annotations

import html
import json
from functools import lru_cache
from pathlib import Path

_TOKENS_PATH = Path(__file__).parent / "design" / "tokens.json"

# DESIGN_SYSTEM.md §§2–3.  These are named here so page markup cannot drift
# into a parallel, improvised type or spacing scale.
SPACE = {"xs": 8, "sm": 16, "md": 24, "lg": 32, "xl": 48, "chapter": 96}
TYPE = {
    "page": (40, 1.15),
    "chapter": (28, 1.20),
    "lead": (18, 1.62),
    "body": (16, 1.50),
    "secondary": (14, 1.45),
    "label": (12, 1.33),
}


@lru_cache(maxsize=1)
def tokens() -> dict:
    """Read the one machine-readable source of visual values."""
    return json.loads(_TOKENS_PATH.read_text())


def palette(mode: str | None) -> dict[str, str]:
    """Return a complete authored palette; dark is the deliberate fallback."""
    values = tokens()
    return values["light"] if mode == "light" else values["dark"]


def _safe(value: str) -> str:
    return html.escape(value, quote=True)


def _font(value: str) -> str:
    """Quote a token-provided font stack for an inline style attribute."""
    return html.escape(value, quote=True)


def site_header(mode: str | None) -> str:
    """A compact site header with real in-page destinations."""
    t = tokens()
    p = palette(mode)
    return f"""
    <header style="
        display:flex;
        align-items:center;
        justify-content:space-between;
        gap:{SPACE['md']}px;
        padding:{SPACE['sm']}px 0;
        border-bottom:1px solid {p['hairline']};
        color:{p['ink']};
        font-family:{_font(t['fontSans'])};
        font-size:{TYPE['label'][0]}px;
        line-height:{TYPE['label'][1]};
        font-weight:400;
    ">
      <a href="#top" style="color:{p['ink']};text-decoration:none;">
        Tax burden equity analyzer
      </a>
      <nav aria-label="Page">
        <a href="#build-a-comparison" style="
            color:{p['muted']};
            text-decoration:none;
            margin-right:{SPACE['md']}px;
        ">Build a comparison</a>
        <a href="#how-to-read-this" style="
            color:{p['muted']};
            text-decoration:none;
            margin-right:{SPACE['md']}px;
        ">How to read this</a>
        <a href="#method" style="
            color:{p['muted']};
            text-decoration:none;
        ">Method</a>
      </nav>
    </header>
    """


def hero_copy(mode: str | None) -> str:
    """The argument, stated before the reader meets a control."""
    t = tokens()
    p = palette(mode)
    return f"""
    <section id="top" style="
        padding:{SPACE['chapter']}px 0 {SPACE['xl']}px;
        color:{p['ink']};
        font-family:{_font(t['fontSans'])};
    ">
      <div style="
          margin:0 0 {SPACE['sm']}px;
          color:{p['accent']};
          font-size:{TYPE['label'][0]}px;
          line-height:{TYPE['label'][1]};
      ">A public-interest machine learning project</div>
      <h1 style="
          max-width:60ch;
          margin:0;
          color:{p['ink']};
          font-family:{_font(t['fontSerif'])};
          font-size:{TYPE['page'][0]}px;
          line-height:{TYPE['page'][1]};
          font-weight:400;
      ">Two filers, same income, different tax</h1>
      <p style="
          max-width:60ch;
          margin:{SPACE['md']}px 0 0;
          color:{p['ink']};
          font-size:{TYPE['lead'][0]}px;
          line-height:{TYPE['lead'][1]};
          font-weight:400;
      ">Federal tax is not only about how much a household earns. See what
      changes when one fact changes and everything else stays fixed.</p>
      <p style="
          max-width:60ch;
          margin:{SPACE['lg']}px 0 0;
          color:{p['muted']};
          font-size:{TYPE['secondary'][0]}px;
          line-height:{TYPE['secondary'][1]};
      ">Describe a household, follow its predicted rate through the country,
      then meet its closest comparison.</p>
    </section>
    """


def hero_argument(mode: str | None) -> str:
    """A dense surface that makes the counterfactual premise visible."""
    t = tokens()
    p = palette(mode)
    rows = (
        ("Held fixed", "Income and every other fact"),
        ("Changed", "One household characteristic"),
        ("Compared", "The predicted federal tax rate"),
    )
    rendered = "".join(
        f"""
        <div style="
            display:grid;
            grid-template-columns:1fr 1fr;
            gap:{SPACE['md']}px;
            padding:{SPACE['sm']}px 0;
            border-top:1px solid {p['hairline']};
        ">
          <span style="color:{p['muted']};">{_safe(label)}</span>
          <span style="color:{p['ink']};">{_safe(value)}</span>
        </div>
        """
        for label, value in rows
    )
    return f"""
    <aside aria-label="The comparison" style="
        margin:{SPACE['chapter']}px 0 {SPACE['xl']}px;
        padding:{SPACE['lg']}px;
        border:1px solid {p['hairline']};
        border-radius:{t['radius']}px;
        background:{p['surface']};
        color:{p['ink']};
        font-family:{_font(t['fontSans'])};
        font-size:{TYPE['secondary'][0]}px;
        line-height:{TYPE['secondary'][1]};
    ">
      <div style="
          margin:0 0 {SPACE['md']}px;
          color:{p['muted']};
          font-size:{TYPE['label'][0]}px;
          line-height:{TYPE['label'][1]};
      ">The test</div>
      <p style="
          margin:0 0 {SPACE['lg']}px;
          color:{p['ink']};
          font-family:{_font(t['fontSerif'])};
          font-size:{TYPE['chapter'][0]}px;
          line-height:{TYPE['chapter'][1]};
      ">One return. One difference. One measurable distance.</p>
      {rendered}
    </aside>
    """


def section_heading(
    mode: str | None,
    marker: str,
    title: str,
    *,
    anchor: str | None = None,
    lead: str | None = None,
) -> str:
    """A chapter marker and title with the fixed 96/32 rhythm."""
    t = tokens()
    p = palette(mode)
    anchor_attr = f' id="{_safe(anchor)}"' if anchor else ""
    lead_html = (
        f"""
        <p style="
            max-width:60ch;
            margin:{SPACE['sm']}px 0 0;
            color:{p['muted']};
            font-size:{TYPE['secondary'][0]}px;
            line-height:{TYPE['secondary'][1]};
        ">{_safe(lead)}</p>
        """
        if lead
        else ""
    )
    return f"""
    <section{anchor_attr} style="
        padding:{SPACE['chapter']}px 0 {SPACE['lg']}px;
        border-top:1px solid {p['hairline']};
        color:{p['ink']};
        font-family:{_font(t['fontSans'])};
    ">
      <div style="
          margin:0 0 {SPACE['sm']}px;
          color:{p['muted']};
          font-size:{TYPE['label'][0]}px;
          line-height:{TYPE['label'][1]};
      ">{_safe(marker)}</div>
      <h2 style="
          max-width:60ch;
          margin:0;
          color:{p['ink']};
          font-family:{_font(t['fontSerif'])};
          font-size:{TYPE['chapter'][0]}px;
          line-height:{TYPE['chapter'][1]};
          font-weight:400;
      ">{_safe(title)}</h2>
      {lead_html}
    </section>
    """


def notice(mode: str | None, title: str, body: str) -> str:
    """A quiet project-status surface, never styled like an error."""
    t = tokens()
    p = palette(mode)
    return f"""
    <aside style="
        max-width:60ch;
        padding:{SPACE['md']}px;
        border:1px solid {p['hairline']};
        border-radius:{t['radius']}px;
        background:{p['surface']};
        color:{p['ink']};
        font-family:{_font(t['fontSans'])};
        font-size:{TYPE['secondary'][0]}px;
        line-height:{TYPE['secondary'][1]};
    ">
      <div style="margin:0 0 {SPACE['xs']}px;color:{p['ink']};">{_safe(title)}</div>
      <div style="color:{p['muted']};">{_safe(body)}</div>
    </aside>
    """


def form_group(mode: str | None, title: str, description: str) -> str:
    """Heading copy for one native Streamlit group inside the tool."""
    t = tokens()
    p = palette(mode)
    return f"""
    <div style="
        margin:0 0 {SPACE['md']}px;
        color:{p['ink']};
        font-family:{_font(t['fontSans'])};
    ">
      <h3 style="
          margin:0;
          color:{p['ink']};
          font-family:{_font(t['fontSans'])};
          font-size:{TYPE['body'][0]}px;
          line-height:{TYPE['body'][1]};
          font-weight:400;
      ">{_safe(title)}</h3>
      <p style="
          max-width:60ch;
          margin:{SPACE['xs']}px 0 0;
          color:{p['muted']};
          font-size:{TYPE['label'][0]}px;
          line-height:{TYPE['label'][1]};
      ">{_safe(description)}</p>
    </div>
    """


def reading_key(mode: str | None) -> str:
    """A short bridge from the tool to the four scroll chapters."""
    t = tokens()
    p = palette(mode)
    items = (
        ("01", "What they pay"),
        ("02", "Where it sits"),
        ("03", "What moved it"),
        ("04", "One thing changed"),
    )
    cells = "".join(
        f"""
        <div style="
            padding:{SPACE['sm']}px 0;
            border-top:1px solid {p['hairline']};
        ">
          <div style="
              color:{p['muted']};
              font-size:{TYPE['label'][0]}px;
              line-height:{TYPE['label'][1]};
          ">{number}</div>
          <div style="
              margin-top:{SPACE['xs']}px;
              color:{p['ink']};
              font-size:{TYPE['secondary'][0]}px;
              line-height:{TYPE['secondary'][1]};
          ">{_safe(label)}</div>
        </div>
        """
        for number, label in items
    )
    return f"""
    <section id="how-to-read-this" style="
        padding:{SPACE['xl']}px 0 0;
        color:{p['ink']};
        font-family:{_font(t['fontSans'])};
    ">
      <div style="
          display:grid;
          grid-template-columns:repeat(4, 1fr);
          gap:{SPACE['md']}px;
      ">{cells}</div>
    </section>
    """

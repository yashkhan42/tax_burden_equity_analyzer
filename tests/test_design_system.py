"""Guards on the things that silently drift.

Run with: python -m pytest tests -q   (or plain `python tests/test_design_system.py`)

Three classes of drift this catches:

1. The palette is written twice — once in design/tokens.json, which Python and
   React read, and once in .streamlit/config.toml, which only Streamlit reads
   and which cannot import JSON. If they disagree, the page and the pictures
   inside it are different colours and nobody notices until a screenshot.
2. A component ships without its production build, which deploys as a blank
   iframe on Community Cloud, where npm never runs.
3. The frozen modelling schema moves under us.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TOKENS = json.loads((ROOT / "design" / "tokens.json").read_text())
CONFIG = (ROOT / ".streamlit" / "config.toml").read_text()


def _config_section(name: str) -> dict[str, str]:
    """Read one [theme.<name>] block without a TOML dependency."""
    block = re.search(rf"^\[theme\.{name}\]$(.*?)(?=^\[|\Z)", CONFIG, re.M | re.S)
    assert block, f"[theme.{name}] missing from config.toml"
    return dict(re.findall(r'^(\w+)\s*=\s*"([^"]+)"', block.group(1), re.M))


def test_palettes_match_between_tokens_and_streamlit_config() -> None:
    """Every colour the shell paints must equal the colour the components get."""
    for mode in ("dark", "light"):
        config = _config_section(mode)
        tokens = TOKENS[mode]
        pairs = {
            "backgroundColor": "background",
            "secondaryBackgroundColor": "surface",
            "textColor": "ink",
            "primaryColor": "accent",
            "borderColor": "hairline",
        }
        for config_key, token_key in pairs.items():
            assert config[config_key].upper() == tokens[token_key].upper(), (
                f"{mode}: config.toml {config_key}={config[config_key]} but "
                f"tokens.json {token_key}={tokens[token_key]}"
            )


def test_both_modes_define_every_role() -> None:
    roles = {"background", "surface", "ink", "muted", "hairline", "shape", "accent", "raised"}
    for mode in ("dark", "light"):
        assert roles <= set(TOKENS[mode]), f"{mode} is missing {roles - set(TOKENS[mode])}"


def _luminance(hex_colour: str) -> float:
    """WCAG relative luminance."""
    r, g, b = (int(hex_colour[i : i + 2], 16) / 255 for i in (1, 3, 5))

    def channel(c: float) -> float:
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4

    r, g, b = channel(r), channel(g), channel(b)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast(a: str, b: str) -> float:
    la, lb = _luminance(a), _luminance(b)
    lighter, darker = max(la, lb), min(la, lb)
    return (lighter + 0.05) / (darker + 0.05)


def test_text_contrast_passes_in_both_modes() -> None:
    """Body ink at AA-large or better; supporting text and accents at AA."""
    for mode in ("dark", "light"):
        p = TOKENS[mode]
        assert contrast(p["ink"], p["background"]) >= 7.0, f"{mode}: ink too weak"
        assert contrast(p["muted"], p["background"]) >= 4.5, f"{mode}: muted text too weak"
        assert contrast(p["accent"], p["background"]) >= 4.5, f"{mode}: accent too weak"
        assert contrast(p["raised"], p["background"]) >= 4.5, f"{mode}: second hue too weak"


def test_the_two_direction_hues_are_distinguishable_without_colour() -> None:
    """Direction must survive greyscale, so the pair needs a lightness gap."""
    for mode in ("dark", "light"):
        p = TOKENS[mode]
        ratio = contrast(p["accent"], p["raised"])
        assert ratio >= 1.9, (
            f"{mode}: accent and raised are too close in lightness ({ratio:.2f}); "
            "a reader seeing them in greyscale could not tell them apart. DESIGN_SYSTEM.md section 4 derives 1.9 as the achievable ceiling."
        )


def test_every_declared_component_has_a_committed_build() -> None:
    components = ROOT / "components"
    if not components.is_dir():
        return
    for source in components.iterdir():
        if not (source / "package.json").is_file():
            continue
        index = source / "build" / "index.html"
        assert index.is_file(), (
            f"{source.name} has no committed build. Run `npm run build` in "
            f"components/{source.name} — Community Cloud never runs npm, so an "
            "unbuilt component deploys as a blank space."
        )


def test_frozen_schema_is_unchanged() -> None:
    manifest = json.loads((ROOT / "data" / "processed" / "freeze_manifest.json").read_text())
    import sys

    sys.path.insert(0, str(ROOT))
    import model_interface as mi

    assert list(mi.FEATURE_COLS) == manifest["feature_cols"]
    assert mi.INCTOT_SHARE_FLOOR == manifest["inctot_share_floor"]


if __name__ == "__main__":
    failures = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print(f"pass  {name}")
            except AssertionError as error:
                failures += 1
                print(f"FAIL  {name}\n      {error}")
    raise SystemExit(1 if failures else 0)

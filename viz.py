"""The bridge to the React visualisations.

Streamlit owns the page; React owns three pictures inside it. This module is
the only place that knows both exist. It does three jobs and no others:

* loads each component, from a committed production build in normal use or
  from a live dev server when ``TAX_VIZ_DEV=1``
* hands every component the full design token set and the reader's current
  mode, because a sandboxed iframe cannot see the host page's theme
* degrades: if a build is missing, the loader returns None and the caller
  draws the fallback instead of leaving a hole in the page

Nothing about the model comes through here. Callers pass display-shaped data —
finished English labels and rounded numbers — which is why these components can
be developed against JSON fixtures with no Python running.
"""

from __future__ import annotations

import json
import os
from functools import lru_cache
from pathlib import Path
from typing import Any, Callable

import streamlit.components.v1 as components

_ROOT = Path(__file__).parent
_TOKENS_PATH = _ROOT / "design" / "tokens.json"
_COMPONENTS = _ROOT / "components"

#: Set TAX_VIZ_DEV=1 to load components from their vite dev servers instead of
#: the committed builds, so edits hot-reload inside the running Streamlit page.
DEV_MODE = os.environ.get("TAX_VIZ_DEV") == "1"

#: Dev-server port per component. Fixed, not auto-assigned, so the Python side
#: and the npm scripts cannot disagree about where a component lives.
DEV_PORTS = {"twin": 5174, "contribution": 5175}


@lru_cache(maxsize=1)
def tokens() -> dict[str, Any]:
    """The design tokens, read once per process."""
    return json.loads(_TOKENS_PATH.read_text())


@lru_cache(maxsize=None)
def _load(name: str) -> Callable[..., Any] | None:
    """Declare a component, or return None if it cannot be served.

    Missing build directories are an expected state — a fresh checkout has not
    run ``npm run build`` yet — so this reports rather than raises, and the
    page falls back to a drawing Streamlit can do on its own.
    """
    if DEV_MODE:
        return components.declare_component(name, url=f"http://localhost:{DEV_PORTS[name]}")

    build = _COMPONENTS / name / "build"
    if not (build / "index.html").is_file():
        return None
    return components.declare_component(name, path=str(build))


def available(name: str) -> bool:
    """Whether this component can be rendered at all."""
    return _load(name) is not None


def render(name: str, *, mode: str, key: str, **props: Any) -> bool:
    """Render a component, returning False if it could not be loaded.

    `mode` and the token set are injected here rather than at each call site so
    no component can be written that ignores the light/dark toggle: theming is
    part of the transport, not something a caller remembers to pass.
    """
    component = _load(name)
    if component is None:
        return False
    component(mode=mode, tokens=tokens(), key=key, default=None, **props)
    return True

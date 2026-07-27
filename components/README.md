# The React visualisations

Streamlit owns the page. React owns three pictures inside it, and nothing else.

If you find yourself wanting to move the form, the navigation or the page
layout in here, stop — that is the signal the architecture is wrong, and it
should be raised rather than done incrementally.

## What lives where

```
components/<name>/
  src/            component source
  fixtures/*.json display-shaped sample payloads; the component renders from
                  these with no Python running at all
  build/          production build — COMMITTED, see "deployment" below
```

The Python side is `viz.py`: it declares each component, injects the design
tokens and the reader's mode, and returns `False` if a component cannot be
loaded so the page can draw a fallback instead of leaving a hole.

## Everyday development

Two terminals.

Terminal 1 — the component, with hot reload:

```bash
cd components/twin && npm run dev
```

Terminal 2 — Streamlit, pointed at the dev server instead of the build:

```bash
TAX_VIZ_DEV=1 streamlit run app.py
```

Ports are fixed per component (twin 5174, contribution 5175) and declared in
both `package.json` and `viz.py`, so the two sides cannot disagree about where
a component lives.

### Designing without Streamlit

`npm run dev` also serves the component standalone at
<http://localhost:5174>, rendering a fixture with a light/dark switch:

```
http://localhost:5174/?fixture=negative&mode=light
```

Fixtures cover the cases that break layouts: `default`, `negative` (refundable
credits exceed tax owed), `near-zero` (a flip that changes almost nothing), and
`extremes` (both ends of the observed range). A change that looks right on
`default` and wrong on `negative` is not finished.

## Deployment

Streamlit Community Cloud installs `requirements.txt` and runs `app.py`. It
never runs `npm`. So the production build is committed:

```bash
cd components/twin && npm run build   # writes components/twin/build/
git add -f components/twin/build      # .gitignore keeps node_modules out, not build
```

`tests/test_design_system.py` fails if any component source exists without a
committed build, which is the failure that would otherwise only show up as a
blank space on the deployed site.

## Two things that are easy to get wrong

**The iframe does not inherit the theme.** A component is sandboxed; the host's
CSS variables do not reach inside it. Both palettes and the current mode are
passed explicitly through `viz.render`, and every component picks its colours
from those props. A component that hard-codes a colour, or that ignores `mode`,
is broken in one of the two themes — that is a defect, not a limitation.

**The iframe does not size itself.** Report the real height with the
`useFrameHeight` hook in `src/frame.ts`, attached to the outermost element. It
reports after every render, on element resize, and once more when web fonts
settle. Content that is clipped, or an internal scrollbar, means the height is
not being reported.

### Why the protocol is hand-written

`streamlit-component-lib`'s `withStreamlitConnection` never completed its
handshake with Streamlit 1.60 and React 19 here: the component mounted, waited
for a render message that never arrived, and left a zero-height iframe with an
empty root. A hand-written protocol check confirmed the host side was fine, so
`src/frame.ts` speaks the three messages directly — `componentReady`,
`setFrameHeight`, `render`. It is about twenty lines, it removed a dependency,
and it halved the bundle. If a future Streamlit changes those message names,
this is the one file to change.

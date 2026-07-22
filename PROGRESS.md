# Tax burden equity analyzer — Phase 7 (the demo)

Progress and summary for the team. Covers what was built, why it is shaped the
way it is, what is verified, and what remains. Written for someone picking this
up cold.

---

## What this is

A Streamlit web page where a reader describes a tax filer and sees four things:
the filer's predicted effective federal tax rate, where that rate sits among
everyone else, what pushed it up or down, and — the point of the whole thing —
what happens to the rate when one fact about the filer changes and nothing else
does. That last one is the equity argument: two people, same income, different
rate, with the responsible attribute isolated.

This is **Phase 7** of the project's build sequence (README §9), built ahead of
the model so UI work does not block on modelling.

## Model state (important)

**There is no trained model yet.** A teammate is training the Random Forest
(Phase 3). Every rate, percentile, attribution and gap on the page is a
**deterministic placeholder** produced by `model_interface.py`, and the page
says so on screen. When the real model lands, wiring it in touches **one file**
(`model_interface.py`) and flips one flag; no other module changes.

---

## Architecture: a hybrid, and the boundary that defines it

Stock Streamlit could not carry the three visualisations at the quality the
argument needs. A full React frontend would throw away Streamlit's form,
session and deployment story. So: **Streamlit is the application shell; real
React (via Streamlit's custom-components API) draws the visualisations that
carry the argument, and nothing else.**

| Streamlit owns | React owns |
|---|---|
| form, session, page structure | the twin comparison |
| model calls (via `model_interface.py`) | the contribution chart |
| theming source of truth, deployment | *(percentile stayed Altair — see below)* |

The boundary is held deliberately. React never rebuilds the form, navigation or
layout. Everything crossing into a component is **display-shaped** — finished
English, rounded numbers, no column names — so each component renders from a
JSON fixture with no Python running.

---

## How the work was staged

**Stage 1 — research (three parallel investigations).**
- *lance.live teardown* — measured, not admired: two type scales with a 2× void
  between them, one ink alpha-stepped into five tiers, 92 px between chapters vs
  ≤48 px within, ~8% ink coverage per viewport, an accent budget of 448 px².
- *Bloomberg numeric authority* — bot-walled, so ~⅓ of it is honestly labelled
  recalled rather than verified. Yielded the number-setting rules: tabular
  figures, one precision per comparison, U+2212 minus, never abbreviate a
  headline figure, numbers never animate, encode direction twice.
- *Explanatory-visualisation research* — how NYT/FT/Pudding/OWID and regulated
  fields (credit scores, insurance, medical risk) explain outcomes to lay
  readers. Drove all three visualisation choices.

**Stage 2 — the design system (blocking; authored by hand).**
`design/DESIGN_SYSTEM.md` is authoritative: type scale, spacing scale, both
palettes, number-formatting rules, the chosen visualisation for each of the
three, and the component prop contracts. `design/tokens.json` is the
machine-readable colour/type source that Python, Altair and React all read.
Three reference conflicts were resolved here (see below).

**Stage 3 — parallel build against the frozen system.** Twin component,
contribution component, and the Streamlit shell + form + percentile chart.

**Stage 4 — integration (in progress).** Wiring, theme-propagation verification
across the iframe boundary in both modes, extreme-value testing, deploy check.

---

## The three design conflicts, resolved

1. **Density.** lance spends whitespace; Bloomberg packs a field. Resolved *by
   scope*: lance governs the page (chapter rhythm, one idea per moment),
   Bloomberg governs the inside of any block of figures (tight, aligned,
   tabular). lance itself shows the synthesis — its dense stats live in an
   inverted card inside the sparse page.
2. **The type void.** Kept, with all numbers on one side of it: exactly one
   figure is display-sized (the headline rate), every other number is ≤28 px and
   differentiated by weight, colour and position — never another size step.
3. **Motion.** Direct contradiction. Bloomberg wins: **numbers never animate.**
   A tax rate counting up performs a precision it does not have.

## One rule that could not be met, and why

Bloomberg's ≥3:1 lightness gap between the two direction hues is
**arithmetically impossible** here — proven, not hand-waved. On the dark ground,
AA legibility floors a colour at L ≥ 0.205, so a partner 3:1 lighter needs
L ≥ 0.716 (near-white, stops reading as a hue); on paper the mirror forces
near-black. The best achievable pair with both hues legible and neither
impersonating ink is **2.11:1 dark, 2.03:1 light**. The rule's *intent* — that
direction survive greyscale — is met three other ways, with hue as the weakest:
bar **position** relative to zero, explicit **sign and word**, then hue. A test
enforces ≥1.9 and verified greyscale-readability by rendering the components
desaturated.

---

## The three visualisations

| | Form | Why | Rejected |
|---|---|---|---|
| **Twin** (React) | two identical cards + a gap strip with a dumbbell whose *connector* is the heaviest mark | a chart of two dots can't show that everything else was held constant — the sameness is the premise, so it's drawn twice in grey | two big numbers side by side (emotionally inert); slope chart (reads as time) |
| **Contribution** (React) | ranked reason list with inline magnitude bars from a shared zero | the credit-report pattern readers already know, and what regulators mandate | SHAP waterfall (needs chart literacy, names features) |
| **Percentile** (**Altair**) | fixed-bin histogram, zero drawn as its own separated column, negative region shaded | no interaction, no state, no bespoke layout — Altair does it well and every extra iframe is a cost | a smoothed density (would render the 8.5% zero point-mass as a bump with width — a lie) |

The percentile staying Altair is a deliberate call the brief invited: custom
rendering is spent only where it earns its keep.

## Degradation is designed, not patched

Every component has a fixture for each hard case, each verified in both modes:
- **Negative rates are a finding, never an error.** ~12% of real filers have one
  (refundable credits exceed tax owed); styled identically to positives, only a
  U+2212 marks the difference. Verified end-to-end (a −7.1% filer renders clean).
- **Gap crossing zero** ("one pays, one is paid") draws the zero line explicitly.
- **Near-zero gap** trips a copy rule ("essentially the same rate") — never a
  two-pixel bar implying a difference that isn't there.
- **Extremes** (+33 vs −49) — labels never clip or collide.
- **"Nothing stands out"** — the contribution renders a calm sentence, not five
  indistinguishable stubs.

---

## Engineering the hybrid actually needs (all addressed)

- **Theme across the iframe.** Components are sandboxed; the host theme does not
  reach in. Both palettes and the current mode are passed explicitly through
  `viz.render`, injected in the transport so no component can forget to honour
  the toggle. Verified: twin iframe paints the dark token in dark and the light
  token in light. *(Known Streamlit lag: flipping the OS preference mid-session
  repaints host chrome instantly but the components update on the next rerun; a
  fresh load and the in-app Settings toggle are always correct.)*
- **Auto-height.** Iframes don't self-size. A `useFrameHeight` hook reports the
  real height after every render, on element resize, and once more when web
  fonts settle. No scrollbars, no clipping (measured 366 px / 887 px live).
- **The Streamlit React binding is bypassed on purpose.** `withStreamlitConnection`
  never completed its handshake under Streamlit 1.60 + React 19 (zero-height
  iframe, empty root). A vanilla protocol probe proved the host was fine, so
  `frame.ts` speaks the three messages directly — twenty lines, one fewer
  dependency, half the bundle. This is documented so a future Streamlit change
  has one file to touch.
- **Graceful degradation.** Three layers: prop validation, a React error
  boundary, and `viz.render()` returning `False` so Python draws a prose
  fallback. A malformed payload renders a legible sentence, never a blank box.
- **Deploy.** Community Cloud installs `requirements.txt` and never runs npm, so
  each component's production `build/` is committed. A test fails if any
  component source ships without its build.

---

## Guards against silent drift

`tests/test_design_system.py` — all passing — catches the things that rot
quietly: palette disagreement between `tokens.json` and `.streamlit/config.toml`,
a component shipped without its build, text contrast below AA in either mode,
the direction hues collapsing in greyscale, and the frozen modelling schema
moving underneath the app.

The schema itself is authoritative from the **frozen files**
(`train.csv` + `freeze_manifest.json`), never the README's prose — including the
income-share rule (shares zeroed when total income < 1000) and the corrected
`filestat` codes (the README mislabels joint filers as separated; the data and
IPUMS codebook agree they are joint).

---

## Current state

**Working and verified:**
- Full page renders end to end in both light and dark, no exceptions.
- Both React components render inside their iframes, correctly themed, auto-sized.
- No column names, module names or filenames anywhere on screen.
- Four sequenced chapters; form-first interaction (nothing computed until submit,
  then live updates so the twin's "what if" stays light).
- Negative rates, extremes and near-zero gaps all handled deliberately.
- All six design guards pass; props serialise to the fixed contract.

**Not yet done:**
- **Model wiring** — waiting on Phase 3. Stubs stay stubs; the boundary is ready.
- **Deploy-path check** — a fresh clone building only from committed artifacts
  (no npm) has not been run yet.
- **One small contract cleanup** — the twin needs the "changed" attribute in two
  forms (sentence fragment + card label); it currently bridges this in-component.
  A pre-written `changedLabel` field is the clean fix, deferred to avoid a merge
  clash during the parallel build.
- **Not started (out of scope for Phase 7):** the model itself (Phase 3), SHAP
  (4), the real twin engine (5), IRS SOI validation (6), stretch goals (§8).

---

## Running it

Everything runs from the repo root. Python env needs `requirements.txt`.

```bash
streamlit run app.py
```

Switch light/dark in Streamlit's own menu: **⋮ → Settings → Appearance**. Dark
is the default.

**Developing a component** (hot reload alongside Streamlit):

```bash
cd components/twin && npm run dev          # standalone on :5174
TAX_VIZ_DEV=1 streamlit run app.py         # points the page at the dev server
```

A component also renders standalone from any fixture with no Python:
`http://localhost:5174/?fixture=negative&mode=light`.

**Before deploying**, rebuild and commit each component's `build/`:

```bash
cd components/twin && npm run build && git add -f build
```

---

## Where things live

```
app.py                     the page: form, four chapters, fallbacks
charts.py                  the two Altair visuals (headline rate, percentile)
model_interface.py         THE model boundary — stubs now, one-file swap later
codebook.py                codes → plain English (nothing internal reaches screen)
viz.py                     the bridge to the React components (theme + height + fallback)
design/
  DESIGN_SYSTEM.md         authoritative: type, space, colour, numbers, viz choices, contracts
  tokens.json              machine-readable colour/type, read by Python + React
components/
  README.md                dev workflow, deploy, the two iframe gotchas
  twin/                     React: the twin comparison  (src/ + fixtures/ + committed build/)
  contribution/            React: the contribution chart (src/ + fixtures/ + committed build/)
tests/test_design_system.py  guards against palette/build/contrast/schema drift
.streamlit/config.toml     both theme palettes (mirrors tokens.json)
```

---

## The judgement calls worth knowing about

- **`filestat` codes** — the README mislabels two joint-filer codes as
  "separated"; the frozen data and IPUMS codebook agree they are joint filers
  split by age. The UI uses the correct labels. (This was the early catch that
  set the "trust the frozen files, not the prose" rule.)
- **Percentile stayed Altair** — stated plainly rather than built in React for
  symmetry. Custom rendering is spent only where it carries the argument.
- **The 3:1 hue rule was dropped with a proof**, not quietly. Direction is
  triple-encoded so hue is never load-bearing.
- **The Streamlit React binding was replaced**, not worked around, after a
  vanilla probe isolated the fault to the library.

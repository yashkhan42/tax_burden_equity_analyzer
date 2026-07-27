# Tax burden equity analyzer — Path C website and Streamlit fallback

Progress and summary for the team. Covers what was built, why it is shaped the
way it is, what is verified, and what remains. Written for someone picking this
up cold.

---

## Current application — Path C

**Updated 27 July 2026.** The primary experience is now a real Next.js website,
not the Streamlit page shell. FastAPI wraps the existing model boundary, and
the Streamlit hybrid remains available as a fallback.

```text
Next.js website ──HTTP──> FastAPI ──public calls──> model_interface.py
                                                ├── frozen train data
                                                ├── model metrics/checksum
Streamlit fallback ──────────────────────────────└── local model artifact
```

The boundary is strict:

- `frontend/` owns the semantic profile form, themes, motion, page sequencing,
  and the percentile, contribution, and twin visualisations.
- `backend/` validates reader-facing requests, calls the public operations in
  `model_interface.py`, and returns display-safe JSON. It does not reconstruct
  a model feature row or calculate a prediction itself.
- `model_interface.py` remains the sole authority for the 16-feature tax-unit
  order, dtypes and encodings, spouse-residual logic, artifact validation,
  prediction distribution, SHAP collapse/add-back, and twin interventions.
- `app.py` and the committed Streamlit component builds were not removed or
  rewritten.

### Website state

- Dark mode is the default; the light theme is equally tokenised.
- The cinematic hero, fixed navigation, full-width chapter surfaces, restrained
  scroll reveals, and dense numeric cards live in the Next.js shell.
- The form opens with four familiar input groups. “Add more detail” reveals the
  seven income sources, household fields, and conditional spouse income. When
  it stays closed, the complete tax-unit profile uses an explicit all-wage,
  no-children, smallest-valid-household default; those values still pass
  through the ordinary 16-feature construction without approximation.
- Result numbers use the site’s Source Sans Pro rather than terminal-style
  monospace figures. Precision, U+2212 minus signs, and matching decimal places
  within each comparison remain unchanged.
- The API exposes health, prediction, percentile, contribution, and twin
  operations. Model-unavailable responses are path-free `503` messages;
  invalid profiles are path-free `422` messages.
- The model artifact may be local or downloaded once at API startup. Downloads
  are streamed to a partial file, verified against the metrics SHA-256, and
  atomically promoted. Configure `TAX_MODEL_DOWNLOAD_URL` and optionally
  `TAX_MODEL_DOWNLOAD_TOKEN` or `GITHUB_TOKEN`.
- Production artifact delivery is **resolved for the Streamlit app**. One
  canonical build is published as the `model-v1` release asset, and its URL is
  recorded in `models/rf_metrics.json` under `final_model.distribution`, so a
  host needs no configuration. `model_interface` fetches it on first use when
  no artifact is on disk, under a lock so concurrent readers cause one
  download; `app.py` starts that fetch in the background as the page opens.
  Measured cold start: ~18 s to fetch and load, ~5 s to first answer, ~1.5 GB
  peak against Community Cloud's ~2.7 GB ceiling. `scripts/fetch_model.py`
  does the same fetch from a terminal.
- Because joblib output is not byte-reproducible across machines, a locally
  rebuilt artifact no longer fails to load: byte equality with the committed
  checksum is the fast path, and an artifact whose bytes differ is admitted
  only after it reproduces the logged test metrics, with a warning. Downloads
  are still strictly byte-verified before promotion.
- A production **backend** host for the FastAPI service is still outstanding.
  `bootstrap_artifact()` remains env-var driven there and is unchanged.

### Verification completed

- `34` Python tests pass, including the real boundary/schema guards and API
  error/response/artifact cases.
- Frontend type checking, linting, and a production Next.js build pass.
- Live-model checks cover ordinary, high-income, low-income, and negative-rate
  profiles. A tested low-income household returns `−47.9%` without clipping or
  error styling.
- Dark and light themes, desktop and mobile layouts, mobile navigation, form
  submission, all three visualisations, extreme markers, and negative twin
  results were exercised in a browser.
- The two legacy `components/*/build/` directories remain tracked and are not
  ignored, so the Streamlit fallback is still deployable.

### Current local runbook

Generate the ignored artifact only if `models/rf_eff_rate.joblib` is absent:

```bash
source .venv/bin/activate
MPLBACKEND=Agg jupyter nbconvert \
  --to notebook \
  --execute notebooks/train_random_forest.ipynb \
  --output train_random_forest.executed.ipynb \
  --output-dir /tmp \
  --ExecutePreprocessor.timeout=-1
```

Then run the API:

```bash
source .venv/bin/activate
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

Run the website from a second terminal:

```bash
cd frontend
npm ci
cp .env.example .env.local
npm run dev
```

Open `http://localhost:3000`. A working service shows
`{"status":"ready","model":"local"}` at `http://localhost:8000/healthz` and the
website replaces its invitation to analyse with four populated result
chapters. A broken artifact/API state leaves the site shell usable but displays
the service's unavailable message when the form is submitted.

---

## Streamlit fallback history

Everything below documents the Phase 7 hybrid as a retained fallback. It
explains decisions still embodied in the shared design tokens and model
boundary, but it is no longer the primary page architecture.

### What the fallback is

A Streamlit web page where a reader describes a tax filer and sees four things:
the filer's predicted effective federal tax rate, where that rate sits among
everyone else, what pushed it up or down, and — the point of the whole thing —
what happens to the rate when one fact about the filer changes and nothing else
does. That last one is the equity argument: two people, same income, different
rate, with the responsible attribute isolated.

This is **Phase 7** of the project's build sequence (README §9). The interface
was built ahead of the model and is now wired to the completed Phase 3 Random
Forest.

### Model state (important)

**The model is live; the artifact is local-only.** `model_interface.py` loads
and validates the trained Random Forest, predicts rates, recomputes the
reference distribution over the frozen training set, calculates empirical
percentiles, collapses 73 encoded SHAP values back to the 16 reader-facing
inputs, and runs the twin interventions. `MODEL_IS_STUB` is `False`.

The 275.7 MB artifact is `models/rf_eff_rate.joblib`. It is intentionally
ignored and must be regenerated from `notebooks/train_random_forest.ipynb`
before the app can return a result. The notebook verifies both frozen hashes,
fits the model, writes the artifact, updates its matching checksum in
`models/rf_metrics.json`, and redraws the Phase 3 residual diagnostic.

The application/model boundary remains real: `app.py` supplies reader-answerable
tax-unit values, and only `model_interface.py` imports modelling libraries,
loads model bytes, constructs the ordered feature row, or interprets encoded
outputs. The form changed because the authoritative model changed from the old
15-feature person contract to the 16-feature tax-unit contract; no other
presentation module knows the model schema.

---

### Architecture: a hybrid, and the boundary that defines it

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

**Stage 4 — integration (complete locally).** Live-model wiring, theme
verification across the iframe boundary in both modes, negative/extreme/
near-zero testing, conditional tax-unit form, and deploy-artifact checks.

**Website pass — complete within the honest Streamlit boundary.** The sidebar
is gone. A real hero, site navigation, integrated on-page form, asymmetric
result chapters and three-column method close now make the shell read as a
website rather than a centred document. True viewport-edge bands, sticky
scroll choreography, bespoke native widgets, an in-page host-theme switch and
removal of Streamlit chrome still require private-DOM injection or the full
React Path C; none is faked here.

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
| **Percentile** (**Altair**) | fixed-bin histogram, zero drawn as its own separated column, negative region shaded | no interaction, no state, no bespoke layout — Altair does it well and every extra iframe is a cost | a smoothed density (would give a point-mass false width) |

The percentile staying Altair is a deliberate call the brief invited: custom
rendering is spent only where it earns its keep.

## Degradation is designed, not patched

Every component has a fixture for each hard case, each verified in both modes:
- **Negative rates are a finding, never an error.** 11.4% of frozen observed
  outcomes are negative; 16.1% of the live model's frozen-training predictions
  fall below zero. The page labels the latter as predicted rates, styles them
  identically to positives, and uses only U+2212 to mark the sign. Verified
  end-to-end at the live prediction minimum (−48.6%).
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
  token in light. *(Known Streamlit lag: changing the host theme repaints its
  chrome immediately but custom HTML, charts and components receive the new
  mode only on the next script rerun. The page tells the reader to choose
  Rerun in the same menu.)*
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
(`train.csv` + `freeze_manifest.json`), never the README's prose. The locked
order is:

1. `unit_inctot` (`float64`)
2. `wage_share` (`float64`)
3. `business_share` (`float64`)
4. `interest_share` (`float64`)
5. `dividend_share` (`float64`)
6. `retirement_share` (`float64`)
7. `socsec_share` (`float64`)
8. `rent_share` (`float64`)
9. `spouse_income_share` (`float64`)
10. `age` (`int64`)
11. `nchild` (`int64`)
12. `nchlt5` (`int64`)
13. `famsize` (`int64`)
14. `filing_status` (`int64`, categorical levels 1/4/5)
15. `marst` (`int64`, categorical levels 1–6)
16. `statefip` (`int64`, the 51 frozen state levels)

The three categorical fields are one-hot encoded first, followed by the 13
numeric fields, for 73 encoded columns. All eight shares are zeroed when
whole-return income is below 1000. The form asks for whole-return income,
spouse income separately, and seven source amounts for the primary filer plus
claimed dependents excluding the spouse; `model_interface.py` alone derives
the eight shares.

---

## Current state

**Working and verified:**
- Full page renders end to end against the real artifact in both authored
  palettes, no exceptions.
- Both React components render inside their iframes, correctly themed, auto-sized.
- No column names, module names or filenames anywhere on screen.
- Website hero and navigation; integrated conditional tax-unit form; four
  sequenced result chapters.
- Form-first interaction: nothing computes until submit, then changing the
  profile or twin updates live.
- Exact 16-column order/dtypes, frozen hashes, artifact checksum, scikit-learn
  version, pipeline steps, category order and 73-column encoded output all
  validate before use.
- Live prediction, empirical percentile, SHAP add-back and all four twins pass.
- Negative rates, the −48.6/32.6 prediction extremes, a zero-crossing twin and
  a true zero-gap twin all preserve the deliberate copy and rendering rules.
- All six design guards and 20 tests pass; both production bundles rebuild and
  remain tracked and unignored.

**Still open:**
- **Production artifact delivery is blocked.** The trained file is 275.7 MB,
  is not in Git, and `models/*.joblib` is ignored. Choose one: Git LFS;
  download-at-startup from versioned object storage with checksum verification;
  or train and document a materially smaller artifact. Until then, a fresh
  deployment shows the designed unavailable state rather than a fake rate.
- **Fresh-clone deploy smoke test** after the artifact-delivery choice.
- **IRS SOI validation** (Phase 6) and the README stretch goals.
- **Streamlit ceiling:** viewport-edge bands, sticky scenes, bespoke widget
  internals, a one-click in-page theme control and chrome removal need private
  DOM hooks or the full React frontend. The current theme menu needs one manual
  Rerun after choosing Light or Dark so custom HTML/charts/iframes receive the
  new explicit palette.

---

## Running it

Everything runs from the repo root. Python 3.12+ is recommended.

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-dev.txt

# Regenerate the ignored 275.7 MB artifact and matching metadata.
MPLBACKEND=Agg jupyter nbconvert \
  --to notebook \
  --execute notebooks/train_random_forest.ipynb \
  --output /tmp/train_random_forest.executed.ipynb \
  --ExecutePreprocessor.timeout=-1

streamlit run app.py
```

The notebook reads only the authoritative frozen CSVs and manifest. It writes
`models/rf_eff_rate.joblib`, `models/rf_metrics.json`, and
`reports/figures/phase3_residual_diagnostics.png`. The app finds the default
artifact automatically. To use a matching artifact and metadata elsewhere:

```bash
TAX_MODEL_PATH=/absolute/path/to/rf_eff_rate.joblib \
TAX_MODEL_METRICS_PATH=/absolute/path/to/rf_metrics.json \
streamlit run app.py
```

Switch light/dark in Streamlit's top-right menu. Dark is the configured
default. After choosing Light or Dark, choose **Rerun** in the same menu so the
palette passed to custom HTML, Altair and both iframes updates too.

**Developing a component** (hot reload alongside Streamlit):

```bash
cd components/twin && npm run dev          # standalone on :5174
TAX_VIZ_DEV=1 streamlit run app.py         # points the page at the dev server
```

A component also renders standalone from any fixture with no Python:
`http://localhost:5174/?fixture=negative&mode=light`.

**Before deploying**, rebuild and commit each component's `build/` if its
source changed:

```bash
npm --prefix components/twin run build
npm --prefix components/contribution run build
```

---

## Where things live

```
app.py                     website shell, tax-unit form, four chapters, fallbacks
page_style.py              token-driven semantic HTML for website-scale sections
charts.py                  the two Altair visuals (headline rate, percentile)
model_interface.py         THE live model boundary — schema, load, predict, SHAP, twins
codebook.py                codes → plain English (nothing internal reaches screen)
viz.py                     the bridge to the React components (theme + height + fallback)
design/
  DESIGN_SYSTEM.md         authoritative: type, space, colour, numbers, viz choices, contracts
  tokens.json              machine-readable colour/type, read by Python + React
components/
  README.md                dev workflow, deploy, the two iframe gotchas
  twin/                     React: the twin comparison  (src/ + fixtures/ + committed build/)
  contribution/            React: the contribution chart (src/ + fixtures/ + committed build/)
tests/test_design_system.py guards against palette/build/contrast/schema drift
tests/test_model_interface.py  16-feature/twin/SHAP-collapse boundary tests
tests/test_codebook.py      truthfulness guards for reader-facing income language
.streamlit/config.toml     both theme palettes (mirrors tokens.json)
```

---

## The judgement calls worth knowing about

- **Filing-status codes** — the earlier person-level prose mislabelled joint
  filers. The current authoritative tax-unit freeze collapses filing status to
  1/4/5 and the UI derives exactly those ordinary combinations. This was the
  catch that set the "trust the frozen files, not the prose" rule.
- **Percentile stayed Altair** — stated plainly rather than built in React for
  symmetry. Custom rendering is spent only where it carries the argument.
- **The 3:1 hue rule was dropped with a proof**, not quietly. Direction is
  triple-encoded so hue is never load-bearing.
- **The Streamlit React binding was replaced**, not worked around, after a
  vanilla probe isolated the fault to the library.

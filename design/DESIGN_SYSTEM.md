# Design system

Authoritative. Stage 3 work consumes these values and does not invent its own.
If something here is wrong, change it here and let it propagate — a component
that hard-codes a number that disagrees with this file is a defect.

Machine-readable colour and type live in `design/tokens.json`, which Python,
Altair and the React components all read. `.streamlit/config.toml` mirrors the
palette by hand because TOML cannot import JSON; `tests/test_design_system.py`
fails if the two ever disagree.

---

## 1. The two references, and where they conflict

**lance.live** was measured, not admired. What it actually does: two type
scales with a deliberate void between them, one ink alpha-stepped into five
tiers, 92 px between chapters against ≤48 px within one, roughly 8% ink
coverage per viewport, 64.5 words per 1000 px of scroll, and a total accent
budget of 448 px² — seven 8×8 dots. Its first number appears at 51% page depth.

**Bloomberg** is the opposite instinct: hierarchy in a dense field, carried by
alignment and typographic weight rather than space, with figures set in tabular
lining numerals so a column of them can be read down.

They conflict in three places.

**Conflict 1 — density.** lance spends space to make one idea land. Bloomberg
packs a field and uses alignment to make it navigable.
*Resolution: they govern different scopes.* lance owns the page — the chapter
rhythm, the one-idea-per-moment sequencing, the empty space between. Bloomberg
owns the inside of any block containing figures — tight, aligned, tabular,
no decoration. The transition between the two scopes is not a compromise, it is
a boundary. lance itself demonstrates it: its dense statistics live in an
inverted white card set inside the sparse dark page. We do the same thing with
the surface token.

**Conflict 2 — the type void.** lance has nothing between 24 px and 48 px, so
display type and reading type never blur into each other. Bloomberg wants small
size steps between numbers and at most two, because a figure's importance is
carried by weight and position, not by scale.
*Resolution: the void is preserved and the numbers live on one side of it.*
Exactly one figure on the page is display-sized — the headline rate. Every
other number sits at 32 px or below and is differentiated by weight, colour and
position, never by another size step.

**Conflict 3 — motion.** lance animates a single statistic from 0 to 99 in
1.65 s. Bloomberg's rule is that numbers never animate; they swap in place.
*Resolution: Bloomberg wins, because our numbers are the argument.* A tax rate
counting up performs precision it does not have, and this page already carries
a warning that its figures are placeholders. Marks may move; digits may not.
See §7.

---

## 2. Type

Two families, two scales, a void between them.

### Display — serif, for the one number that matters and for chapter titles

| Role | Size | Leading | Weight | Notes |
|---|---|---|---|---|
| Headline rate | 72 px | 1.00 | 400 | mono, not serif — see §5 |
| Page title | 40 px | 1.15 | 400 | serif |
| Chapter title | 28 px | 1.20 | 400 | serif |

Display type is set solid or nearly so. lance sets 48 px at leading 1.00; we
follow at 72 and relax slightly as size falls.

### Reading and interface — sans

| Role | Size | Leading | Weight | Colour role |
|---|---|---|---|---|
| Secondary figure | 28 px | 1.20 | 400 | ink — mono, for any figure that is not the headline rate |
| Lead paragraph | 18 px | 1.62 | 400 | ink |
| Body | 16 px | 1.50 | 400 | ink |
| Secondary body | 14 px | 1.45 | 400 | muted |
| Label, caption, axis | 12 px | 1.33 | 400 | muted |
| Chapter marker | 12 px | 1.33 | 400 | muted, no letterspacing |

Leading is inversely proportional to size, as measured on lance: 1.62 at 18 px
down to 1.00 at display. Nothing sits between 28 px and 40 px, and nothing
between 20 px and 28 px.

**Weight carries hierarchy in exactly one place:** 14 px 600 against 14 px 400
in the same colour, used to lift a name above its role. Everywhere else
hierarchy is size, colour and position. 82% of lance's text is weight 400 and
ours should be similar. No weight below 400 anywhere.

**Measure is capped at 60 characters** (lance caps at 49–51; Streamlit's
centred column is wider than ideal, so this is the one place we accept its
ceiling rather than fight it — see §9).

---

## 3. Space

Everything on an 8 px grid, using only these steps: **8, 16, 24, 32, 48, 96**.

| Gap | Value | Rule |
|---|---|---|
| Between chapters | 96 px | lance measured 92; we round to the grid |
| Between blocks inside a chapter | 32 px | |
| Between a figure and its sentence | 16 px | the sentence belongs to the figure |
| Inside a bordered surface | 24 px | 32 px for the one data surface |
| Between paragraph and following caption | 8 px | |

The ratio between chapters and within them is ~3:1 — steeper than lance's
1.9:1, because our chapters are shorter and need harder separation.

**Density budget.** Aim for 8–12% ink coverage in any viewport. Concretely: no
screen carries more than one figure and its sentence, and the first screen
shows fewer than 40 words before the reader reaches the number. If a chapter
cannot be read in one glance it is two chapters.

---

## 4. Colour

Both palettes are authored independently. The light one is not the dark one
inverted: the dark ground is a near-black with a green cast and warm off-white
text, and the light ground is warm paper with near-black text. Neither uses
pure black or pure white — pure black behind a large bright figure haloes, and
pure white on paper is colder than the ink it carries.

### Roles

| Role | What it is for | May it carry meaning? |
|---|---|---|
| `background` | the page ground | no |
| `surface` | a raised block; the dense-figure scope of §1 | no |
| `ink` | body text and the headline figure | no |
| `muted` | labels, captions, axes, supporting text | no |
| `hairline` | rules and borders | never |
| `shape` | neutral fills that must be read, e.g. the population silhouette | no |
| `accent` | **the reader's own value, and "lowered"** | yes |
| `raised` | **"raised the rate", and nothing else** | yes |

Two chromatic values total. The accent doubles as the "lowered" direction so we
never introduce a third hue.

**Where the accent's two jobs collide, "lowered" wins locally.** Inside a block
that shows both a reader's own figure and a set of directional marks, the
figure is set in `ink` so that within that block the accent means only
"lowered". Otherwise the same colour would mean "this is yours" on one line and
"this pushed it down" on the next. Outside such a block — the percentile
marker, the twin's gap — the accent means the reader's value.

**The zero rule is `shape`, not `hairline`.** A zero baseline has to be read:
it is the thing bar direction is measured against, so it is not structure and
`hairline` is forbidden from carrying it. It is drawn in `shape`, the role for
neutral fills that must be legible.

### Dark (default)

| Token | Value | Contrast on ground |
|---|---|---|
| `background` | `#0E1513` | — |
| `surface` | `#161F1D` | 1.14 |
| `ink` | `#E9E7E2` | 14.97 |
| `muted` | `#94A09D` | 6.85 |
| `hairline` | `#2A3634` | 1.48 |
| `shape` | `#3A4A47` | 1.98 |
| `accent` | `#8AD0EA` | 10.83 |
| `raised` | `#BE7636` | 5.14 |

### Light

| Token | Value | Contrast on ground |
|---|---|---|
| `background` | `#FAF8F4` | — |
| `surface` | `#F0EDE6` | 1.07 |
| `ink` | `#17201E` | 15.69 |
| `muted` | `#556360` | 5.93 |
| `hairline` | `#DAD5CA` | 1.38 |
| `shape` | `#C9C2B4` | 1.67 |
| `accent` | `#3075A6` | 4.69 |
| `raised` | `#6F2E0D` | 9.55 |

### Why the direction pair is not 3:1

The Bloomberg rule is a ≥3:1 lightness difference between the two direction
hues. It cannot be met here, and the arithmetic is worth recording so nobody
re-opens it:

On the dark ground, AA legibility floors any colour at relative luminance
L ≥ 0.205. A partner 3:1 lighter would need L ≥ 0.716 — that is near-white,
which stops reading as a hue and starts competing with `ink`. On paper the
mirror applies: the AA ceiling is L ≤ 0.170, so the partner would need
L ≤ 0.023, which is darker than our body ink and reads as a mistake.

The achievable maximum, with both hues legible and neither impersonating ink or
the ground, is **2.11:1 dark and 2.03:1 light**. That is what we ship, and
`tests/test_design_system.py` enforces ≥1.9.

The rule's *intent* is met a different way. Both research streams say direction
must be encoded twice; ours is encoded three times and hue is the weakest of
the three:

1. **Position** — bars extend left or right of a zero line. Unambiguous with no
   colour at all.
2. **Sign and word** — every value carries an explicit `+` or `−`, and the
   sentence above the figure names the direction in English.
3. **Hue** — the secondary cue, at the best contrast the constraints allow.

Red and green are never used for direction.

---

## 5. Numbers

Every figure on this page follows these rules. They come from the Bloomberg
research, cut down to what this page actually shows.

1. **Tabular figures everywhere.** `font-variant-numeric: tabular-nums lining-nums`
   on any numeric element, and the mono stack where a face may lack `tnum`.
   Two figures a reader compares must align on the decimal.
2. **One precision per comparison.** Rates are one decimal, always. A gap in
   points is one decimal, always. Never 1.6 against 1.60.
3. **Negatives use U+2212 (−), tight to the digit.** Never parentheses, never
   colour alone, never a hyphen.
4. **Percent versus percentage point is a real distinction and is respected in
   the copy.** A rate is "8.6% of income"; a gap is "1.6 points", never "1.6%".
5. **Unit stated once**, in the sentence or the axis title, never repeated in
   every value.
6. **Never abbreviate** the headline rate, the percentile, or either comparison
   value. Money is abbreviated only by rounding to a magnitude
   (`$1,000 a year`), never to `1K`.
7. **Money is rounded hard and labelled as approximate** — nearest 10 below
   $1,000, nearest 100 below $10,000, nearest 1,000 above. Always preceded by
   "roughly" or "about". The dollar sign is escaped in Streamlit markdown, or
   the renderer eats the text between two of them as maths.
8. **Percentiles are whole numbers**, phrased as counts out of 100 rather than
   as an ordinal where possible: "about 64 in every 100 filers".
9. **Numbers never animate.** They swap in place.

---

## 6. The three visualisations

### (a) Percentile — **Altair, not React**

The brief allows this and the honest answer is that Altair does it well. It is
a static distribution with a marker; there is no interaction requirement, no
state, and no bespoke layout. Every additional React component is another
build artifact, another iframe, another theme-propagation surface, and another
way for the page to break — that cost is worth paying for the two figures that
carry the argument, and is not worth paying here.

Chosen form: a **fixed-bin histogram** over the real distribution, with the
zero bin drawn as its own separated column, the negative region shaded and
labelled in words, and a single accent rule for the reader.

- *Communicates:* the true shape — a long negative tail, a hard spike at zero,
  a short right tail. That the reader is somewhere in a real population.
- *Obscures:* the percentile itself, which is not readable off a histogram and
  must be asserted in the sentence beneath it. Also the far right tail, which
  is short enough to nearly vanish next to the mode.
- *Degrades:* a very high rate puts the marker in a sparse region where the
  label must flip inside the plot to avoid clipping. A negative rate puts it in
  the shaded region, which is exactly where the annotation explains itself. A
  rate at zero collides with the zero column, so the marker draws above it.
- *Rejected:* a smoothed density (renders the 8.5% point mass at zero as a bump
  with width — a lie); a cumulative curve (reads the percentile directly, but
  is the least familiar chart type on the page).
- *Companion:* the sentence states the position as a count out of 100, which is
  the format low-numeracy readers handle best.

### (b) Contribution — **React**

Chosen form: a **ranked reason list with inline magnitude bars** — the pattern
credit reports and regulated insurance disclosures already use, so a general
reader has met it before. At most five rows, sorted by absolute size, each a
plain English sentence with a bar from a shared zero and a figure in points.
Rows are grouped by direction with a heading in words.

- *Communicates:* which handful of things mattered and roughly how much, in a
  form that reads as reasons rather than as a chart.
- *Obscures:* interaction between factors. A ranked additive list asserts an
  independence the underlying values do not have, which is why the baseline is
  stated explicitly and the list closes with "everything else together".
- *Degrades:* when nothing exceeds the threshold the component renders an
  explicit "nothing stands out" state rather than five indistinguishable stubs.
  A single dominant factor is fine. More than five are truncated with the
  remainder summed into one final row, never silently dropped.
- *Rejected:* the SHAP waterfall (assumes chart literacy, names features);
  a single stacked deviation bar (compact, but tiny segments become unreadable
  and the ranking disappears).

### (c) Twin — **React, and the most care**

Chosen form: **two identically-formatted cards with the gap between them.**
Each card lists the same attributes in the same order; everything the two share
is set in muted, and the one attribute that differs is lifted into ink. Between
them sits the gap: the difference in points as the largest element, a dumbbell
whose *connector* is the heaviest mark, and one line of money translation.

The reason for the cards, and it is the whole argument: a chart of two dots
shows that two numbers differ. It does not show that everything else was held
constant, which is the premise the equity claim rests on. The sameness has to
be visible.

- *Communicates:* that these two filers are the same person but for one fact,
  and that the fact is worth a specific amount.
- *Obscures:* how typical this gap is — two twins can always be chosen to
  flatter an argument. The copy must state that this is one comparison, not a
  population finding, and the page never presents it as the latter.
- *Degrades:* a near-zero gap must trip a copy rule — "essentially the same
  rate" — and must never be drawn as a two-pixel bar that implies a difference.
  A gap that crosses zero draws the zero line explicitly, because "one pays,
  one is paid" is a different claim from "one pays more". Both sides negative
  is legitimate and styled identically to both sides positive.
- *Rejected:* two large numbers side by side (numerically clear, emotionally
  inert — the reader compares two facts instead of seeing one distance);
  a slope chart (reads as change over time, which this is not).

---

## 6b-i. Bar and mark geometry

The design system fixes type, colour and space but was silent on the pixel
sizes of the marks inside the two React components. These are the agreed
values, so the two components draw at the same weights:

| Mark | Size |
|---|---|
| Magnitude / dumbbell bar thickness | 8 px (the grid step) |
| Bar track height | 14 px |
| Zero rule thickness | 2 px |
| Minimum visible bar mark | 3 px (so a 0.2-point bar is still a mark) |
| Dumbbell dot diameter | 10 px |
| Dumbbell connector thickness | 5 px (the heaviest mark in the twin) |

The layout breakpoint where a bar drops beneath its sentence rather than
sitting beside it is **560 px of component width** — not a device width, the
component's own width, since it renders in a variable column inside an iframe.

## 7. Motion

A budget, not a palette.

- Two durations only: **150 ms** with `cubic-bezier(.4, 0, .2, 1)` for state
  changes, **300 ms** with `cubic-bezier(0, 0, .2, 1)` for anything entering.
- **Digits never animate.** When a flip changes the twin, the connector and the
  dots move to their new positions; the numerals are replaced.
- No entrance choreography, no scroll-triggered reveals, no count-ups. lance
  ships zero opacity-0 elements and zero inline transforms, and so do we.
- `prefers-reduced-motion: reduce` removes all transitions. Nothing on this
  page depends on motion to be understood.

---

## 8. Component prop contracts

Both components are renderable from a JSON fixture with no Python running.
Everything crossing the boundary is display-shaped: finished English, rounded
numbers, no column names, no codes.

```ts
type Mode = "dark" | "light";

interface Palette {
  background: string; surface: string; ink: string; muted: string;
  hairline: string; shape: string; accent: string; raised: string;
}

interface Tokens {
  fontSans: string; fontMono: string; fontSerif: string;
  radius: number;
  light: Palette; dark: Palette;
}
```

### twin

```ts
interface TwinAttribute {
  /** e.g. "Income" — sentence case, already written for a reader. */
  label: string;
  /** e.g. "$64,000 a year, mostly from a paycheck". */
  value: string;
}

interface TwinSide {
  /** e.g. "filing alone". */
  label: string;
  /** Effective rate in points. Negative is legitimate. */
  rate: number;
  /** Pre-formatted, e.g. "8.6%". The component never rounds. */
  display: string;
}

interface TwinProps {
  mode: Mode;
  tokens: Tokens;
  /** What differs, in English: "how they file". */
  changed: string;
  a: TwinSide;
  b: TwinSide;
  /** Held constant, shown identically on both cards, in display order. */
  shared: TwinAttribute[];
  /** Signed gap in points, pre-rounded to one decimal. */
  gapPoints: number;
  /** Pre-formatted money, or null when it would mislead. */
  gapMoney: string | null;
  /** True while the model is a placeholder. */
  isPlaceholder: boolean;
}
```

### contribution

```ts
interface Reason {
  /** A sentence fragment: "having two children at home". */
  text: string;
  /** Signed, in points, pre-rounded to one decimal. */
  points: number;
}

interface ContributionProps {
  mode: Mode;
  tokens: Tokens;
  /** What a typical filer pays, in points — where the bars start from. */
  baseline: number;
  /** Where this filer ended up, in points. */
  predicted: number;
  /** At most five, pre-sorted by absolute size, pre-filtered. */
  reasons: Reason[];
  /** Everything below the threshold, summed. Null when there is none. */
  remainder: number | null;
  /** True when nothing cleared the threshold: render the calm empty state. */
  nothingStandsOut: boolean;
  isPlaceholder: boolean;
}
```

Rounding, filtering, ranking, thresholding and every English string are decided
on the Python side. The components render what they are given.

---

## 9. The ceiling, stated plainly

Page-level layout is Streamlit's and will stay Streamlit's. That has real
costs, and they are accepted rather than worked around:

- **Measure.** Streamlit's centred column is wider than the 49–51 characters
  lance holds to. We cap at 60 and accept it.
- **Widget typography.** Form controls are Streamlit's, themed but not
  redrawn. They will never look bespoke.
- **The theme toggle** lives in Streamlit's own settings menu, not on the page,
  because an in-page toggle needs injected CSS to repaint the host's chrome.
- **Vertical rhythm** is approximate. Streamlit inserts its own margins between
  elements; our 96 px chapter gaps are achieved with explicit spacers and land
  within a few pixels rather than exactly.

What we get is flagship-quality figures inside a well-themed Streamlit page.
Anything that requires control of the page itself is out of reach, and no
amount of care inside the components changes that.

# Path C web system

This document locks the design and HTTP contracts for the standalone website.
It extends `DESIGN_SYSTEM.md` for a page shell that the project owns. Colour,
font-family, radius, number-formatting, and visualization semantics still come
from `DESIGN_SYSTEM.md` and `tokens.json`.

## Page system

- Dark is the deterministic first theme. Light is independently designed.
- Palette roles and values are unchanged from `tokens.json`.
- Display type remains Source Serif. Reading, interface, and numeric type use
  Source Sans Pro. Website figures use proportional lining numerals at weight
  600: warm and editorial, never terminal-like. This deliberately overrides
  the Streamlit fallback’s historical mono/tabular rule in
  `DESIGN_SYSTEM.md`; formatting precision does not change.
- Hero display type is 44 px on mobile, 72 px on desktop, and 80 px on wide
  screens. The headline rate remains 72 px at weight 600. Chapter statements
  are 40 px.
- Spacing uses only 8, 16, 24, 32, 48, and 96 px.
- The page is full bleed. Its internal canvas is at most 1,800 px, prose is at
  most 60 characters, and the wide-screen chapter heading column is 240 px.
- Sections use 96 px vertical padding and normally occupy 80–100 svh.
- State changes take 150 ms. A chapter may reveal once with 16 px of vertical
  travel over 500 ms and at most 60 ms of sibling stagger.
- Digits never tween, count, or roll. Reduced motion removes all transforms,
  ambient movement, and transitions.

The page sequence is: fixed navigation and progress line, argument-first hero,
thesis, integrated profile form, the four result chapters, method and limits,
then the closing argument.

The profile form opens with four essential groups: total income, marital and
filing status, state, and age. “Add more detail” reveals the seven income-source
amounts, household details, and spouse income when applicable. A collapsed form
still submits the complete semantic profile: all income is assigned to wages,
other sources and children are zero, and household size is the smallest valid
value for the selected marital status.

The frontend exposes these theme variables:

```css
--background; --surface; --ink; --muted; --hairline; --shape;
--accent; --raised;
--font-sans; --font-mono; --font-serif; --radius;
```

## Reader-facing profile

Every model operation receives a wrapper with this profile:

```ts
type TaxProfile = {
  totalIncome: number;
  spouseIncome: number;
  income: {
    wages: number;
    business: number;
    interest: number;
    dividends: number;
    retirement: number;
    socialSecurity: number;
    rent: number;
  };
  age: number;
  childrenAtHome: number;
  childrenUnderFive: number;
  householdSize: number;
  maritalStatus:
    | "married_living_together"
    | "married_living_apart"
    | "separated"
    | "divorced"
    | "widowed"
    | "never_married";
  filingChoice: "head_of_household" | "single" | null;
  state: string; // full reader-facing state name
};
```

The API may map these semantic values to the existing raw profile accepted by
`model_interface.py`. It must not construct, reorder, encode, or reinterpret
the frozen 16-feature row.

## HTTP contract

All endpoints use `/api/v1`. The three initial requests can run concurrently
after the reader submits the form. The twin request runs when the comparison
choice changes.

### Predict

`POST /api/v1/predict`

```json
{
  "profile": {
    "totalIncome": 64000,
    "spouseIncome": 0,
    "income": {
      "wages": 64000,
      "business": 0,
      "interest": 0,
      "dividends": 0,
      "retirement": 0,
      "socialSecurity": 0,
      "rent": 0
    },
    "age": 42,
    "childrenAtHome": 0,
    "childrenUnderFive": 0,
    "householdSize": 1,
    "maritalStatus": "never_married",
    "filingChoice": "single",
    "state": "New York"
  }
}
```

```ts
type PredictResponse = {
  rate: number;
  display: string; // one decimal, percent sign, U+2212 when negative
  isNegative: boolean;
  framing: string;
};
```

### Percentile

`POST /api/v1/percentile` receives the same `{ profile }` wrapper.

```ts
type DistributionBin = { start: number; share: number };
type PercentileResponse = {
  markerRate: number;
  displayRate: string;
  percentile: number;
  belowCount: number;
  bins: DistributionBin[];
  binWidth: number;
  shareExactlyZero: number;
  shareNegative: number;
  domain: [number, number];
  summary: string;
};
```

The summary describes predicted rates among survey filers in the model's
reference set. It must not call this unweighted reference “the whole country.”

### Contribution

`POST /api/v1/contribution` receives the same `{ profile }` wrapper.

```ts
type Reason = { text: string; points: number };
type ContributionResponse = {
  baseline: number;
  predicted: number;
  reasons: Reason[];
  remainder: number | null;
  nothingStandsOut: boolean;
  summary: string;
};
```

Reasons are finished English, absolute-magnitude ranked, thresholded at 0.15
raw points, capped at five, and rounded to one decimal. Everything omitted is
summed into `remainder`. `nothingStandsOut` is true only when there is no named
reason and the total predicted-minus-baseline difference is negligible.

### Twin

`POST /api/v1/twin`

```ts
type TwinRequest = {
  profile: TaxProfile;
  comparison: "filing" | "marital" | "income_source" | "dependents";
};

type TwinSide = { label: string; rate: number; display: string };
type TwinAttribute = { label: string; value: string };
type TwinResponse = {
  changed: string;
  changedLabel: string;
  a: TwinSide;
  b: TwinSide;
  shared: TwinAttribute[];
  gapPoints: number;
  gapMoney: string | null;
  summary: string;
  comparisonNote: string;
};
```

The printed gap equals the difference between the two printed one-decimal
rates. A gap that prints as zero is “essentially the same.” Negative rates are
ordinary findings. A comparison crossing zero names that one side pays while
the other is paid.

### Readiness and errors

`GET /healthz` returns:

```ts
type HealthResponse = {
  status: "ready" | "degraded";
  modelReady: boolean;
  artifactSource: "local" | "downloaded" | null;
};
```

Invalid profiles return 422. A missing artifact or a contract-integrity
failure returns 503 with:

```json
{
  "detail": {
    "code": "model_unavailable",
    "message": "The analysis service is not ready yet."
  }
}
```

Messages returned to the browser never contain paths, filenames, model field
names, or implementation details.

## Model artifact bootstrap

The backend uses the local configured artifact when it exists. Otherwise,
`TAX_MODEL_DOWNLOAD_URL` may name a GitHub Release asset. The download is
streamed to a sibling `.part` file, checked against the SHA-256 in committed
model metadata, and atomically promoted only after verification. A private
release may use a token. `model_interface.py` remains responsible for loading
and validating the fitted pipeline.

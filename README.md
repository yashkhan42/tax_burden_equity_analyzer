# Tax Burden Equity Analyzer

Two people can earn the same amount and pay very different shares of it in
federal tax. Where that income comes from and who you live with both matter.
This project measures how much.

We trained a model on 61,231 real tax filers from Census survey data, then used
it to answer three questions about any household you describe:

- What effective federal tax rate would a household like this pay?
- Which of its characteristics pushed that rate up or down, and by how much?
- What happens if you change exactly one thing and hold everything else fixed?

That last question is the point. It isolates one characteristic at a time,
which is the cleanest way to show a difference that's built into the system
rather than into the person.

Built for AI4ALL Ignite.

---

## What we found

**Marriage.** A single earner making $85,000 pays about 12%. Change nothing
except marital status — same income, same state, same age — and the rate drops
to about 7%. That gap comes from the standard deduction doubling and the
brackets widening for joint filers.

We checked it two ways outside the model. Hand-computing 2023 tax law gives
12.9% and 7.6%. Real filers in the data at $80–90k with no children show a
median of 12.4% single and 7.3% married. The model isn't inventing the pattern.

**Where income comes from.** Wage income and capital income at the same dollar
amount don't land in the same place. Two of the SHAP waterfalls in
`reports/figures/` show this at the top income decile: one wage-heavy filer,
one capital-heavy filer, same income band, different outcomes.

**Refundable credits.** About 12% of filers have a negative effective rate —
they get more back than they owe. We never round these up to zero. Clipping
them would erase the most progressive part of the system, and it's the part
most people never see.

---

## Does the model actually work?

**Accuracy.** On a test set of 12,247 filers the model was never trained on:
R² of 0.90, and predictions land within 1.28 percentage points on average.
Guessing the average for everyone gives 6.37, so the model is about 5× better
than that baseline.

**Against the IRS.** We compared our predicted rates to the IRS's published
2023 statistics, band by band. In the $50,000–75,000 band we predict 5.5%, the
survey data observes 5.5%, and the IRS reports 6.1%. The full comparison across
19 income bands is in `reports/phase6_summary.md`.

**Where it's weak.** Survey data undersamples the very wealthy — the highest
band with any observations at all has 8 people in it. We say so rather than
quietly dropping the band.

---

## The part we're most careful about

A "what if this person were married" comparison asks the model about someone who
doesn't exist in the data. Sometimes that's fine and sometimes it's guessing,
and the difference matters.

Going from single to married joint is well supported: 1,370 filers in the
training data are married with no spouse income, so the model has seen this kind
of household. Average gap of −4.84 points.

Going the other direction produces a bigger number, +6.62, and we don't report
it. 94.3% of those filers carry spouse income into a combination that appears
**zero times** in the training data. The model is extrapolating, so the notebook
labels it and excludes it.

We ran the same check on filing status. Flipping a childless single filer to
head of household gives a dramatic −13.88, but head of household usually
requires a dependent, and only 258 of 4,524 training examples fit that shape.
Flagged as thin, not quoted.

The comparison we lead with is the smaller, better-supported one. That's on
purpose.

---

## How it fits together

**The data.** IPUMS CPS ASEC 2024, covering income year 2023. 64,696 person
records, filtered to 61,231 tax filers.

**A bug we had to fix first.** The tax figures in this data describe a whole
return, but the income columns describe one person, and only one spouse per
couple is in the file. For joint filers, income was being undercounted by a
median factor of 1.77. Left alone the model would have learned "married people
pay less" when the real reason was "married people often have a second earner I
can't see." We rebuild income at the return level before anything else —
dependents are recoverable through a pointer column, and the missing spouse
comes out of the family total. After the fix, correlation between our income
feature and the true return income goes from 0.82 to 0.98.

**The model.** A Random Forest of 500 trees over 16 features. Settings chosen
by cross-validation inside the training data only; the test set was used once,
at the end.

**Explanations.** SHAP breaks each prediction into per-feature contributions
that sum exactly to the predicted rate. We verify that sum to 11 decimal places,
because an explanation that doesn't add up is decoration.

**Guardrails.** The training and test files are frozen and fingerprinted. Every
notebook checks those fingerprints before running and refuses to continue if
anything drifted. Nine columns that encode the answer are quarantined and can
never reach the model — the code rejects a profile that even mentions them.

---

## Running it

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-dev.txt
python3 scripts/fetch_model.py
```

The trained model is 276 MB, too big for git, so it's published as a GitHub
Release and downloaded by that last command. It's checked against a recorded
SHA-256 while it downloads, so a corrupted transfer can't land.

Then start the app:

```bash
uvicorn backend.main:app --port 8000
```

Startup takes 30–60 seconds. It loads the model and exercises every code path
before reporting ready, so no user request is ever the first time something
runs. Check with `curl localhost:8000/healthz` and wait for `"modelReady":true`.

For frontend development with hot reload, run `npm run dev` in `frontend/`
alongside the API. For a single-URL deployment, `npm run build` exports the site
to static files that the API serves itself — that's what the `Dockerfile` does,
and it runs anywhere that takes a Dockerfile.

Run the tests with `python3 -m pytest tests/`.

---

## What's in here

```
notebooks/     the analysis, in order: prepare, train, explain, compare, validate
model_interface.py   the only file allowed to touch the model
backend/       FastAPI service
frontend/      Next.js site
app.py         Streamlit version, kept as a fallback
reports/       figures, twin results, IRS comparison
data/          raw CPS extract and the frozen train/test split
```

Everything routes through `model_interface.py`. Two separate interfaces and all
the notebooks call it, and none of them rebuild feature logic or touch the model
file directly. That's why the website and the analysis can't drift apart — the
SHAP notebook asserts its own math matches the version the website uses, to 18
decimal places.

---

## Honest limitations

- The train/test split is random by filer, not by family, so 8,917 families have
  members on both sides. The test score is probably a little optimistic.
- Spouse income has no breakdown by source, so it can't be split across the
  seven income categories the way the filer's own income is.
- Survey data thins out badly at the top of the distribution.
- Predictions describe what households like yours typically pay. This is not a
  tax calculator and won't tell you what you owe.

---

## Team

Yash Khan, Laura Romero, Arya Bhatt.

Data from IPUMS CPS. Validation figures from IRS Statistics of Income, 2023.
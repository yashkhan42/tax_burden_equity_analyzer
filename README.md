# Tax Burden Equity Analyzer — Technical Specification & PRD

**Project:** AI4ALL Ignite — Finance & Business domain
**Version:** 1.0
**Status:** Development-ready
**Audience:** Developer / coding agent building the system end to end

---

## 1. Purpose & One-Sentence Definition

Train a regression model to predict a tax filer's **effective federal tax rate** from their **pre-tax characteristics**, then use SHAP and counterfactual "twin" comparisons to expose that economically similar filers pay systematically different effective rates — quantifying structural inequities in how the federal tax code treats different people and income types.

This is **not** a tax calculator. TurboTax computes a filer's exact tax by *applying the rules*. This system does the inverse: it *learns the patterns* across ~60K real filers, then interrogates the learned model to reveal which characteristics move a filer's effective rate up or down, and by how much.

---

## 2. Problem Statement & Motivation

The federal tax code treats different **income types** (wages vs. capital gains vs. dividends), **filing statuses**, and **household structures** differently. As a result, two filers with identical total income can face materially different effective rates. These differences are legal and by design, but their *aggregate distributional effect* is not obvious to any individual filer.

The deliverable makes those effects visible and quantifiable: given a filer profile, it shows the predicted effective rate, explains what drove it (SHAP), and — most powerfully — holds everything constant while flipping a single attribute to isolate that attribute's causal contribution to the rate (twin comparison).

---

## 3. Data

### 3.1 Source
- **Dataset:** IPUMS CPS ASEC 2024 (income year 2023), single sample.
- **Rationale:** free; contains Census-imputed federal tax variables plus all required demographic axes. Income year 2023 aligns exactly with IRS SOI 2023 tables used for validation.
- **Do not add more ASEC years.** The analysis is cross-sectional; multiple years introduce tax-law and inflation confounds without serving the research question.
- **Current input file:** `cps_filers_clean.csv` — **64,696 rows × 59 columns**, IPUMS variable names, one row per **person** record.

### 3.2 Unit of Analysis
The file is currently **person-level** (`pernum`, `cpsidp` identify persons). The modeling unit is the **tax-filer unit**. IPUMS provides the tax-unit grouping via `spmfamunit` (SPM family unit; ~50,751 distinct units in this file), and `depstat` flags dependents.

**Decision for the implementer (Phase 1):** choose one and document it —
- **(A) Filter to primary filers:** keep `depstat == 0` (non-dependent filers; 61,231 rows) and treat each as a filer-unit row. Simplest, and the tax variables (`fedtaxac`, `adjginc`, `eitcred`) are already imputed at the filing level by Census. **Recommended default.**
- **(B) Collapse by `spmfamunit`:** aggregate person records to the SPM unit. More faithful to true household filing but requires deciding how to combine spousal income and which person supplies demographic features.

Start with (A). It is defensible, avoids aggregation ambiguity, and the imputed tax fields already reflect filing-level amounts.

> **AMENDED (Phase 1, implemented).** (A) is the right filter but is **not sufficient on its own**, and the reason is the sentence above: the tax fields are imputed at the *filing* level, while every income column on the row is that one *person's*. For a joint return `adjginc` covers both spouses and `inctot` covers one. Measured: median `adjginc / inctot` was **1.77** for joint filers against **1.00** for single. ~40% of rows were asking the model to predict a rate whose denominator it could not see — which would have charged the missing spouse's income to `filing_status`/`marst` in every SHAP waterfall, and made the twin comparison's single → joint gap mostly "married people often have a second earner" rather than anything the tax code does.
>
> Income is therefore **reconstructed to whole-return scope** before any feature is derived:
> - **Dependents** are present as rows — `depstat` holds the claiming filer's `pernum` within `serial`.
> - **The spouse is absent from this extract entirely** (one spouse is kept per couple), so their income cannot be read off any row. It is recovered as the family residual `ftotval − sum(inctot of persons present)`. That residual is $0 at the 25th, 50th *and* 75th percentile for families with no joint filer, and ~$50,000 median for families with one — it is the spouse. It is keyed on the **family**, not `spmfamunit`: an SPM unit can span several families and 4,173 do.
>
> Result: spread in `adjginc / income` across filing statuses **0.77 → 0.11**, correlation with `adjginc` **0.815 → 0.983**. The feature is `unit_inctot`; `inctot` alone no longer enters `X`. `ftotval` moves from `drop` to `feature` for this reason (it is pre-tax, so it is not leakage — income level is the primary *legitimate* driver of an effective rate, and knowing a ratio's denominator does not reveal the ratio). See `data_dictionary.md` and `freeze_manifest.json`.

### 3.3 The Target

**Target column:** `eff_rate`, already present in the file.
- **It is stored as a percentage:** `eff_rate = 100 × fedtaxac / adjginc` (verified exactly against the file). A value of `4.06` means **4.06%**, not 406%. Do **not** divide by `adjginc` again — use `eff_rate` directly, or model `fedtaxac/adjginc` and stay consistent, but never both.
- `fedtaxac` = federal income tax after credits (numerator). `adjginc` = adjusted gross income (denominator). All rows have `adjginc > 0`, so the ratio is always defined.

**Negative effective rates — a required modeling decision.** **7,344 rows (11.4%) have `fedtaxac < 0`** and therefore a **negative `eff_rate`** (min ≈ −50%). These are filers whose **refundable credits (EITC, refundable CTC) exceed tax owed** — the government pays them net. This is real and important to the equity story (the code is net-progressive at the bottom), but the implementer must decide how to frame it:
- **Keep them (recommended):** the negative tail *is* a finding — refundable credits produce negative effective rates for low-income filers with dependents. Report it explicitly.
- If a reviewer objects to "rates below zero," present it as *net federal tax rate* rather than clipping, so the progressivity signal survives.
- Do **not** silently clip to zero — that erases the most progressive part of the system.

### 3.4 The Feature / Quarantine Split (full 59-column sort)

Every column is assigned to exactly one pile. Misassignment causes **data leakage** — a model that peeks at the answer, producing fake-perfect accuracy that collapses on real data and invalidates every SHAP attribution and twin gap. **When timing is ambiguous, quarantine.**

**QUARANTINE — never a feature (target, its components, or post-tax/credit variables):**

| Column | Reason |
|---|---|
| `eff_rate` | The target itself. |
| `fedtaxac` | Numerator of the target. |
| `adjginc` | Denominator of the target. |
| `spmfedtaxac` | SPM-unit federal tax — same outcome, different grouping. Leakage. |
| `eitcred` | Refundable credit — computed as part of the tax outcome. |
| `ctccrd`, `actccrd` | Child tax credit / additional (refundable) CTC — post-tax credits. |
| `margtax` | Marginal tax rate — a direct function of the tax computation. |
| `taxinc` | Taxable income — post-deduction, downstream of AGI. |
| `fica` | Payroll tax — a computed tax outcome (not the target, but not a pre-tax feature; exclude to keep "pre-tax" clean). |
| `filestat` (as leakage risk) | **See note below** — filing status is a legitimate feature, but the *variable itself* was assigned by the CPS tax model. Use `marst`-derived status instead where possible; if using `filestat`, treat as feature but flag it. |

**FEATURES — pre-tax, known before any tax is computed:**

| Feature (derived) | Source column(s) | Notes |
|---|---|---|
| Total income | `unit_inctot` | **AMENDED** — whole-return pre-tax income: `inctot` + dependents' `inctot` + spouse residual (§3.2). Person-level `inctot` alone is the wrong scope and no longer enters `X`. Range is heavily skewed; **consider `log1p`**. Can be negative (business/rent losses). |
| Wage share | `unit incwage / unit_inctot` | Income composition — **the core equity signal.** |
| Business share | `unit incbus / unit_inctot` | Can be negative (losses); guard division when the denominator is small. |
| Interest share | `unit incint / unit_inctot` | |
| Dividend share | `unit incdivid / unit_inctot` | Capital income — taxed preferentially; key to the story. |
| Retirement share | `unit incretir / unit_inctot` | `incretir` has some nulls — impute 0. |
| Social Security share | `unit incss / unit_inctot` | Partially/untaxed; relevant to age equity. |
| Rent share | `unit incrent / unit_inctot` | Can be negative; guard. |
| Spouse income share | `spouse residual / unit_inctot` | **AMENDED (new)** — `ftotval` carries no breakdown by source, so the recovered spouse income cannot be split across the seven shares above. It gets its own column, keeping the shares additive and the unobserved portion legible to SHAP. 0 for every non-joint filer, so read its waterfall bar as *"a second earner is on this return"*, not as an income type. |
| Filing status | `filing_status`, derived from `filestat` | **AMENDED — the gloss below was wrong.** Per the IPUMS codebook shipped at `data/raw/data_dictionary.csv`, `filestat` is `1=Joint both <65`, `2=Joint one 65+`, `3=Joint both 65+`, `4=Head of household`, `5=Single`. Codes **1/2/3 are all joint returns split by age** — not joint/sep/sep — and there is **no married-filing-separately category in this data at all**. The data confirms it: 1/2/3 are 100% `marst`=1 and code 3 has a minimum age of 65. Collapsed to `filing_status` = **1 joint / 4 head_of_household / 5 single**; the age split stays in `age`, which is already a feature. Keeping the raw code would hand the model an age bracket disguised as a filing status and make the §5.2 twin flip incoherent — `5 → 3` would mean *become married **and** become 65+*. |
| Marital status | `marst` | Structural driver independent of imputed filestat. |
| Number of children | `nchild` | Drives dependent credits/deductions. |
| Young children | `nchlt5` | CTC/childcare relevance. |
| Family size | `famsize` | Household scale. |
| Age | `age` | Retirement/senior treatment. |
| State | `statefip` | Geographic axis; hook for optional state merges. **Categorical** — one-hot or target-encode, don't treat as numeric. |

**FEATURES — optional demographic/context axes (include deliberately, see risk §10.4):**

| Feature | Source | Notes |
|---|---|---|
| Education | `educ` | Categorical/ordinal. |
| Employment status | `empstat` | |
| Weeks worked | `wkswork1` | |
| Usual hours | `uhrsworkly` | |
| Class of worker | `classwkr` | Self-employed vs. wage — interacts with income type. |
| Pension coverage | `pension` | |
| Firm size | `firmsize` | |
| Sex | `sex` | **Sensitive — include only if the equity framing explicitly covers it.** |

**DROP — identifiers, weights, and administrative columns (not features, not target):**
`year`, `serial`, `month`, `cpsid`, `cpsidp`, `cpsidv`, `asecflag`, `pernum`, `ftype`, `spmfamunit`, `spmwt`, `spmftotval`, `hhincome` (household-level, redundant with filer income and risks leakage of the unit's total).

> **AMENDED:** `ftotval` was originally in this drop list; it is now a **feature-pile** column — it is the sole recoverable source of the absent spouse's income (§3.2) and enters `X` only via `unit_inctot` and the shares. `serial`, `pernum`, `depstat` remain dropped but serve as structural keys during tax-unit assembly.

**Survey weights — do not use as features, but keep for validation:** `asecwt`, `asecwth`. These are the correct weights for producing population-representative estimates in the §6 validation loop (unweighted CPS means are biased). Pass them to weighted metrics / weighted aggregation, **never** into `X`.

**Sensitive columns to handle with care (see §10.4):** `race`, `hispan`, `citizen`, `nativity`, `yrimmig`, `vetstat`, `diffany`, `sex`. The demographic framing agreed for this project is **income / filing-status / geography** — do **not** add race/ethnicity/immigration as equity axes without an explicit team decision, and never present them as causal drivers of tax burden.

> **Phase 0 deliverable:** encode the above as an explicit `data_dictionary.md` mapping every one of the 59 columns to `{target, feature, optional_feature, quarantine, drop, weight, sensitive}`. This is the artifact that prevents leakage.

### 3.5 Freeze the Modeling Table (blocking dependency)
After the filer-unit filter (§3.2) and the split (§3.4), produce `train.csv` and `test.csv` (recommended 80/20, fixed `random_state`). Retain `asecwt` as a non-feature column for weighted validation. **This freeze is the only blocking dependency in the project.** Once frozen, no column may be added, and the modeling / SHAP / stretch workstreams run in parallel.

---

## 4. Modeling (Core — Required)

### 4.1 Model
- **Random Forest Regressor** (scikit-learn) predicting `eff_rate` (percentage-scale effective federal tax rate, §3.3).
- Chosen for: handles non-linear feature interactions, robust on tabular data, native compatibility with SHAP `TreeExplainer` (fast, exact). Also tolerates the negative-rate tail without transformation.
- Reproducibility: fixed `random_state` everywhere; log all hyperparameters.
- Categorical features (`statefip`, `marst`, `filestat`, `educ`, etc.) need encoding — one-hot for low-cardinality, and for `statefip` (51 levels) prefer one-hot or leave-one-out target encoding; document the choice.

### 4.2 Metrics
- Primary: **R²**, **MAE** (mean absolute error, in effective-rate points).
- Diagnostic: residual distribution plot; residuals vs. predicted (check for systematic bias across income levels).

### 4.3 Faithfulness > Accuracy
The deliverable's value comes from SHAP attributions and twin gaps being **trustworthy**, which requires the model to have learned the tax code's *real* patterns rather than noise or leaked signal. A leaked model gives confident, wrong waterfalls. Prioritize a clean, leakage-free feature set over squeezing out marginal accuracy.

---

## 5. Interpretation Layer (Core — Required)

The trained model is a queryable function: `features → predicted effective rate`. Both headline features are different interrogations of that same function.

### 5.1 SHAP Waterfall (per-filer explanation)
- Use SHAP `TreeExplainer` on the Random Forest.
- **Global output:** feature-importance summary + dependence plots (where the aggregate equity findings live).
- **Per-filer output:** a waterfall that starts at the baseline (average predicted effective rate across all filers) and walks feature-by-feature to that filer's predicted rate — one labeled bar per feature showing its signed push in rate points.
- Example: baseline 12% → married-joint −2.1 → 2 dependents −1.8 → dividend-heavy income −3.4 → income level +1.5 → **6.2%**.
- Mechanism note: SHAP works by asking the model what it would predict as each feature is varied/removed. **No trained model = nothing to interrogate = no waterfall.**

### 5.2 Twin Comparison (counterfactual — the strongest feature)
- Take one filer, **hold every feature constant, flip exactly one** (e.g. filing status single → married-joint), run both versions through the model, surface both predictions and the gap.
- Example: Twin A (single) 14.0% vs. Twin B (married) 11.2% → **2.8-point gap caused solely by the flipped attribute.**
- This is a counterfactual: the "married twin" of a single filer doesn't exist in the data, so it must be *generated* by the model. This is the cleanest statement of a structural inequity — same income, same everything, different rate, with the responsible attribute isolated.
- Attributes to support flipping: filing status, marital status, dominant income source (recompose shares), number of dependents.

---

## 6. Validation Loop (Core — Required)

- Bin CPS predicted **and** actual effective rates by income band.
- Compare against **IRS SOI 2023** benchmark effective rates by income band.
- Purpose: prove the microdata model tracks real-world published aggregates; gives reviewers a credibility anchor.
- **Two-source discipline:** IRS SOI and CPS are distinct sources. One teammate owns a final pass ensuring no sentence in the writeup or UI blends IRS and CPS numbers.

---

## 7. Deliverable / Finished Product

A **Streamlit demo** where a user enters a filer profile and sees:

1. **Predicted effective rate** for that profile.
2. **Percentile placement** — where this rate sits in the distribution of all filers.
3. **SHAP waterfall** — what pushed this filer's rate up/down.
4. **Twin comparison** — hold income constant, flip one attribute, watch the rate move. *This visual is the equity argument.*
5. *(Stretch)* Plain-language explanation of the finding grounded in IRS publications.

Supporting the UI: the trained model artifact, the validation results against IRS SOI 2023, and a short written findings summary.

---

## 8. Stretch Goals (Optional — Clearly Bounded)

> These are **not required** for a complete, defensible deliverable. The RF + SHAP + twin + validation core stands entirely on its own. Attempt these only after the core ships and the model table is frozen. Each is independent and can be dropped without affecting the core.

### 8.1 Neural Network Benchmark *(stretch)*
- Train a small feed-forward NN on the **same frozen `train.csv`** as a comparison to the Random Forest.
- Framed as a benchmark ("does a NN beat RF on this tabular task?"), **not** as the primary model. RF + SHAP remains the analytical spine regardless of outcome.
- Report the same metrics (R², MAE) side by side with the RF.

### 8.2 RAG Grounding Layer *(stretch)*
- Retrieval over IRS publications / relevant tax-code sections to ground explanations in source text.
- **Hard cap: one week.** It is a grounding layer, not a chatbot. If it slips, drop it — the model and SHAP work stand alone.

### 8.3 LLM Natural-Language Explanation *(stretch)*
- An LLM layer that turns SHAP outputs into plain-language explanations of why a filer's rate landed where it did.
- Depends on SHAP output existing; sits on top of the core, never inside it.

---

## 9. Build Sequence

| Phase | Task | Output | Blocking? |
|---|---|---|---|
| 0 | Sort all 59 `cps_filers_clean.csv` columns → target/feature/optional/quarantine/drop/weight/sensitive (§3.4) | `data_dictionary.md` | — |
| 1 | Filter to filer units (`depstat==0`, §3.2); confirm `eff_rate` target; **reconstruct tax-unit income (§3.2 amendment)**; build income-share features; apply split | clean filer table | — |
| 2 | **Freeze modeling table** (80/20, fixed seed) | `train.csv`, `test.csv` | **Yes — blocks all below** |
| 3 | Train Random Forest; report R², MAE, residuals | model artifact + metrics | after 2 |
| 4 | SHAP `TreeExplainer`: global summary + per-filer waterfall | SHAP outputs | after 3, parallelizable |
| 5 | Twin comparison engine (hold-all-flip-one) | counterfactual module | after 3, parallelizable |
| 6 | Validation loop vs. IRS SOI 2023 | validation report | after 3, parallelizable |
| 7 | Streamlit demo integrating 3–6 | working demo | after 4/5/6 |
| S | Stretch goals (§8) — NN / RAG / LLM | optional add-ons | after 2, independent |

Once Phase 2 is frozen, Phases 4/5/6 and the stretch goals run in parallel across teammates — this is what makes the timeline realistic for a multi-person team.

---

## 10. Top Risks & Mitigations

1. **Data leakage** — a quarantined variable slips into features → invalidates all results. *Mitigation:* §3.3 pile-sort as Phase 0, documented; quarantine anything ambiguous; freeze table before modeling.
2. **Two-source confusion** — IRS and CPS numbers blended in writeup/UI. *Mitigation:* one owner does a final consistency pass (§6).
3. **RAG time sink** — grounding layer expands into a chatbot. *Mitigation:* one-week hard cap; it's droppable (§8.2).
4. **Scope creep on demographics** — the data supports income / filing-status / geography equity, not race/ethnicity. *Mitigation:* lock the demographic framing in Phase 0; revisit only after the core ships.
5. **Confusing the model for the product** — treating accuracy as the goal. *Mitigation:* internalize that the model is the *engine*; faithfulness (leakage-free) matters more than marginal accuracy (§4.3).

---

## 11. Definition of Done (Core)

- [ ] Every column assigned and documented (target / feature / quarantine).
- [ ] Filer-unit table built; `train.csv` / `test.csv` frozen with fixed seed.
- [ ] Random Forest trained; R², MAE, and residual diagnostics reported.
- [ ] SHAP global summary + per-filer waterfall rendering correctly.
- [ ] Twin comparison isolates single-attribute rate gaps.
- [ ] Model validated against IRS SOI 2023 by income band, sources kept distinct.
- [ ] Streamlit demo integrates prediction, percentile, waterfall, and twin comparison.
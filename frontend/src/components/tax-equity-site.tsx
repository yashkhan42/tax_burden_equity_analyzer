"use client";

import { ArrowDown, ArrowUpRight } from "lucide-react";
import { useCallback, useRef, useState } from "react";

import { ProfileForm } from "@/components/profile-form";
import { Reveal } from "@/components/reveal";
import { SiteHeader } from "@/components/site-header";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import {
  ContributionChart,
  PercentileChart,
  TwinComparison,
} from "@/components/visualizations";
import {
  analysisApi,
  ApiError,
  type ContributionResponse,
  type PercentileResponse,
  type PredictResponse,
  type TaxProfile,
  type TwinComparison as TwinComparisonType,
  type TwinResponse,
} from "@/lib/api";

type InitialResults = {
  prediction: PredictResponse;
  percentile: PercentileResponse;
  contribution: ContributionResponse;
};

const comparisonOptions: Array<{
  value: TwinComparisonType;
  label: string;
}> = [
  { value: "filing", label: "How they file" },
  { value: "marital", label: "Whether they are married" },
  { value: "income_source", label: "Where the money comes from" },
  { value: "dependents", label: "Whether children are at home" },
];

function publicError(error: unknown) {
  if (!(error instanceof ApiError)) {
    return "The analysis could not be completed. Please try again.";
  }
  if (error.status === 503) {
    return "The analysis service is not ready yet. Start the local service with the trained analysis available, then try again.";
  }
  if (error.status === 422) {
    return "One of the entries could not be analyzed. Review the form and try again.";
  }
  if (error.code === "network_error") {
    return "We could not reach the analysis service. Make sure the local service is running, then try again.";
  }
  return "The analysis could not be completed. Please try again.";
}

function ChapterHeading({
  title,
}: {
  title: string;
}) {
  return (
    <div className="chapter-heading">
      <h2>{title}</h2>
    </div>
  );
}

export function TaxEquitySite() {
  const [results, setResults] = useState<InitialResults | null>(null);
  const [twin, setTwin] = useState<TwinResponse | null>(null);
  const [committedProfile, setCommittedProfile] =
    useState<TaxProfile | null>(null);
  const [comparison, setComparison] =
    useState<TwinComparisonType>("filing");
  const [loading, setLoading] = useState(false);
  const [twinLoading, setTwinLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [twinError, setTwinError] = useState<string | null>(null);
  const requestRef = useRef<AbortController | null>(null);
  const twinRequestRef = useRef<AbortController | null>(null);
  const resultHeadingRef = useRef<HTMLHeadingElement>(null);

  const loadTwin = useCallback(
    async (profile: TaxProfile, nextComparison: TwinComparisonType) => {
      twinRequestRef.current?.abort();
      const controller = new AbortController();
      twinRequestRef.current = controller;
      setTwinLoading(true);
      setTwinError(null);

      try {
        const nextTwin = await analysisApi.twin(
          profile,
          nextComparison,
          controller.signal,
        );
        setTwin(nextTwin);
      } catch (requestError) {
        if (
          requestError instanceof DOMException &&
          requestError.name === "AbortError"
        ) {
          return;
        }
        setTwin(null);
        setTwinError(publicError(requestError));
      } finally {
        if (twinRequestRef.current === controller) {
          setTwinLoading(false);
        }
      }
    },
    [],
  );

  const submitProfile = useCallback(
    async (profile: TaxProfile) => {
      requestRef.current?.abort();
      twinRequestRef.current?.abort();
      const controller = new AbortController();
      requestRef.current = controller;
      setLoading(true);
      setError(null);
      setTwinError(null);
      setResults(null);
      setTwin(null);

      try {
        const [prediction, percentile, contribution] = await Promise.all([
          analysisApi.predict(profile, controller.signal),
          analysisApi.percentile(profile, controller.signal),
          analysisApi.contribution(profile, controller.signal),
        ]);

        setResults({ prediction, percentile, contribution });
        setCommittedProfile(profile);
        requestAnimationFrame(() => resultHeadingRef.current?.focus());
        void loadTwin(profile, comparison);
      } catch (requestError) {
        if (
          requestError instanceof DOMException &&
          requestError.name === "AbortError"
        ) {
          return;
        }
        setCommittedProfile(null);
        setError(publicError(requestError));
        requestAnimationFrame(() => resultHeadingRef.current?.focus());
      } finally {
        if (requestRef.current === controller) {
          setLoading(false);
        }
      }
    },
    [comparison, loadTwin],
  );

  const changeComparison = (nextComparison: TwinComparisonType) => {
    setComparison(nextComparison);
    if (committedProfile) {
      void loadTwin(committedProfile, nextComparison);
    }
  };

  return (
    <>
      <SiteHeader />
      <main id="top">
        <section className="hero full-bleed" aria-labelledby="hero-title">
          <div className="hero-light" aria-hidden="true" />
          <div className="site-canvas hero-grid">
            <Reveal className="hero-copy">
              <h1 id="hero-title">
                <span>Two filers.</span>
                <span>Same income.</span>
                <span>Different tax.</span>
              </h1>
              <p className="hero-lead">
                Similar filers can face systematically different federal tax
                rates. Hold the surrounding facts still and see where the gap
                appears.
              </p>
              <Button asChild>
                <a href="#analyze">
                  Build a comparison
                  <ArrowDown aria-hidden size={18} />
                </a>
              </Button>
            </Reveal>

            <Reveal className="hero-argument" delay={0.06}>
              <div className="hero-filer">
                <span>Filer A</span>
                <strong>$64,000</strong>
                <small>Annual income</small>
              </div>
              <div className="hero-connector">
                <span />
                <p>One fact changes</p>
                <span />
              </div>
              <div className="hero-filer">
                <span>Filer B</span>
                <strong>$64,000</strong>
                <small>Annual income</small>
              </div>
              <p className="hero-card-close">The predicted rates can diverge.</p>
            </Reveal>
          </div>
          <a className="scroll-cue" href="#argument">
            Read the argument
            <ArrowDown aria-hidden size={16} />
          </a>
        </section>

        <section
          className="thesis full-bleed"
          id="argument"
          aria-labelledby="argument-title"
        >
          <div className="site-canvas thesis-grid">
            <Reveal>
              <h2 id="argument-title">
                The question is not only what one filer pays. It is who pays
                more when the surrounding facts stay the same.
              </h2>
            </Reveal>
            <Reveal className="thesis-note" delay={0.06}>
              <p>
                This site predicts an effective federal tax rate from facts
                known before tax, then separates the strongest contributors
                and compares a carefully matched twin.
              </p>
              <p>
                A negative rate is a legitimate finding. Refundable credits can
                make the amount received larger than the federal tax owed.
              </p>
            </Reveal>
          </div>
        </section>

        <section
          className="analyze-section full-bleed"
          id="analyze"
          aria-labelledby="analyze-title"
        >
          <div className="site-canvas">
            <h2 className="section-title" id="analyze-title">
              Describe the return
            </h2>
            <p className="section-lead">
              Start with four familiar details. The optional section lets you
              describe income sources and household circumstances more closely.
            </p>
            <Card className="form-card">
              <ProfileForm loading={loading} onSubmit={submitProfile} />
            </Card>
          </div>
        </section>

        <section
          aria-busy={loading}
          aria-labelledby="results-title"
          className="results-region"
          id="evidence"
        >
          <h2
            className="sr-only"
            id="results-title"
            ref={resultHeadingRef}
            tabIndex={-1}
          >
            Analysis results
          </h2>

          {loading ? (
            <div className="loading-results full-bleed" role="status">
              <div className="site-canvas">
                <h3 className="status-title">Building the comparison</h3>
                <div className="loading-rule" />
                <p>
                  Predicting the rate, locating it in the reference group, and
                  tracing the strongest contributions.
                </p>
              </div>
            </div>
          ) : null}

          {error ? (
            <div className="result-error full-bleed" role="alert">
              <div className="site-canvas">
                <h3>We could not build this comparison.</h3>
                <p>{error}</p>
                <Button asChild variant="outline">
                  <a href="#analyze">Return to the form</a>
                </Button>
              </div>
            </div>
          ) : null}

          {results ? (
            <>
              <section
                aria-labelledby="prediction-title"
                className="result-chapter prediction-chapter full-bleed"
              >
                <div className="site-canvas chapter-layout">
                  <ChapterHeading
                    title="Your predicted rate"
                  />
                  <Reveal className="prediction-result">
                    <p className="rate-display">{results.prediction.display}</p>
                    <p id="prediction-title">
                      of income is the predicted effective federal tax rate for
                      filers with these characteristics.
                    </p>
                    <p className="result-framing">
                      {results.prediction.framing}
                    </p>
                  </Reveal>
                </div>
              </section>

              <section
                aria-labelledby="percentile-title"
                className="result-chapter full-bleed"
              >
                <div className="site-canvas chapter-layout">
                  <ChapterHeading
                    title="Where this rate sits"
                  />
                  <Reveal className="visualization-surface">
                    <h3 className="sr-only" id="percentile-title">
                      Position among similar filers
                    </h3>
                    <PercentileChart {...results.percentile} />
                  </Reveal>
                </div>
              </section>

              <section
                aria-labelledby="contribution-title"
                className="result-chapter result-chapter-inverted full-bleed"
              >
                <div className="site-canvas chapter-layout">
                  <ChapterHeading
                    title="What shaped the prediction"
                  />
                  <Reveal className="visualization-surface dense-surface">
                    <h3 className="sr-only" id="contribution-title">
                      Strongest contributions to the prediction
                    </h3>
                    <ContributionChart {...results.contribution} />
                  </Reveal>
                </div>
              </section>

              <section
                aria-labelledby="twin-title"
                className="result-chapter twin-chapter full-bleed"
              >
                <div className="site-canvas chapter-layout">
                  <div>
                    <ChapterHeading
                      title="Change one fact"
                    />
                    <label className="comparison-control" htmlFor="comparison">
                      <span>Compare by</span>
                      <select
                        id="comparison"
                        onChange={(event) =>
                          changeComparison(
                            event.target.value as TwinComparisonType,
                          )
                        }
                        value={comparison}
                      >
                        {comparisonOptions.map((option) => (
                          <option key={option.value} value={option.value}>
                            {option.label}
                          </option>
                        ))}
                      </select>
                    </label>
                  </div>
                  <Reveal className="visualization-surface twin-surface">
                    <h3 className="sr-only" id="twin-title">
                      Matched twin comparison
                    </h3>
                    {twinLoading ? (
                      <div className="twin-loading" role="status">
                        Rebuilding the twin comparison
                      </div>
                    ) : twinError ? (
                      <p className="inline-error" role="alert">
                        {twinError}
                      </p>
                    ) : twin ? (
                      <TwinComparison {...twin} />
                    ) : null}
                  </Reveal>
                </div>
              </section>
            </>
          ) : null}
        </section>

        <section
          className="method full-bleed"
          id="method"
          aria-labelledby="method-title"
        >
          <div className="site-canvas method-layout">
            <div>
              <Reveal>
                <h2 id="method-title">A prediction is evidence, not a verdict.</h2>
              </Reveal>
            </div>
            <div className="method-grid">
              <Reveal>
                <h3>Learn from complete returns</h3>
                <p>
                  The analysis finds patterns in survey responses using income,
                  household, filing, and location details known before federal
                  tax is calculated.
                </p>
              </Reveal>
              <Reveal delay={0.06}>
                <h3>Show what shaped the estimate</h3>
                <p>
                  The contribution view shows which parts of the profile moved
                  the estimate above or below a typical prediction. It explains
                  a learned pattern, not a legal tax calculation.
                </p>
              </Reveal>
              <Reveal delay={0.12}>
                <h3>Keep the comparison close</h3>
                <p>
                  The matched comparison changes one detail while keeping the
                  rest of the profile fixed. It reveals a contrast, but does
                  not by itself prove that the changed detail caused it.
                </p>
              </Reveal>
            </div>
            <aside className="limits-card">
              <h3>Read with care</h3>
              <ul>
                <li>
                  Results are estimates learned from survey data, not personal
                  tax advice.
                </li>
                <li>
                  The comparison chart gives each survey example equal weight;
                  it does not claim to represent every filer in the country.
                </li>
                <li>
                  Negative rates remain visible because refundable credits are
                  part of the finding.
                </li>
              </ul>
            </aside>
          </div>
        </section>

        <section className="closing full-bleed" aria-labelledby="closing-title">
          <div className="site-canvas">
            <Reveal>
              <h2 id="closing-title">
                Equity becomes visible when the comparison is close enough to
                be fair.
              </h2>
              <a className="text-link" href="#analyze">
                Build another comparison
                <ArrowUpRight aria-hidden size={18} />
              </a>
            </Reveal>
          </div>
        </section>
      </main>
      <footer className="site-footer">
        <div className="site-canvas">
          <p>Tax burden equity analyzer</p>
          <p>Created as part of AI4ALL Ignite.</p>
        </div>
      </footer>
    </>
  );
}

/**
 * Entry point. One bundle, two worlds:
 *
 *   inside Streamlit — props arrive on the host's render message, height is
 *                      reported back, and the page around us is Streamlit's
 *   standalone       — props come from a JSON fixture chosen by ?fixture=,
 *                      with a mode switch, so the visual can be built and
 *                      reviewed with no Python running at all
 */

import { StrictMode, useState } from "react";
import { createRoot } from "react-dom/client";

import { Contribution } from "./Contribution";
import { Boundary } from "./Boundary";
import { insideStreamlit, useFrameHeight, useStreamlitArgs } from "./frame";
import type { ContributionProps, Mode } from "./contract";

import defaultFixture from "../fixtures/default.json";
import nothingStandsOutFixture from "../fixtures/nothing-stands-out.json";
import dominantFixture from "../fixtures/dominant.json";
import allDownFixture from "../fixtures/all-down.json";
import allUpFixture from "../fixtures/all-up.json";
import extremesFixture from "../fixtures/extremes.json";
import longTextFixture from "../fixtures/long-text.json";
import negativeRatesFixture from "../fixtures/negative-rates.json";

const FIXTURES: Record<string, unknown> = {
  default: defaultFixture,
  "nothing-stands-out": nothingStandsOutFixture,
  dominant: dominantFixture,
  "all-down": allDownFixture,
  "all-up": allUpFixture,
  extremes: extremesFixture,
  "long-text": longTextFixture,
  "negative-rates": negativeRatesFixture,
};

/**
 * Props are validated, not trusted. A malformed payload renders a readable
 * line rather than throwing, because a component that throws inside an iframe
 * leaves the reader looking at nothing at all.
 */
function isContributionProps(value: unknown): value is ContributionProps {
  if (!value || typeof value !== "object") return false;
  const v = value as Record<string, unknown>;
  const tokens = v.tokens as { dark?: unknown; light?: unknown } | undefined;
  const reasons = v.reasons;
  const wellFormed =
    Array.isArray(reasons) &&
    reasons.every(
      (r) =>
        !!r &&
        typeof r === "object" &&
        typeof (r as { text?: unknown }).text === "string" &&
        typeof (r as { points?: unknown }).points === "number",
    );
  return (
    wellFormed &&
    typeof v.baseline === "number" &&
    typeof v.predicted === "number" &&
    !!tokens?.dark &&
    !!tokens?.light
  );
}

function Unavailable() {
  return (
    <p style={{ font: "13px/1.5 system-ui", margin: 0, opacity: 0.75 }}>
      This list could not be drawn. The reasons it would have shown are written
      out in the sentences below it.
    </p>
  );
}

/** The frame-aware shell both worlds mount. */
function Shell({ props }: { props: unknown }) {
  const ref = useFrameHeight<HTMLDivElement>();
  return (
    <div ref={ref}>
      <Boundary>
        {isContributionProps(props) ? <Contribution {...props} /> : <Unavailable />}
      </Boundary>
    </div>
  );
}

function StreamlitEntry() {
  const payload = useStreamlitArgs();
  // Nothing is drawn until the host speaks, but the frame still needs a height
  // or the component would be invisible if the handshake ever stalled.
  if (!payload) return <Shell props={undefined} />;
  return <Shell props={payload.args} />;
}

function StandaloneEntry() {
  const params = new URLSearchParams(window.location.search);
  const requested = params.get("fixture") ?? "default";
  const fixture = (FIXTURES[requested] ?? FIXTURES.default) as ContributionProps;
  const [mode, setMode] = useState<Mode>((params.get("mode") as Mode) ?? fixture.mode);
  const palette = mode === "light" ? fixture.tokens.light : fixture.tokens.dark;

  return (
    <div style={{ minHeight: "100vh", padding: 32, background: palette.background }}>
      <nav
        style={{
          display: "flex",
          gap: 16,
          marginBottom: 28,
          flexWrap: "wrap",
          alignItems: "center",
          font: `12px/1 ${fixture.tokens.fontSans}`,
        }}
      >
        {Object.keys(FIXTURES).map((name) => (
          <a
            key={name}
            href={`?fixture=${name}&mode=${mode}`}
            style={{ color: name === requested ? palette.accent : palette.muted }}
          >
            {name}
          </a>
        ))}
        <button
          onClick={() => setMode(mode === "dark" ? "light" : "dark")}
          style={{ font: "inherit", cursor: "pointer" }}
        >
          {mode === "dark" ? "light" : "dark"} mode
        </button>
      </nav>
      <Shell props={{ ...fixture, mode }} />
    </div>
  );
}

const root = createRoot(document.getElementById("root")!);
root.render(
  <StrictMode>{insideStreamlit() ? <StreamlitEntry /> : <StandaloneEntry />}</StrictMode>,
);

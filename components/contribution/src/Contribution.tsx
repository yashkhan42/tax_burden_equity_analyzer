/**
 * What moved this filer's rate — a ranked reason list with inline magnitude
 * bars (DESIGN_SYSTEM.md §6b). The pattern credit reports and regulated
 * insurance disclosures use, so a general reader has met it before.
 *
 * The reader is not evaluating a model. There is no "feature", no
 * "contribution", no chart literacy assumed: a short list of things, each with
 * a bar showing how far it moved the rate and in which direction.
 *
 * DIRECTION IS ENCODED THREE TIMES (§4), hue last and weakest:
 *   1. position — every bar is drawn from one shared zero rule, left or right
 *   2. sign and word — an explicit + or − on every figure, and a group heading
 *      that names the direction in English
 *   3. hue — `accent` for lowered, `raised` for raised. Never red/green.
 * Remove all colour and the list still reads. That is the test.
 *
 * WHAT THIS COMPONENT NEVER DOES: sort, round to a different precision,
 * filter, threshold, or write a sentence out of a number. Ranking, rounding,
 * thresholding and every fragment of English about the data arrive in props
 * (§8). The only English here is fixed chrome the design owns — the two
 * headings, the two figure labels, the caption, the "everything else together"
 * row and the empty state.
 */

import { useEffect, useLayoutEffect, useRef, useState, type CSSProperties } from "react";
import type { ContributionProps, Mode, Palette, Tokens } from "./contract";

/* ------------------------------------------------------------------ values */

/** §3 — the 8 px grid. Only these steps exist. */
const SPACE = { xs: 8, sm: 16, md: 24, lg: 32 } as const;

/** §2 — the reading scale. Nothing between 20 and 28; nothing off this list. */
const TYPE = {
  figure: 28, // a chapter-title step; the page's one display figure is elsewhere
  body: 16,
  secondary: 14,
  label: 12,
} as const;

/** §7 — two durations, and digits never animate. Only bar widths move. */
const MOTION = "150ms cubic-bezier(.4, 0, .2, 1)";

/** The bar geometry. 8 px bar on the grid, inside a 14 px zero rule. */
const BAR_HEIGHT = 8;
const TRACK_HEIGHT = 14;
const ZERO_WIDTH = 2;
/** A 0.2 point reason must still land as a mark, not as nothing. */
const MIN_BAR = 3;

/** Below this the bar moves under its sentence; above, it sits beside it. */
const NARROW = 560;

/** §5 — tabular lining figures on anything numeric, with the mono stack. */
const numeric = (tokens: Tokens) => ({
  fontFamily: tokens.fontMono,
  fontVariantNumeric: "tabular-nums lining-nums" as const,
});

export const paletteFor = (mode: Mode, tokens: Tokens): Palette =>
  mode === "light" ? tokens.light : tokens.dark;

/**
 * A rate: one decimal, U+2212 for negative, percent sign (§5.2–§5.4).
 * A negative effective rate is a real finding for roughly one filer in eight
 * and is set exactly like a positive one.
 */
export const formatRate = (value: number): string =>
  `${value < 0 ? "−" : ""}${Math.abs(value).toFixed(1)}%`;

/**
 * A magnitude in points: always signed, one decimal, no unit (§5.5 — the unit
 * is stated once, in the caption). Never a percent sign: this is a gap.
 */
export const formatPoints = (value: number): string =>
  `${value < 0 ? "−" : "+"}${Math.abs(value).toFixed(1)}`;

/* ------------------------------------------------------------------- hooks */

/** Width of our own box, not the window: we live in an iframe of unknown size. */
function useNarrow<T extends HTMLElement>() {
  const ref = useRef<T | null>(null);
  const [narrow, setNarrow] = useState(false);

  // Measured before paint: the first frame must already be the right layout,
  // because the height we report to the host is measured from it.
  useLayoutEffect(() => {
    const node = ref.current;
    if (!node) return;
    const measure = () => setNarrow(node.getBoundingClientRect().width < NARROW);
    measure();
    const observer = new ResizeObserver(measure);
    observer.observe(node);
    return () => observer.disconnect();
  }, []);

  return [ref, narrow] as const;
}

/** §7 — reduced motion removes every transition. Nothing here needs motion. */
function useReducedMotion(): boolean {
  const [reduced, setReduced] = useState(false);

  useEffect(() => {
    const query = window.matchMedia("(prefers-reduced-motion: reduce)");
    const apply = () => setReduced(query.matches);
    apply();
    query.addEventListener("change", apply);
    return () => query.removeEventListener("change", apply);
  }, []);

  return reduced;
}

/* -------------------------------------------------------------------- rows */

interface Row {
  text: string;
  points: number;
  /** The "everything else together" row: same geometry, quieter voice. */
  supporting: boolean;
}

/* --------------------------------------------------------------- component */

export function Contribution(props: ContributionProps) {
  const { mode, tokens, baseline, predicted } = props;
  const reasons = Array.isArray(props.reasons) ? props.reasons : [];
  const remainder = props.remainder ?? null;
  const nothingStandsOut = Boolean(props.nothingStandsOut);
  const p = paletteFor(mode, tokens);
  const [ref, narrow] = useNarrow<HTMLDivElement>();
  const reduced = useReducedMotion();

  // The order below is the order given. Splitting by sign groups the list; it
  // drops nothing and reorders nothing inside a group.
  const rows: Row[] = nothingStandsOut
    ? []
    : reasons.map((r) => ({ text: r.text, points: r.points, supporting: false }));

  const closing: Row | null =
    !nothingStandsOut && remainder !== null
      ? { text: "Everything else together", points: remainder, supporting: true }
      : null;

  const drawn = closing ? [...rows, closing] : rows;
  // `nothingStandsOut` is the flag the Python side sets; an empty list with the
  // flag unset would leave the same hole, so it takes the same calm state.
  const empty = nothingStandsOut || drawn.length === 0;

  // One shared zero for every bar in the component, including the closing row.
  // The zero sits where the two directions meet, so a list that only pushes one
  // way spends the whole track on that way instead of half of it.
  const maxUp = drawn.reduce((m, r) => (r.points > 0 ? Math.max(m, r.points) : m), 0);
  const maxDown = drawn.reduce((m, r) => (r.points < 0 ? Math.max(m, -r.points) : m), 0);
  const span = maxUp + maxDown;
  const zeroPct = span > 0 ? (maxDown / span) * 100 : 50;
  const lengthPct = (points: number) => (span > 0 ? (Math.abs(points) / span) * 100 : 0);

  const up = rows.filter((r) => r.points > 0);
  const down = rows.filter((r) => r.points < 0);
  // The largest reason leads, so the list still reads biggest-first across the
  // two headings. `reasons` is pre-sorted by absolute size, so it is row one.
  const upFirst = rows.length > 0 ? rows[0].points > 0 : true;

  const groups = (upFirst
    ? [
        { heading: "Pushed the rate up", colour: p.raised, rows: up },
        { heading: "Pushed it down", colour: p.accent, rows: down },
      ]
    : [
        { heading: "Pushed it down", colour: p.accent, rows: down },
        { heading: "Pushed the rate up", colour: p.raised, rows: up },
      ]
  ).filter((g) => g.rows.length > 0);

  return (
    <div
      ref={ref}
      style={{
        background: p.background,
        color: p.ink,
        fontFamily: tokens.fontSans,
        padding: "4px 0 8px",
      }}
    >
      {/* The frame. §6b: a ranked additive list asserts an independence the
          underlying values do not have, which is why the baseline is stated
          explicitly rather than left implied by the bars. */}
      <div style={{ display: "flex", flexWrap: "wrap", gap: SPACE.lg }}>
        <Figure label="A typical filer pays" value={baseline} p={p} tokens={tokens} />
        <Figure label="This filer pays" value={predicted} p={p} tokens={tokens} />
      </div>
      <p
        style={{
          margin: `${SPACE.xs}px 0 0`,
          maxWidth: "60ch",
          fontSize: TYPE.label,
          lineHeight: 1.33,
          color: p.muted,
        }}
      >
        {empty
          ? "As a share of income."
          : "As a share of income. Everything below is measured in percentage points of that rate."}
      </p>

      {empty ? (
        // §6b degradation: an explicit, calm state in words — never five
        // indistinguishable stubs pretending to be findings.
        <p
          style={{
            margin: `${SPACE.lg}px 0 0`,
            maxWidth: "60ch",
            fontSize: TYPE.body,
            lineHeight: 1.5,
            color: p.ink,
          }}
        >
          Nothing about this filer stands out; their rate is close to what a
          typical filer pays.
        </p>
      ) : (
        <>
          {groups.map((group) => (
            <section key={group.heading} style={{ marginTop: SPACE.lg }}>
              <h3
                style={{
                  margin: `0 0 ${SPACE.sm}px`,
                  fontSize: TYPE.label,
                  lineHeight: 1.33,
                  fontWeight: 400,
                  color: group.colour,
                }}
              >
                {group.heading}
              </h3>
              <div style={{ display: "flex", flexDirection: "column", gap: SPACE.sm }}>
                {group.rows.map((row, i) => (
                  <ReasonRow
                    key={`${row.text}-${i}`}
                    row={row}
                    zeroPct={zeroPct}
                    lengthPct={lengthPct(row.points)}
                    colour={row.points < 0 ? p.accent : p.raised}
                    p={p}
                    tokens={tokens}
                    narrow={narrow}
                    reduced={reduced}
                  />
                ))}
              </div>
            </section>
          ))}

          {/* §6b: more than five are truncated with the remainder summed into
              one final row, never silently dropped. */}
          {closing && (
            <div
              style={{
                marginTop: SPACE.md,
                paddingTop: SPACE.sm,
                borderTop: `1px solid ${p.hairline}`,
              }}
            >
              <ReasonRow
                row={closing}
                zeroPct={zeroPct}
                lengthPct={lengthPct(closing.points)}
                colour={closing.points < 0 ? p.accent : p.raised}
                p={p}
                tokens={tokens}
                narrow={narrow}
                reduced={reduced}
              />
            </div>
          )}
        </>
      )}

      {props.isPlaceholder && (
        <p
          style={{
            margin: `${SPACE.md}px 0 0`,
            fontSize: TYPE.label,
            lineHeight: 1.33,
            color: p.muted,
          }}
        >
          These figures are placeholders.
        </p>
      )}
    </div>
  );
}

/* ----------------------------------------------------------------- pieces */

/** One framing rate: a quiet label above a tabular figure. */
function Figure(props: { label: string; value: number; p: Palette; tokens: Tokens }) {
  return (
    <div>
      <div
        style={{
          fontSize: TYPE.label,
          lineHeight: 1.33,
          color: props.p.muted,
          marginBottom: SPACE.xs,
        }}
      >
        {props.label}
      </div>
      <div
        style={{
          ...numeric(props.tokens),
          fontSize: TYPE.figure,
          lineHeight: 1.2,
          color: props.p.ink,
        }}
      >
        {formatRate(props.value)}
      </div>
    </div>
  );
}

/**
 * One reason: sentence, bar, figure.
 *
 * Wide, the three sit in a grid so every bar shares one x-origin and a
 * sentence that wraps to three lines cannot shift its neighbours' bars.
 * Narrow, the bar drops under its sentence — still full width, still one
 * shared zero, so the alignment that carries the direction survives.
 */
function ReasonRow(props: {
  row: Row;
  zeroPct: number;
  lengthPct: number;
  colour: string;
  p: Palette;
  tokens: Tokens;
  narrow: boolean;
  reduced: boolean;
}) {
  const { row, p, tokens, narrow } = props;

  const sentence = (
    <div
      style={{
        fontSize: TYPE.body,
        lineHeight: 1.5,
        color: row.supporting ? p.muted : p.ink,
        maxWidth: "60ch",
        overflowWrap: "anywhere",
      }}
    >
      {row.text}
    </div>
  );

  const track = (
    <Track
      points={row.points}
      zeroPct={props.zeroPct}
      lengthPct={props.lengthPct}
      colour={props.colour}
      p={p}
      radius={tokens.radius}
      reduced={props.reduced}
    />
  );

  const figure = (
    <div
      style={{
        ...numeric(tokens),
        fontSize: TYPE.body,
        lineHeight: 1.5,
        textAlign: "right",
        color: row.supporting ? p.muted : p.ink,
      }}
    >
      {formatPoints(row.points)}
    </div>
  );

  if (narrow) {
    return (
      <div>
        {sentence}
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "minmax(0, 1fr) 4rem",
            columnGap: SPACE.sm,
            alignItems: "center",
            marginTop: SPACE.xs,
          }}
        >
          {track}
          {figure}
        </div>
      </div>
    );
  }

  // The bar is nudged onto the optical centre of the sentence's first line:
  // a 24 px line box (16 px × 1.5) around a 14 px track.
  const firstLineOffset = (TYPE.body * 1.5 - TRACK_HEIGHT) / 2;

  return (
    <div
      style={{
        display: "grid",
        // The sentence column stops at the 60-character measure (§2) and the
        // track is a proportion of the row, floored so a bar is always a bar
        // and capped so a wide host cannot open a dead gap between a sentence
        // and the bar that belongs to it (§3).
        gridTemplateColumns: "minmax(0, 60ch) clamp(96px, 34%, 320px) 4rem",
        columnGap: SPACE.sm,
        alignItems: "start",
      }}
    >
      {sentence}
      <div style={{ marginTop: firstLineOffset }}>{track}</div>
      {figure}
    </div>
  );
}

/**
 * The magnitude bar. Position is the strongest of the three direction cues, so
 * the zero rule is drawn as a mark that must be read (`shape`, not `hairline`)
 * and every bar in the component starts from it.
 */
function Track(props: {
  points: number;
  zeroPct: number;
  lengthPct: number;
  colour: string;
  p: Palette;
  radius: number;
  reduced: boolean;
}) {
  const { zeroPct, lengthPct, points, radius } = props;
  // Keep the zero rule inside the track at both ends: at 0% it sits flush
  // left, at 100% flush right, and in between it straddles the position.
  const shift = (zeroPct / 100) * ZERO_WIDTH;

  const bar: CSSProperties =
    points < 0
      ? {
          right: `${100 - zeroPct}%`,
          marginRight: shift,
          borderRadius: `${radius}px 0 0 ${radius}px`,
        }
      : {
          left: `${zeroPct}%`,
          marginLeft: ZERO_WIDTH - shift,
          borderRadius: `0 ${radius}px ${radius}px 0`,
        };

  return (
    <div
      aria-hidden="true"
      style={{ position: "relative", height: TRACK_HEIGHT, overflow: "hidden" }}
    >
      <div
        style={{
          position: "absolute",
          top: 0,
          bottom: 0,
          left: `${zeroPct}%`,
          marginLeft: -shift,
          width: ZERO_WIDTH,
          background: props.p.shape,
        }}
      />
      <div
        style={{
          position: "absolute",
          top: (TRACK_HEIGHT - BAR_HEIGHT) / 2,
          height: BAR_HEIGHT,
          // The 2 px taken back is the width of the zero rule the bar starts
          // beside; minWidth keeps a 0.2 point reason visible as a mark.
          width: `calc(${lengthPct}% - ${ZERO_WIDTH}px)`,
          minWidth: MIN_BAR,
          background: props.colour,
          transition: props.reduced ? undefined : `width ${MOTION}`,
          ...bar,
        }}
      />
    </div>
  );
}

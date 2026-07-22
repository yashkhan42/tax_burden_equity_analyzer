/**
 * The twin comparison — design/DESIGN_SYSTEM.md §6c, implemented.
 *
 * Two identically-formatted cards with the gap between them. Each card lists
 * the same attributes in the same order; everything the two filers share is
 * set in `muted`, and the one attribute that differs is lifted into `ink`.
 * Below them sits the gap: the difference in points, a dumbbell whose
 * CONNECTOR is the heaviest mark on the page, and one line of money.
 *
 * The reason for the cards, and it is the whole argument: a chart of two dots
 * shows that two numbers differ. It does not show that everything else was
 * held constant, which is the premise the equity claim rests on. The sameness
 * has to be visible, so it is drawn twice, in full, in grey.
 *
 * Every size, colour and spacing step below is quoted from the design system,
 * with the section noted. Nothing here is invented; where the system was
 * silent the nearest existing token was used and the choice is commented.
 */

import { useEffect, useState } from "react";

import type { Mode, Palette, TwinAttribute, TwinProps, TwinSide } from "./contract";

/* ------------------------------------------------------------------ tokens */

/** §2. The only type steps this component uses. Numbers never leave 28. */
const TYPE = {
  /** Every figure here. §1: only the page's headline rate is display-sized. */
  figure: { size: 28, leading: 1.2 },
  /** §2 secondary body — every sentence and every shared value. */
  body: { size: 14, leading: 1.45 },
  /** §2 label/caption/axis. */
  label: { size: 12, leading: 1.33 },
} as const;

/** §7. One duration, because only marks move and only between two states. */
const MOVE = "150ms cubic-bezier(.4, 0, .2, 1)";

/**
 * §5.2 — a gap is reported to one decimal, so a gap that rounds to 0.0 is not
 * a difference we are entitled to draw. This is the near-zero trip, and it is
 * derived from the reporting precision rather than picked.
 */
const NEAR_ZERO = 0.05;

/** §5.1 — on every numeric element, not just the mono ones. */
const TABULAR = "tabular-nums lining-nums" as const;

/* ----------------------------------------------------------------- helpers */

/**
 * §5.2 one decimal, §5.3 U+2212 for the minus.
 *
 * A fallback only: `TwinSide.display` arrives pre-formatted and is preferred.
 * This exists so a payload that predates the `display` field still renders a
 * legible figure rather than `undefined`.
 */
export const formatRate = (rate: number): string =>
  `${rate < 0 ? "−" : ""}${Math.abs(rate).toFixed(1)}%`;

/** §5.4 — a gap is "1.6 points". Unsigned; the sentence carries direction. */
export const formatGap = (points: number): string => Math.abs(points).toFixed(1);

export const paletteFor = (mode: Mode, tokens: TwinProps["tokens"]): Palette =>
  mode === "light" ? tokens.light : tokens.dark;

/**
 * `changed` is written for the middle of a sentence ("Changing how they file"),
 * but the cards also use it as a row label beside "Income" and "Age". Raising
 * the first letter is the whole of the transformation; no words are chosen
 * here. See the report: the contract should carry both forms.
 */
const asLabel = (text: string): string =>
  text.length === 0 ? text : text[0].toUpperCase() + text.slice(1);

/** §7 — `prefers-reduced-motion: reduce` removes all transitions. */
function useReducedMotion(): boolean {
  const [reduced, setReduced] = useState(false);
  useEffect(() => {
    const query = window.matchMedia?.("(prefers-reduced-motion: reduce)");
    if (!query) return;
    setReduced(query.matches);
    const onChange = () => setReduced(query.matches);
    query.addEventListener("change", onChange);
    return () => query.removeEventListener("change", onChange);
  }, []);
  return reduced;
}

/**
 * The dumbbell's scale.
 *
 * The domain is derived from the two rates but ALWAYS contains zero, which is
 * what keeps the picture honest: the connector's length is the gap measured
 * against the distance from zero, and zero is drawn, so a reader can see how
 * much of the rate the gap actually is. A domain padded around the pair alone
 * would render every gap at the same length, which would say nothing.
 */
function scaleFor(a: number, b: number) {
  const low = Math.min(a, b, 0);
  const high = Math.max(a, b, 0);
  // 12% of the span each side so an endpoint never sits on the axis end.
  // The 0.5 floor keeps the domain finite when both rates are zero.
  const pad = Math.max((high - low) * 0.12, 0.5);
  const min = low - pad;
  const max = high + pad;
  return (value: number): number => ((value - min) / (max - min)) * 100;
}

/* ------------------------------------------------------------------- twin */

export function Twin(props: TwinProps) {
  const { mode, tokens, changed, a, b, gapMoney, isPlaceholder } = props;
  const p = paletteFor(mode, tokens);
  const reduced = useReducedMotion();

  // Defensive reads. `main.tsx` validates the shape it can afford to validate;
  // a payload missing an optional field must still draw rather than throw.
  const shared: TwinAttribute[] = Array.isArray(props.shared) ? props.shared : [];
  const gapPoints =
    typeof props.gapPoints === "number" ? props.gapPoints : b.rate - a.rate;

  const isNearZero = Math.abs(gapPoints) < NEAR_ZERO;
  // "One pays, one is paid" is a different claim from "one pays more" (§6c).
  const crossesZero = Math.min(a.rate, b.rate) < 0 && Math.max(a.rate, b.rate) > 0;

  const at = scaleFor(a.rate, b.rate);
  const [low, high] = a.rate <= b.rate ? [a, b] : [b, a];
  const lowAt = at(low.rate);
  const highAt = at(high.rate);
  const zeroAt = at(0);

  // The stretch of the axis both filers have in common: zero to whichever of
  // them sits nearer zero. When they straddle zero there is no common stretch,
  // which is the visual half of "one pays, one is paid".
  const sameSign = (a.rate >= 0) === (b.rate >= 0);
  const commonAt = sameSign ? (a.rate >= 0 ? lowAt : highAt) : null;

  /** §4 — direction is named in English, not left to a hue. */
  const lead = isNearZero
    ? `Changing ${changed} leaves essentially the same rate.`
    : `Changing ${changed} ${gapPoints > 0 ? "raises" : "lowers"} the effective rate by`;

  return (
    <div
      style={{
        background: p.background,
        color: p.ink,
        fontFamily: tokens.fontSans,
        fontSize: TYPE.body.size,
        lineHeight: TYPE.body.leading,
      }}
    >
      {/* The two cards. `flex-wrap` with a 260px basis is the whole responsive
          story: side by side above roughly 560px, stacked below it, with no
          media query and so no CSS file. */}
      <div style={{ display: "flex", flexWrap: "wrap", gap: 24, alignItems: "stretch" }}>
        <Card side={a} changed={changed} shared={shared} palette={p} tokens={tokens} />
        <Card side={b} changed={changed} shared={shared} palette={p} tokens={tokens} />
      </div>

      {/* The gap. §3: 32px between blocks inside a chapter, on both sides of
          the rule, because this is the finding and it gets the air. */}
      <div
        style={{
          marginTop: 32,
          paddingTop: 32,
          borderTop: `1px solid ${p.hairline}`,
        }}
      >
        {/* §4: the sentence above the figure names the direction.
            §2: measure capped at 60 characters. */}
        <p style={{ margin: 0, color: p.muted, maxWidth: "60ch" }}>{lead}</p>

        {/* §3: 16px between a figure and its sentence — the sentence belongs
            to the figure. §5.4: a gap is in points, never in per cent. */}
        <div style={{ display: "flex", alignItems: "baseline", gap: 8, marginTop: 16 }}>
          <span
            style={{
              fontFamily: tokens.fontMono,
              fontSize: TYPE.figure.size,
              lineHeight: TYPE.figure.leading,
              color: p.ink,
              fontVariantNumeric: TABULAR,
            }}
          >
            {formatGap(gapPoints)}
          </span>
          <span style={{ color: p.muted }}>points</span>
        </div>

        <Dumbbell
          palette={p}
          tokens={tokens}
          low={low}
          high={high}
          lowAt={lowAt}
          highAt={highAt}
          zeroAt={zeroAt}
          commonAt={commonAt}
          collapsed={isNearZero}
          crossesZero={crossesZero}
          reduced={reduced}
        />

        {/* §6c: the explicit second claim, only when the pair straddles zero. */}
        {crossesZero ? (
          <p style={{ margin: "16px 0 0", color: p.muted, maxWidth: "60ch" }}>
            One pays; the other is paid.
          </p>
        ) : null}

        {/* One line of money translation, rendered exactly as it arrives.
            §5.7's rounding and hedging happen in Python, never here. */}
        {gapMoney ? (
          <p
            style={{
              margin: `${crossesZero ? 8 : 16}px 0 0`,
              color: p.muted,
              maxWidth: "60ch",
              fontVariantNumeric: TABULAR,
            }}
          >
            {gapMoney}
          </p>
        ) : null}

        {isPlaceholder ? (
          <p
            style={{
              margin: "24px 0 0",
              color: p.muted,
              fontSize: TYPE.label.size,
              lineHeight: TYPE.label.leading,
              maxWidth: "60ch",
            }}
          >
            These figures are placeholders.
          </p>
        ) : null}
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------- card */

/**
 * One filer. The two cards differ in exactly one row, and that row is first,
 * so a reader who scans down either card meets the difference immediately and
 * then reads four identical greys.
 */
function Card(props: {
  side: TwinSide;
  changed: string;
  shared: TwinAttribute[];
  palette: Palette;
  tokens: TwinProps["tokens"];
}) {
  const { side, changed, shared, palette: p, tokens } = props;

  return (
    <div
      style={{
        // flex-basis 260px: two cards fit above ~545px, one below it. The
        // basis has to include the padding or the wrap point lands 100px late,
        // and the host page ships no CSS reset to assume one.
        boxSizing: "border-box",
        flex: "1 1 260px",
        // Without this a flex item refuses to shrink past its content and a
        // long unbroken value would push the card out of the frame.
        minWidth: 0,
        background: p.surface,
        border: `1px solid ${p.hairline}`,
        borderRadius: tokens.radius,
        padding: 24, // §3 — inside a bordered surface.
      }}
    >
      <Row
        label={asLabel(changed)}
        value={side.label}
        palette={p}
        // The one thing that differs: lifted into ink, and the single place
        // §2 allows weight to carry hierarchy — 14/600 against 14/400.
        distinct
      />

      {shared.map((attribute) => (
        <Row
          key={attribute.label}
          label={attribute.label}
          value={attribute.value}
          palette={p}
        />
      ))}

      <div
        style={{
          marginTop: 24,
          paddingTop: 24,
          borderTop: `1px solid ${p.hairline}`,
        }}
      >
        <div
          style={{
            fontSize: TYPE.label.size,
            lineHeight: TYPE.label.leading,
            color: p.muted,
          }}
        >
          Effective rate
        </div>
        <div
          style={{
            fontFamily: tokens.fontMono,
            fontSize: TYPE.figure.size,
            lineHeight: TYPE.figure.leading,
            color: p.ink,
            // §5.1 — the two rates must align on the decimal across the gutter.
            fontVariantNumeric: TABULAR,
            marginTop: 8,
          }}
        >
          {side.display ?? formatRate(side.rate)}
        </div>
      </div>
    </div>
  );
}

function Row(props: {
  label: string;
  value: string;
  palette: Palette;
  distinct?: boolean;
}) {
  const { label, value, palette: p, distinct } = props;
  return (
    <div style={{ marginBottom: 16 }}>
      <div
        style={{
          fontSize: TYPE.label.size,
          lineHeight: TYPE.label.leading,
          color: p.muted,
        }}
      >
        {label}
      </div>
      <div
        style={{
          fontSize: TYPE.body.size,
          lineHeight: TYPE.body.leading,
          color: distinct ? p.ink : p.muted,
          fontWeight: distinct ? 600 : 400,
          fontVariantNumeric: TABULAR,
          // §2 — measure capped at 60 characters, which only bites on a wide
          // host column; below that the card is the narrower constraint.
          maxWidth: "60ch",
          // Long values wrap; nothing overflows the card.
          overflowWrap: "anywhere",
          // Two lines reserved on the one row whose height can differ between
          // the cards, so every row below it still lines up across the gutter.
          // Sameness that does not align is not visible as sameness.
          minHeight: distinct ? Math.round(TYPE.body.size * TYPE.body.leading * 2) : undefined,
        }}
      >
        {value}
      </div>
    </div>
  );
}

/* --------------------------------------------------------------- dumbbell */

/**
 * Two dots joined by a connector, on an axis that always contains zero.
 *
 * The connector is the heaviest mark: 8px of `ink`, the highest-contrast
 * colour in either palette. The endpoints are 12px of `shape` sitting on top
 * of it — present, locatable, and quieter than the distance between them.
 *
 * The zero marker is `shape`, never `hairline`: §4 forbids hairline from
 * carrying meaning, and zero here is meaning, not structure. It is drawn over
 * the connector so that a gap which straddles zero is visibly cut by it.
 */
function Dumbbell(props: {
  palette: Palette;
  tokens: TwinProps["tokens"];
  low: TwinSide;
  high: TwinSide;
  lowAt: number;
  highAt: number;
  zeroAt: number;
  commonAt: number | null;
  collapsed: boolean;
  crossesZero: boolean;
  reduced: boolean;
}) {
  const {
    palette: p,
    tokens,
    low,
    high,
    lowAt,
    highAt,
    zeroAt,
    commonAt,
    collapsed,
    crossesZero,
    reduced,
  } = props;

  const TRACK = 24; // the row the marks live on
  const CONNECTOR = 8; // §3 grid — the heaviest mark in the component
  const COMMON = 4; // half the connector, and still on the grid
  const DOT = 12;
  const move = reduced ? undefined : `left ${MOVE}, width ${MOVE}`;

  const endLabel = {
    position: "absolute" as const,
    top: 0,
    whiteSpace: "nowrap" as const,
    fontFamily: tokens.fontMono,
    fontSize: TYPE.label.size,
    lineHeight: TYPE.label.leading,
    color: p.muted,
    fontVariantNumeric: TABULAR,
    transition: reduced ? undefined : `left ${MOVE}`,
  };

  return (
    <div
      style={{
        // §3 — 24px between the figure and the picture that restates it.
        marginTop: 24,
        // The end labels splay outward from their dots; this is the room they
        // need at 380px, so nothing clips at any width.
        padding: "0 32px",
      }}
    >
      {/* Zero always names itself. §2: 12px muted label. */}
      <div style={{ position: "relative", height: 16, marginBottom: 8 }}>
        <span
          style={{
            position: "absolute",
            left: `${zeroAt}%`,
            transform: "translateX(-50%)",
            whiteSpace: "nowrap",
            fontSize: TYPE.label.size,
            lineHeight: TYPE.label.leading,
            color: p.muted,
            transition: reduced ? undefined : `left ${MOVE}`,
          }}
        >
          zero
        </span>
      </div>

      <div style={{ position: "relative", height: TRACK }}>
        {/* The stretch both filers have in common, from zero to whichever of
            them is nearer it. `shape` at half the connector's weight: it has
            to be read, and it must never compete with the connector.
            There is no axis rule behind it — every mark on this track carries
            meaning, and a decorative full-width line would only dilute them. */}
        {commonAt !== null ? (
          <div
            style={{
              position: "absolute",
              left: `${Math.min(zeroAt, commonAt)}%`,
              width: `${Math.abs(commonAt - zeroAt)}%`,
              top: (TRACK - COMMON) / 2,
              height: COMMON,
              borderRadius: COMMON / 2,
              background: p.shape,
              transition: move,
            }}
          />
        ) : null}

        {/* The connector — the finding. Suppressed when the gap rounds to 0.0,
            because a two-pixel bar would imply a difference that is not there. */}
        {!collapsed ? (
          <div
            style={{
              position: "absolute",
              left: `${lowAt}%`,
              width: `${highAt - lowAt}%`,
              top: (TRACK - CONNECTOR) / 2,
              height: CONNECTOR,
              borderRadius: CONNECTOR / 2,
              background: p.ink,
              transition: move,
            }}
          />
        ) : null}

        {/* Endpoints. Identical to each other: same person, one fact apart. */}
        {(collapsed ? [(lowAt + highAt) / 2] : [lowAt, highAt]).map((position, index) => (
          <div
            key={index}
            style={{
              position: "absolute",
              left: `${position}%`,
              top: (TRACK - DOT) / 2,
              width: DOT,
              height: DOT,
              marginLeft: -DOT / 2,
              borderRadius: DOT / 2,
              // Collapsed, there is no connector to sit on, so the single mark
              // takes the connector's weight rather than disappearing.
              background: collapsed ? p.ink : p.shape,
              transition: reduced ? undefined : `left ${MOVE}`,
            }}
          />
        ))}

        {/* Zero, over the connector so a straddling gap is seen to cross it. */}
        <div
          style={{
            position: "absolute",
            left: `${zeroAt}%`,
            top: crossesZero ? -4 : 4,
            width: crossesZero ? 2 : 1,
            height: crossesZero ? TRACK + 8 : TRACK - 8,
            marginLeft: crossesZero ? -1 : 0,
            background: p.shape,
            transition: reduced ? undefined : `left ${MOVE}`,
          }}
        />

      </div>

      {/* Each endpoint's rate, on its own row so no label ever sits on a mark,
          and splayed outward from its dot so the two can never collide however
          close together the dots are. The strings are the ones the cards show
          at 28px, which is what ties a dot back to a card. */}
      <div style={{ position: "relative", height: 16, marginTop: 8 }}>
        <span
          style={{
            ...endLabel,
            left: `${lowAt}%`,
            transform: `translateX(calc(-100% - ${DOT}px))`,
          }}
        >
          {low.display ?? formatRate(low.rate)}
        </span>
        <span
          style={{
            ...endLabel,
            left: `${highAt}%`,
            transform: `translateX(${DOT}px)`,
          }}
        >
          {high.display ?? formatRate(high.rate)}
        </span>
      </div>
    </div>
  );
}

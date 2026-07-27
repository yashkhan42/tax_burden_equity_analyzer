/**
 * The data contract for the twin comparison.
 *
 * This file mirrors `design/DESIGN_SYSTEM.md` §8 exactly. If the two disagree,
 * the design system is right and this file is the defect.
 *
 * Two rules govern everything that crosses this boundary:
 *
 * 1. Everything is shaped for DISPLAY. No model column names, no codes, no
 *    internal identifiers. Every string arrives as finished English written on
 *    the Python side; this component never maps a code to a word, because it
 *    does not know any codes. Rounding, money formatting and unit words are
 *    decided in Python too — §5 of the design system lives there, not here.
 * 2. The component is renderable from a JSON fixture with no Python running.
 *    Anything the visual needs must be in these props.
 */

/** One palette. Both modes are authored independently; neither is derived. */
export interface Palette {
  /** Page ground. Matches the Streamlit theme behind the iframe exactly. */
  background: string;
  /** A raised block; the dense-figure scope of §1. */
  surface: string;
  /** Body text and the headline figure — the highest-contrast ink. */
  ink: string;
  /** Labels, captions, axes, supporting text. */
  muted: string;
  /** Rules and borders. Never carries meaning. */
  hairline: string;
  /** Neutral fills that must be read. Carries no direction. */
  shape: string;
  /** The reader's own value, and "lowered". */
  accent: string;
  /** "Raised the rate", and nothing else. */
  raised: string;
}

export interface Tokens {
  fontSans: string;
  fontMono: string;
  fontSerif: string;
  /** Radius in px, mirroring the shell's baseRadius. */
  radius: number;
  light: Palette;
  dark: Palette;
}

export type Mode = "dark" | "light";

/** One row of the identical attribute list both cards carry. */
export interface TwinAttribute {
  /** e.g. "Income" — sentence case, already written for a reader. */
  label: string;
  /** e.g. "$64,000 a year, mostly from a paycheck". */
  value: string;
}

/** One side of the comparison. */
export interface TwinSide {
  /** e.g. "filing alone". Finished English, never a code. */
  label: string;
  /** Effective rate in points. Negative is legitimate — about 12% of filers. */
  rate: number;
  /** Pre-formatted, e.g. "8.6%". The component never rounds. */
  display: string;
}

export interface TwinProps {
  mode: Mode;
  tokens: Tokens;
  /** What differs, in English: "how they file". */
  changed: string;
  /** The filer as described. */
  a: TwinSide;
  /** The same filer with exactly one thing changed. */
  b: TwinSide;
  /** Held constant, shown identically on both cards, in display order. */
  shared: TwinAttribute[];
  /**
   * Signed gap in points, pre-rounded to one decimal.
   *
   * Sign convention: `b.rate - a.rate`, so a positive gap means changing the
   * one attribute RAISES the rate. The component reads the sign for the
   * direction word and renders the magnitude unsigned (§5.4: a gap is
   * "1.6 points"); the direction is carried by the sentence, per §4.
   */
  gapPoints: number;
  /**
   * Pre-formatted money translation of the gap, or null when it would mislead.
   *
   * A complete, ready-to-render clause — §5.7 requires the "roughly"/"about"
   * hedge and the rounding to a magnitude, and both of those are Python's job.
   * e.g. "About $1,000 a year at this income."
   */
  gapMoney: string | null;
  /** True while the model is a placeholder. */
  isPlaceholder: boolean;
}

/** Props as they arrive from Streamlit, before validation. */
export type MaybeTwinProps = Partial<TwinProps> | undefined;

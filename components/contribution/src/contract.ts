/**
 * The data contract for the contribution list. Mirrors
 * `design/DESIGN_SYSTEM.md` §8 exactly.
 *
 * Two rules hold and are not up for negotiation:
 *
 * 1. Everything crossing this boundary is shaped for DISPLAY. `text` arrives
 *    as finished English written on the Python side; this component never maps
 *    a model feature to a word, because it does not know any features.
 * 2. Ranking, rounding, filtering and thresholding all happen before the
 *    boundary. `reasons` arrives at most five long, already sorted by absolute
 *    size, already rounded to one decimal. The component renders the order it
 *    is given and never reorders, drops or re-rounds a value.
 */

/** One palette. Both modes are authored independently; neither is derived. */
export interface Palette {
  /** Page ground. Matches the Streamlit theme behind the iframe exactly. */
  background: string;
  /** Raised surface, for anything that sits on the ground. */
  surface: string;
  /** Primary figures and headline text — the highest-contrast ink. */
  ink: string;
  /** Supporting labels, axes, captions. */
  muted: string;
  /** Structural lines only. Never carries meaning. */
  hairline: string;
  /** Neutral fills that must be read — here, the zero rule. */
  shape: string;
  /** The reader's own value, and "lowered". */
  accent: string;
  /** Second hue: only ever "this raised the rate". */
  raised: string;
}

export interface Tokens {
  fontSans: string;
  fontMono: string;
  /** Present in design/tokens.json; this component sets no serif type. */
  fontSerif?: string;
  /** Radius in px, mirroring the shell's baseRadius. */
  radius: number;
  light: Palette;
  dark: Palette;
}

export type Mode = "dark" | "light";

/** One row of the list. */
export interface Reason {
  /** A sentence fragment: "having two children at home". Never a code. */
  text: string;
  /** Signed, in percentage points, pre-rounded to one decimal. */
  points: number;
}

export interface ContributionProps {
  mode: Mode;
  tokens: Tokens;
  /** What a typical filer pays, in points — where the bars start from. */
  baseline: number;
  /** Where this filer ended up, in points. Negative is legitimate. */
  predicted: number;
  /** At most five, pre-sorted by absolute size, pre-filtered. */
  reasons: Reason[];
  /** Everything below the threshold, summed. Null when there is none. */
  remainder: number | null;
  /** True when nothing cleared the threshold: render the calm empty state. */
  nothingStandsOut: boolean;
  /** True while the model is a placeholder, so the component can say so. */
  isPlaceholder: boolean;
}

/** Props as they arrive from Streamlit, before validation. */
export type MaybeContributionProps = Partial<ContributionProps> | undefined;

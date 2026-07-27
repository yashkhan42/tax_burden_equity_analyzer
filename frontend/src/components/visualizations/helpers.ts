import type {
  ContributionResponse,
  DistributionBin,
  Reason,
  TwinResponse,
} from "./types";

const ZERO_HALF_WIDTH = 0.6;
const ZERO_GAP = 0.35;
const ZERO_EDGE = ZERO_HALF_WIDTH + ZERO_GAP;
const PRINTED_ZERO = 0.05;

const finite = (value: number, fallback = 0): number =>
  Number.isFinite(value) ? value : fallback;

const closeTo = (a: number, b: number): boolean =>
  Math.abs(a - b) < Number.EPSILON * 16;

export const formatRate = (value: number): string => {
  const safe = finite(value);
  return `${safe < 0 ? "−" : ""}${Math.abs(safe).toFixed(1)}%`;
};

export const formatSignedPoints = (value: number): string => {
  const safe = finite(value);
  return `${safe < 0 ? "−" : "+"}${Math.abs(safe).toFixed(1)}`;
};

export const formatPointMagnitude = (value: number): string =>
  Math.abs(finite(value)).toFixed(1);

export const formatAxisNumber = (value: number): string => {
  const safe = finite(value);
  return `${safe < 0 ? "−" : ""}${Math.abs(safe).toFixed(0)}`;
};

export const clamp = (value: number, low: number, high: number): number =>
  Math.min(Math.max(value, low), high);

export interface PreparedPercentileBin {
  start: number;
  end: number;
  share: number;
  exactZero: boolean;
}

/**
 * Carves the exact-zero point mass out of the ordinary fixed-width bin.
 * This keeps "owed nothing" separate without double-counting any filer.
 */
export function preparePercentileBins(
  bins: readonly DistributionBin[],
  binWidth: number,
  shareExactlyZero: number,
): PreparedPercentileBin[] {
  const width = finite(binWidth);
  if (width <= 0) return [];

  const zeroMass = Math.max(0, finite(shareExactlyZero));
  const prepared = bins
    .filter((bin) => Number.isFinite(bin.start) && Number.isFinite(bin.share))
    .map((bin): PreparedPercentileBin | null => {
      let start = bin.start;
      let end = bin.start + width;
      let share = Math.max(0, bin.share);

      if (closeTo(start, 0)) {
        start = ZERO_EDGE;
        share = Math.max(0, share - zeroMass);
      } else if (closeTo(end, 0)) {
        end = -ZERO_EDGE;
      }

      return end > start && share > 0
        ? { start, end, share, exactZero: false }
        : null;
    })
    .filter((bin): bin is PreparedPercentileBin => bin !== null);

  if (zeroMass > 0) {
    prepared.push({
      start: -ZERO_HALF_WIDTH,
      end: ZERO_HALF_WIDTH,
      share: zeroMass,
      exactZero: true,
    });
  }

  return prepared.sort((left, right) => left.start - right.start);
}

export interface PreparedContribution {
  reasons: Reason[];
  remainder: number | null;
  calm: boolean;
}

/**
 * The service already caps reasons at five. This defensive normalization keeps
 * a malformed response honest: overflow is added to the visible remainder,
 * never silently discarded.
 */
export function prepareContribution(
  response: ContributionResponse,
): PreparedContribution {
  const valid = response.reasons.filter(
    (reason) =>
      typeof reason.text === "string" &&
      reason.text.trim().length > 0 &&
      Number.isFinite(reason.points) &&
      reason.points !== 0,
  );
  const reasons = valid.slice(0, 5);
  const overflow = valid
    .slice(5)
    .reduce((total, reason) => total + reason.points, 0);

  let remainder =
    response.remainder === null || !Number.isFinite(response.remainder)
      ? null
      : response.remainder;
  if (overflow !== 0) remainder = (remainder ?? 0) + overflow;

  const totalDifference = finite(response.predicted) - finite(response.baseline);
  const calm =
    response.nothingStandsOut &&
    reasons.length === 0 &&
    Math.abs(totalDifference) < PRINTED_ZERO;

  // Never turn a meaningful unexplained difference into the calm state.
  if (!calm && reasons.length === 0 && remainder === null) {
    remainder = totalDifference;
  }

  return {
    reasons,
    remainder:
      remainder !== null && Math.abs(remainder) >= PRINTED_ZERO
        ? remainder
        : null,
    calm,
  };
}

export interface ContributionScale {
  zeroPercent: number;
  lengthPercent: (points: number) => number;
}

export function contributionScale(
  values: readonly number[],
): ContributionScale {
  const positive = values.reduce(
    (largest, value) => (value > 0 ? Math.max(largest, value) : largest),
    0,
  );
  const negative = values.reduce(
    (largest, value) => (value < 0 ? Math.max(largest, -value) : largest),
    0,
  );
  const span = positive + negative;

  return {
    zeroPercent: span > 0 ? (negative / span) * 100 : 50,
    lengthPercent: (points) =>
      span > 0 ? (Math.abs(points) / span) * 100 : 0,
  };
}

export interface TwinGeometry {
  firstPercent: number;
  secondPercent: number;
  zeroPercent: number;
  collapsedPercent: number;
  essentiallySame: boolean;
  crossesZero: boolean;
  bothNegative: boolean;
  eitherExactlyZero: boolean;
}

/**
 * Uses a zero-inclusive scale so every connector keeps its numerical meaning.
 * A printed zero gap collapses to one dot rather than drawing fake distance.
 */
export function twinGeometry(response: TwinResponse): TwinGeometry {
  const first = finite(response.a.rate);
  const second = finite(response.b.rate);
  const low = Math.min(first, second, 0);
  const high = Math.max(first, second, 0);
  const pad = Math.max((high - low) * 0.12, 0.5);
  const domainLow = low - pad;
  const domainHigh = high + pad;
  const toPercent = (value: number) =>
    ((value - domainLow) / (domainHigh - domainLow)) * 100;

  const firstPercent = toPercent(first);
  const secondPercent = toPercent(second);

  return {
    firstPercent,
    secondPercent,
    zeroPercent: toPercent(0),
    collapsedPercent: (firstPercent + secondPercent) / 2,
    essentiallySame: Math.abs(finite(response.gapPoints)) < PRINTED_ZERO,
    crossesZero: Math.min(first, second) < 0 && Math.max(first, second) > 0,
    bothNegative: first < 0 && second < 0,
    eitherExactlyZero: first === 0 || second === 0,
  };
}


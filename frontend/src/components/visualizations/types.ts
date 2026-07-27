/**
 * Reader-facing visualization contracts.
 *
 * These mirror design/WEB_SYSTEM.md exactly. Every string is ready to print;
 * no component in this folder knows about encoded fields or implementation
 * details.
 */

export interface DistributionBin {
  start: number;
  share: number;
}

export interface PercentileResponse {
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
}

export interface Reason {
  text: string;
  points: number;
}

export interface ContributionResponse {
  baseline: number;
  predicted: number;
  reasons: Reason[];
  remainder: number | null;
  nothingStandsOut: boolean;
  summary: string;
}

export interface TwinSide {
  label: string;
  rate: number;
  display: string;
}

export interface TwinAttribute {
  label: string;
  value: string;
}

export interface TwinResponse {
  changed: string;
  changedLabel: string;
  a: TwinSide;
  b: TwinSide;
  shared: TwinAttribute[];
  gapPoints: number;
  gapMoney: string | null;
  summary: string;
  comparisonNote: string;
}


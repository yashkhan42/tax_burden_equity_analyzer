import type {
  ContributionResponse,
  DistributionBin,
  PercentileResponse,
  TwinResponse,
} from "./types";

const starts = Array.from({ length: 35 }, (_, index) => -50 + index * 2.5);

const fixtureBins: DistributionBin[] = starts.map((start) => {
  const midpoint = start + 1.25;
  const centre = Math.exp(-Math.pow((midpoint - 7) / 8, 2)) * 0.095;
  const negativeTail =
    midpoint < 0 ? Math.exp(-Math.pow((midpoint + 5) / 12, 2)) * 0.018 : 0;
  const exactZeroMass = start === 0 ? 0.085 : 0;
  return { start, share: centre + negativeTail + exactZeroMass };
});

const percentileBase = {
  percentile: 64,
  belowCount: 64,
  bins: fixtureBins,
  binWidth: 2.5,
  shareExactlyZero: 0.085,
  shareNegative: 0.12,
  domain: [-52, 36] as [number, number],
};

export const percentileFixtures: Record<string, PercentileResponse> = {
  negative: {
    ...percentileBase,
    markerRate: -7.1,
    displayRate: "−7.1%",
    percentile: 8,
    belowCount: 8,
    summary:
      "This rate is below most predictions in the survey comparison group.",
  },
  exactlyZero: {
    ...percentileBase,
    markerRate: 0,
    displayRate: "0.0%",
    percentile: 18,
    belowCount: 18,
    summary:
      "This filer lands at the distinct point where the predicted rate is exactly zero.",
  },
  extremeHigh: {
    ...percentileBase,
    markerRate: 32.6,
    displayRate: "32.6%",
    percentile: 100,
    belowCount: 100,
    summary:
      "This rate sits at the far upper edge of the survey comparison group.",
  },
};

export const contributionFixtures: Record<string, ContributionResponse> = {
  calm: {
    baseline: 9.2,
    predicted: 9.2,
    reasons: [],
    remainder: null,
    nothingStandsOut: true,
    summary:
      "No single characteristic moves this prediction far from its starting point.",
  },
  negative: {
    baseline: 9.2,
    predicted: -8.7,
    reasons: [
      { text: "Three children live at home", points: -4.9 },
      { text: "A low annual income", points: -2.2 },
      { text: "The return uses head-of-household filing", points: -0.8 },
      { text: "Most income comes from a job", points: 0.5 },
    ],
    remainder: -10.3,
    nothingStandsOut: false,
    summary:
      "Several parts of this filer’s situation lower the effective rate below zero.",
  },
  extreme: {
    baseline: 9.2,
    predicted: 32.6,
    reasons: [
      { text: "A very high annual income", points: 12.6 },
      { text: "Most income comes from investments", points: 8.8 },
      { text: "No children live at home", points: 1.4 },
      { text: "The return is filed by a single filer", points: 0.9 },
      { text: "The filer is 65 or older", points: -0.4 },
      { text: "An extra fixture reason", points: 0.3 },
    ],
    remainder: -0.2,
    nothingStandsOut: false,
    summary:
      "Two unusually large reasons account for most of this high predicted rate.",
  },
};

const shared = [
  { label: "Income", value: "$41,000 a year, mostly from paychecks" },
  { label: "Age", value: "34" },
  { label: "Household size", value: "three people" },
  { label: "Where they live", value: "New York" },
];

export const twinFixtures: Record<string, TwinResponse> = {
  crossing: {
    changed: "whether they have children at home",
    changedLabel: "Children at home",
    a: { label: "none", rate: 1.9, display: "1.9%" },
    b: { label: "two", rate: -7.1, display: "−7.1%" },
    shared,
    gapPoints: -9,
    gapMoney: "About $3,700 a year at this income.",
    summary:
      "Adding two children lowers the printed effective rate by 9.0 points.",
    comparisonNote:
      "This is one controlled comparison; it does not describe every family.",
  },
  exactlyZero: {
    changed: "how they file",
    changedLabel: "How they file",
    a: { label: "on their own", rate: 0, display: "0.0%" },
    b: { label: "as head of household", rate: 3.2, display: "3.2%" },
    shared,
    gapPoints: 3.2,
    gapMoney: "About $1,300 a year at this income.",
    summary:
      "Changing how they file raises the printed effective rate by 3.2 points.",
    comparisonNote:
      "The two sides hold income, age, household size, and location constant.",
  },
  nearZero: {
    changed: "whether they are married",
    changedLabel: "Marital situation",
    a: { label: "never married", rate: 11.24, display: "11.2%" },
    b: { label: "married, living together", rate: 11.21, display: "11.2%" },
    shared,
    gapPoints: 0,
    gapMoney: null,
    summary:
      "The two printed effective rates are essentially the same in this comparison.",
    comparisonNote:
      "A difference smaller than the displayed precision is not presented as a gap.",
  },
  bothNegative: {
    changed: "how they file",
    changedLabel: "How they file",
    a: { label: "on their own", rate: -4.2, display: "−4.2%" },
    b: { label: "together with a spouse", rate: -11.9, display: "−11.9%" },
    shared,
    gapPoints: -7.7,
    gapMoney: "About $3,200 a year at this income.",
    summary:
      "Changing how they file lowers an already negative effective rate by 7.7 points.",
    comparisonNote:
      "Negative rates are legitimate findings and are compared on the same scale.",
  },
  extreme: {
    changed: "where the household’s money comes from",
    changedLabel: "Where the money comes from",
    a: { label: "mostly paychecks", rate: 32.6, display: "32.6%" },
    b: {
      label: "mostly other sources, with refundable credits",
      rate: -48.6,
      display: "−48.6%",
    },
    shared,
    gapPoints: -81.2,
    gapMoney: "About $33,000 a year at this income.",
    summary:
      "Changing where the money comes from moves the two printed rates 81.2 points apart.",
    comparisonNote:
      "This extreme case shows the full scale without clipping either rate.",
  },
};

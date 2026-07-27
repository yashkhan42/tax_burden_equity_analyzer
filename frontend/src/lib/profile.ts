import type { MaritalStatus, TaxProfile } from "@/lib/api";

export const DEFAULT_PROFILE: TaxProfile = {
  totalIncome: 64_000,
  spouseIncome: 0,
  income: {
    wages: 64_000,
    business: 0,
    interest: 0,
    dividends: 0,
    retirement: 0,
    socialSecurity: 0,
    rent: 0,
  },
  age: 42,
  childrenAtHome: 0,
  childrenUnderFive: 0,
  householdSize: 1,
  maritalStatus: "never_married",
  filingChoice: "single",
  state: "New York",
};

export const MARITAL_OPTIONS: Array<{
  value: MaritalStatus;
  label: string;
}> = [
  { value: "married_living_together", label: "Married, living together" },
  { value: "married_living_apart", label: "Married, living apart" },
  { value: "separated", label: "Separated" },
  { value: "divorced", label: "Divorced" },
  { value: "widowed", label: "Widowed" },
  { value: "never_married", label: "Never married" },
];

export const STATES = [
  "Alabama",
  "Alaska",
  "Arizona",
  "Arkansas",
  "California",
  "Colorado",
  "Connecticut",
  "Delaware",
  "District of Columbia",
  "Florida",
  "Georgia",
  "Hawaii",
  "Idaho",
  "Illinois",
  "Indiana",
  "Iowa",
  "Kansas",
  "Kentucky",
  "Louisiana",
  "Maine",
  "Maryland",
  "Massachusetts",
  "Michigan",
  "Minnesota",
  "Mississippi",
  "Missouri",
  "Montana",
  "Nebraska",
  "Nevada",
  "New Hampshire",
  "New Jersey",
  "New Mexico",
  "New York",
  "North Carolina",
  "North Dakota",
  "Ohio",
  "Oklahoma",
  "Oregon",
  "Pennsylvania",
  "Rhode Island",
  "South Carolina",
  "South Dakota",
  "Tennessee",
  "Texas",
  "Utah",
  "Vermont",
  "Virginia",
  "Washington",
  "West Virginia",
  "Wisconsin",
  "Wyoming",
] as const;

export function householdMinimum(profile: TaxProfile) {
  const spousePresent =
    profile.maritalStatus === "married_living_together" ? 1 : 0;
  return Math.max(1, profile.childrenAtHome + spousePresent + 1);
}

export function validateProfile(profile: TaxProfile): string | null {
  if (
    !Number.isFinite(profile.totalIncome) ||
    profile.totalIncome < 0 ||
    profile.totalIncome > 2_295_804
  ) {
    return "Enter a total income between $0 and $2,295,804.";
  }

  if (!Number.isFinite(profile.spouseIncome) || profile.spouseIncome < 0) {
    return "Enter a non-negative amount for a spouse’s income.";
  }

  const sourceValues = Object.values(profile.income);
  if (sourceValues.some((value) => !Number.isFinite(value))) {
    return "Enter a number for every income source.";
  }
  if (
    profile.income.wages < 0 ||
    profile.income.interest < 0 ||
    profile.income.dividends < 0 ||
    profile.income.retirement < 0 ||
    profile.income.socialSecurity < 0
  ) {
    return "Only business and rental amounts can be entered as losses.";
  }

  if (!Number.isInteger(profile.age) || profile.age < 15 || profile.age > 85) {
    return "Enter an age from 15 through 85.";
  }
  if (
    !Number.isInteger(profile.childrenAtHome) ||
    profile.childrenAtHome < 0 ||
    profile.childrenAtHome > 9
  ) {
    return "Enter between 0 and 9 children at home.";
  }
  if (
    !Number.isInteger(profile.childrenUnderFive) ||
    profile.childrenUnderFive < 0 ||
    profile.childrenUnderFive > Math.min(5, profile.childrenAtHome)
  ) {
    return "Children under five cannot exceed the number of children at home.";
  }

  const minimum = householdMinimum(profile);
  if (
    !Number.isInteger(profile.householdSize) ||
    profile.householdSize < minimum ||
    profile.householdSize > 16
  ) {
    return `Enter a household size from ${minimum} through 16.`;
  }

  return null;
}

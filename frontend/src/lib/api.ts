export type MaritalStatus =
  | "married_living_together"
  | "married_living_apart"
  | "separated"
  | "divorced"
  | "widowed"
  | "never_married";

export type FilingChoice = "head_of_household" | "single" | null;

export type TaxProfile = {
  totalIncome: number;
  spouseIncome: number;
  income: {
    wages: number;
    business: number;
    interest: number;
    dividends: number;
    retirement: number;
    socialSecurity: number;
    rent: number;
  };
  age: number;
  childrenAtHome: number;
  childrenUnderFive: number;
  householdSize: number;
  maritalStatus: MaritalStatus;
  filingChoice: FilingChoice;
  state: string;
};

export type PredictResponse = {
  rate: number;
  display: string;
  isNegative: boolean;
  framing: string;
};

export type DistributionBin = {
  start: number;
  share: number;
};

export type PercentileResponse = {
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
};

export type Reason = {
  text: string;
  points: number;
};

export type ContributionResponse = {
  baseline: number;
  predicted: number;
  reasons: Reason[];
  remainder: number | null;
  nothingStandsOut: boolean;
  summary: string;
};

export type TwinComparison =
  | "filing"
  | "marital"
  | "income_source"
  | "dependents";

export type TwinResponse = {
  changed: string;
  changedLabel: string;
  a: {
    label: string;
    rate: number;
    display: string;
  };
  b: {
    label: string;
    rate: number;
    display: string;
  };
  shared: Array<{
    label: string;
    value: string;
  }>;
  gapPoints: number;
  gapMoney: string | null;
  summary: string;
  comparisonNote: string;
};

export type HealthResponse = {
  status: "ready" | "degraded";
  modelReady: boolean;
  artifactSource: "local" | "downloaded" | null;
};

type ApiDetail = {
  code?: string;
  message?: string;
};

export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number | null,
    readonly code: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

const API_URL = (
  process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"
).replace(/\/$/, "");

async function request<T>(
  path: string,
  body: object,
  signal?: AbortSignal,
): Promise<T> {
  let response: Response;

  try {
    response = await fetch(`${API_URL}${path}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
      signal,
    });
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError") {
      throw error;
    }
    throw new ApiError(
      "We could not reach the analysis service.",
      null,
      "network_error",
    );
  }

  const payload = (await response.json().catch(() => null)) as
    | { detail?: ApiDetail }
    | null;

  if (!response.ok) {
    const detail = payload?.detail;
    throw new ApiError(
      detail?.message ?? "The analysis could not be completed.",
      response.status,
      detail?.code ?? "request_failed",
    );
  }

  return payload as T;
}

export const analysisApi = {
  predict(profile: TaxProfile, signal?: AbortSignal) {
    return request<PredictResponse>("/api/v1/predict", { profile }, signal);
  },
  percentile(profile: TaxProfile, signal?: AbortSignal) {
    return request<PercentileResponse>(
      "/api/v1/percentile",
      { profile },
      signal,
    );
  },
  contribution(profile: TaxProfile, signal?: AbortSignal) {
    return request<ContributionResponse>(
      "/api/v1/contribution",
      { profile },
      signal,
    );
  },
  twin(
    profile: TaxProfile,
    comparison: TwinComparison,
    signal?: AbortSignal,
  ) {
    return request<TwinResponse>(
      "/api/v1/twin",
      { profile, comparison },
      signal,
    );
  },
};

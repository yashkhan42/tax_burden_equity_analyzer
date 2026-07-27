"""Locked reader-facing request and response schemas for the web API."""

from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

import model_interface as mi
from codebook import STATE_NAMES


MARITAL_STATUS_TO_CODE = {
    "married_living_together": 1,
    "married_living_apart": 2,
    "separated": 3,
    "divorced": 4,
    "widowed": 5,
    "never_married": 6,
}


class APIModel(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class IncomeSources(APIModel):
    wages: float = Field(ge=0)
    business: float
    interest: float = Field(ge=0)
    dividends: float = Field(ge=0)
    retirement: float = Field(ge=0)
    socialSecurity: float = Field(ge=0)
    rent: float


class TaxProfile(APIModel):
    totalIncome: float = Field(
        ge=mi.UNIT_INCTOT_RANGE[0], le=mi.UNIT_INCTOT_RANGE[1]
    )
    spouseIncome: float = Field(ge=0)
    income: IncomeSources
    age: int = Field(ge=mi.AGE_RANGE[0], le=mi.AGE_RANGE[1])
    childrenAtHome: int = Field(ge=0, le=mi.NCHILD_MAX)
    childrenUnderFive: int = Field(ge=0, le=mi.NCHLT5_MAX)
    householdSize: int = Field(ge=mi.FAMSIZE_RANGE[0], le=mi.FAMSIZE_RANGE[1])
    maritalStatus: Literal[
        "married_living_together",
        "married_living_apart",
        "separated",
        "divorced",
        "widowed",
        "never_married",
    ]
    filingChoice: Literal["head_of_household", "single"] | None
    state: str

    @field_validator("state")
    @classmethod
    def state_must_be_reader_facing(cls, value: str) -> str:
        if value not in STATE_NAMES.values():
            raise ValueError("state must be a full supported state name")
        return value

    @model_validator(mode="after")
    def ordinary_tax_unit_relationships(self) -> "TaxProfile":
        living_together = self.maritalStatus == "married_living_together"
        if living_together:
            if self.filingChoice is not None:
                raise ValueError(
                    "filingChoice must be null for a married couple living together"
                )
        elif self.filingChoice is None:
            raise ValueError(
                "filingChoice is required unless the couple is married and living together"
            )

        if not living_together and self.spouseIncome != 0:
            raise ValueError(
                "spouseIncome must be zero unless the couple is married and living together"
            )
        if self.childrenUnderFive > self.childrenAtHome:
            raise ValueError("childrenUnderFive cannot exceed childrenAtHome")

        household_floor = self.childrenAtHome + 1 + (1 if living_together else 0)
        if self.householdSize < household_floor:
            raise ValueError(
                "householdSize is too small for the adults and children described"
            )
        return self

    def to_model_profile(self) -> dict:
        """Map semantic reader values to model_interface's raw profile contract."""
        marital_code = MARITAL_STATUS_TO_CODE[self.maritalStatus]
        head = self.filingChoice == "head_of_household"
        filing_status = mi.derive_filing_status(
            marital_code, head_of_household=head
        )
        state_code = {name: code for code, name in STATE_NAMES.items()}[self.state]
        return {
            "unit_inctot": float(self.totalIncome),
            "spouse_income": float(self.spouseIncome),
            "incwage": float(self.income.wages),
            "incbus": float(self.income.business),
            "incint": float(self.income.interest),
            "incdivid": float(self.income.dividends),
            "incretir": float(self.income.retirement),
            "incss": float(self.income.socialSecurity),
            "incrent": float(self.income.rent),
            "age": int(self.age),
            "nchild": int(self.childrenAtHome),
            "nchlt5": int(self.childrenUnderFive),
            "famsize": int(self.householdSize),
            "filing_status": int(filing_status),
            "marst": int(marital_code),
            "statefip": int(state_code),
        }


class ProfileRequest(APIModel):
    profile: TaxProfile


class TwinComparison(str, Enum):
    filing = "filing"
    marital = "marital"
    income_source = "income_source"
    dependents = "dependents"


class TwinRequest(ProfileRequest):
    comparison: TwinComparison


class PredictResponse(APIModel):
    rate: float
    display: str
    isNegative: bool
    framing: str


class DistributionBin(APIModel):
    start: float
    share: float


class PercentileResponse(APIModel):
    markerRate: float
    displayRate: str
    percentile: float
    belowCount: int
    bins: list[DistributionBin]
    binWidth: float
    shareExactlyZero: float
    shareNegative: float
    domain: tuple[float, float]
    summary: str


class Reason(APIModel):
    text: str
    points: float


class ContributionResponse(APIModel):
    baseline: float
    predicted: float
    reasons: list[Reason]
    remainder: float | None
    nothingStandsOut: bool
    summary: str


class TwinSide(APIModel):
    label: str
    rate: float
    display: str


class TwinAttribute(APIModel):
    label: str
    value: str


class TwinResponse(APIModel):
    changed: str
    changedLabel: str
    a: TwinSide
    b: TwinSide
    shared: list[TwinAttribute]
    gapPoints: float
    gapMoney: str | None
    summary: str
    comparisonNote: str


class HealthResponse(APIModel):
    status: Literal["ready", "degraded"]
    modelReady: bool
    artifactSource: Literal["local", "downloaded"] | None

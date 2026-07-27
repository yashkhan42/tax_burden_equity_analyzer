"use client";

import { ArrowRight, ChevronDown, LoaderCircle } from "lucide-react";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import type { MaritalStatus, TaxProfile } from "@/lib/api";
import {
  DEFAULT_PROFILE,
  householdMinimum,
  MARITAL_OPTIONS,
  STATES,
  validateProfile,
} from "@/lib/profile";

type IncomeKey = keyof TaxProfile["income"];

function NumberField({
  help,
  id,
  label,
  max,
  min,
  onChange,
  prefix,
  step = 1,
  value,
}: {
  help?: string;
  id: string;
  label: string;
  max?: number;
  min?: number;
  onChange: (value: number) => void;
  prefix?: string;
  step?: number;
  value: number;
}) {
  const helpId = help ? `${id}-help` : undefined;

  return (
    <label className="field" htmlFor={id}>
      <span className="field-label">{label}</span>
      <span className="number-control">
        {prefix ? <span aria-hidden="true">{prefix}</span> : null}
        <input
          aria-describedby={helpId}
          id={id}
          inputMode="decimal"
          max={max}
          min={min}
          onChange={(event) => onChange(Number(event.target.value))}
          required
          step={step}
          type="number"
          value={value}
        />
      </span>
      {help ? (
        <span className="field-help" id={helpId}>
          {help}
        </span>
      ) : null}
    </label>
  );
}

export function ProfileForm({
  loading,
  onSubmit,
}: {
  loading: boolean;
  onSubmit: (profile: TaxProfile) => void;
}) {
  const [profile, setProfile] = useState<TaxProfile>(DEFAULT_PROFILE);
  const [detailsOpen, setDetailsOpen] = useState(false);
  const [incomeCustomized, setIncomeCustomized] = useState(false);
  const [validationError, setValidationError] = useState<string | null>(null);

  const spousePresent =
    profile.maritalStatus === "married_living_together";
  const minimumHousehold = householdMinimum(profile);

  const setTopLevel = <K extends keyof TaxProfile>(
    key: K,
    value: TaxProfile[K],
  ) => {
    setProfile((current) => ({ ...current, [key]: value }));
  };

  const setIncome = (key: IncomeKey, value: number) => {
    setIncomeCustomized(true);
    setProfile((current) => ({
      ...current,
      income: { ...current.income, [key]: value },
    }));
  };

  const changeTotalIncome = (value: number) => {
    setProfile((current) => ({
      ...current,
      totalIncome: value,
      income: incomeCustomized
        ? current.income
        : {
            ...current.income,
            wages: Math.max(0, value - current.spouseIncome),
          },
    }));
  };

  const changeSpouseIncome = (value: number) => {
    setProfile((current) => ({
      ...current,
      spouseIncome: value,
      income: incomeCustomized
        ? current.income
        : {
            ...current.income,
            wages: Math.max(0, current.totalIncome - value),
          },
    }));
  };

  const changeMaritalStatus = (value: MaritalStatus) => {
    setProfile((current) => {
      const spouseIncome =
        value === "married_living_together" ? current.spouseIncome : 0;
      const next: TaxProfile = {
        ...current,
        maritalStatus: value,
        spouseIncome,
        income: incomeCustomized
          ? current.income
          : {
              ...current.income,
              wages: Math.max(0, current.totalIncome - spouseIncome),
            },
        filingChoice:
          value === "married_living_together"
            ? null
            : (current.filingChoice ?? "single"),
      };
      return {
        ...next,
        householdSize: Math.max(next.householdSize, householdMinimum(next)),
      };
    });
  };

  const changeChildren = (value: number) => {
    setProfile((current) => {
      const next = {
        ...current,
        childrenAtHome: value,
        childrenUnderFive: Math.min(current.childrenUnderFive, value, 5),
      };
      return {
        ...next,
        householdSize: Math.max(next.householdSize, householdMinimum(next)),
      };
    });
  };

  const handleSubmit = (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const error = validateProfile(profile);
    setValidationError(error);
    if (error) return;
    onSubmit(profile);
  };

  return (
    <form className="profile-form" noValidate onSubmit={handleSubmit}>
      <div className="form-intro">
        <h2>Describe one tax return</h2>
        <p>
          Four details are enough to start. Add income and household detail
          only when it helps describe the return more faithfully.
        </p>
      </div>

      <fieldset className="form-group essentials-group">
        <legend className="sr-only">Essential details</legend>
        <div className="field-grid field-grid-primary">
          <NumberField
            help="Annual income for everyone represented on the return."
            id="total-income"
            label="Total income on the return"
            max={2_295_804}
            min={0}
            onChange={changeTotalIncome}
            prefix="$"
            step={1_000}
            value={profile.totalIncome}
          />

          <div className="field status-field">
            <label className="field-label" htmlFor="marital-status">
              Marital status and filing
            </label>
            <select
              id="marital-status"
              onChange={(event) =>
                changeMaritalStatus(event.target.value as MaritalStatus)
              }
              value={profile.maritalStatus}
            >
              {MARITAL_OPTIONS.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
            {spousePresent ? (
              <span className="field-help">
                Treated as filing together, matching the survey returns.
              </span>
            ) : (
              <label className="filing-check">
                <input
                  checked={profile.filingChoice === "head_of_household"}
                  onChange={(event) =>
                    setTopLevel(
                      "filingChoice",
                      event.target.checked ? "head_of_household" : "single",
                    )
                  }
                  type="checkbox"
                />
                <span>File as head of household</span>
              </label>
            )}
          </div>

          <label className="field" htmlFor="state">
            <span className="field-label">State</span>
            <select
              id="state"
              onChange={(event) => setTopLevel("state", event.target.value)}
              value={profile.state}
            >
              {STATES.map((state) => (
                <option key={state} value={state}>
                  {state}
                </option>
              ))}
            </select>
            <span className="field-help">
              Included because location appears in the survey patterns.
            </span>
          </label>

          <NumberField
            id="age"
            label="Age"
            max={85}
            min={15}
            onChange={(value) => setTopLevel("age", value)}
            value={profile.age}
          />
        </div>
      </fieldset>

      <div className="detail-disclosure">
        <button
          aria-controls="additional-details"
          aria-expanded={detailsOpen}
          className="detail-toggle"
          onClick={() => setDetailsOpen((open) => !open)}
          type="button"
        >
          <span>
            <strong>{detailsOpen ? "Hide extra detail" : "Add more detail"}</strong>
            <small>Income sources and household details</small>
          </span>
          <ChevronDown
            aria-hidden
            className={detailsOpen ? "detail-chevron-open" : ""}
            size={20}
          />
        </button>

        {detailsOpen ? (
          <div className="detail-panel" id="additional-details">
            <p className="detail-default-note">
              Until changed, the return is treated as income from a job, with
              no children and the smallest valid household.
            </p>

            <fieldset className="form-group">
              <legend>Where the income comes from</legend>
              <p className="group-note">
                Use annual amounts before federal tax. Business and rental
                losses can be negative.
              </p>
              {spousePresent ? (
                <div className="field-grid spouse-grid">
                  <NumberField
                    help="Keep this amount out of the seven source fields below."
                    id="spouse-income"
                    label="Spouse’s total income"
                    min={0}
                    onChange={changeSpouseIncome}
                    prefix="$"
                    step={1_000}
                    value={profile.spouseIncome}
                  />
                </div>
              ) : null}
              <div className="field-grid field-grid-four">
                <NumberField
                  id="wages"
                  label="Pay from a job"
                  min={0}
                  onChange={(value) => setIncome("wages", value)}
                  prefix="$"
                  step={1_000}
                  value={profile.income.wages}
                />
                <NumberField
                  id="business"
                  label="Business or self-employment"
                  min={-500_000}
                  onChange={(value) => setIncome("business", value)}
                  prefix="$"
                  step={1_000}
                  value={profile.income.business}
                />
                <NumberField
                  id="interest"
                  label="Interest from savings"
                  min={0}
                  onChange={(value) => setIncome("interest", value)}
                  prefix="$"
                  step={500}
                  value={profile.income.interest}
                />
                <NumberField
                  id="dividends"
                  label="Dividends from investments"
                  min={0}
                  onChange={(value) => setIncome("dividends", value)}
                  prefix="$"
                  step={1_000}
                  value={profile.income.dividends}
                />
                <NumberField
                  id="retirement"
                  label="Pension or retirement account"
                  min={0}
                  onChange={(value) => setIncome("retirement", value)}
                  prefix="$"
                  step={1_000}
                  value={profile.income.retirement}
                />
                <NumberField
                  id="social-security"
                  label="Social Security"
                  min={0}
                  onChange={(value) => setIncome("socialSecurity", value)}
                  prefix="$"
                  step={1_000}
                  value={profile.income.socialSecurity}
                />
                <NumberField
                  id="rent"
                  label="Rent from property"
                  min={-500_000}
                  onChange={(value) => setIncome("rent", value)}
                  prefix="$"
                  step={1_000}
                  value={profile.income.rent}
                />
              </div>
            </fieldset>

            <fieldset className="form-group">
              <legend>Household details</legend>
              <p className="group-note">
                Describe the household as it stood during the year.
              </p>
              <div className="field-grid field-grid-household">
                <NumberField
                  id="children"
                  label="Children at home"
                  max={9}
                  min={0}
                  onChange={changeChildren}
                  value={profile.childrenAtHome}
                />
                <NumberField
                  id="children-under-five"
                  label="Children under five"
                  max={Math.min(5, profile.childrenAtHome)}
                  min={0}
                  onChange={(value) =>
                    setTopLevel("childrenUnderFive", value)
                  }
                  value={profile.childrenUnderFive}
                />
                <NumberField
                  help={`At least ${minimumHousehold} for this household.`}
                  id="household-size"
                  label="People in the household"
                  max={16}
                  min={minimumHousehold}
                  onChange={(value) => setTopLevel("householdSize", value)}
                  value={profile.householdSize}
                />
              </div>
            </fieldset>
          </div>
        ) : null}
      </div>

      <div className="form-submit">
        <div aria-live="polite">
          {validationError ? (
            <p className="form-error" role="alert">
              {validationError}
            </p>
          ) : (
            <p className="form-framing">
              This predicts an average rate for similar filers, not anyone’s
              tax bill.
            </p>
          )}
        </div>
        <Button disabled={loading} type="submit">
          {loading ? (
            <>
              <LoaderCircle aria-hidden className="spin" size={18} />
              Finding the rate
            </>
          ) : (
            <>
              Show the rate
              <ArrowRight aria-hidden size={18} />
            </>
          )}
        </Button>
      </div>
    </form>
  );
}

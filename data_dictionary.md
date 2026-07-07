# Data Dictionary 

# Tax Burden Equity Analyzer

## Source files
- IRS Statistics of Income (SOI), Tables 3.2, 3.3 Tax Return Years 2021-2023
- Link: https://www.irs.gov/statistics/soi-tax-stats-individual-statistical-tables-by-size-of-adjusted-gross-incom
- Tax Policy Center, Table T25-0047 for model validation only
- Link: https://taxpolicycenter.org/model-estimates/t25-0047

## Master Dataset: `irs_master_clean.csv
| Column             | Description                                   | Units                    | Source                  |
|--------------------|-----------------------------------------------|--------------------------|-------------------------|
| income_bracket     | Income range group (ex. $ $10,000 to $15,000) | Text                     | IRS SOI Table 3.2 / 3.3 |
| num_returns        | Number of tax returns filed in this bracket   | Count                    | IRS SOI Table 3.2 / 3.3 |
| agi                | Total adjusted gross income for this bracket  | Thousands of dollars     | IRS SOI Table 3.2 / 3.3 |
| total_income_tax   | Total income tax paid by this bracket         | Thousands of dollars     | IRS SOI Table 3.2 / 3.3 |
| effective_tax_rate | Effective tax rate = total_income_tax ÷ agi   | Decimal (e.x. 0.05 = 5%) | Computed                |
| year               | Tax data year                                 | Year (2021, 2022, 2023)  | IRS SOI                 |


## Additional notes 
- Money amounts are in thousands of dollars
- effective_tax_rate is computed, does not come from the IRS files.
- Under $5,000 includes deficits bracket may show negative agi values (real/expected)
- Cells marked * or ** in raw files show the unrelaible data  (treated as a NaN)
- Table 3.2 includes filers by effective tax rate bracket
- Table 3.3 organizes filers by filing status
- Each year's data has exactly 12 income brakcet rows 
- Total dataset: 72 rows (12 brackets x 3 years x 2 tables)


## Author 
- Laura Romero / Data Engineer / AI4ALL Ignite Team 01B

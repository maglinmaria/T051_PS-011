# Technical and Implementation Decision Log

This log separates facts visible in the project from rationale inferred from
those facts. No separate architecture decision record or meeting note was
used to establish the motivations below; inferred motivations are not
presented as historical decisions.

## Confirmed by the project

### Programming language: Python

- **Confirmed:** The application is implemented in Python under `src/`, and
  the project `requirements.txt` lists `pytest`.
- **Selection rationale:** The repository does not state why Python was
  chosen. No specific historical reason can be verified.

### Modular implementation

- **Confirmed:** Responsibilities are divided among modules for command
  processing, data loading, validation, models/state, depreciation,
  settlement, claim assessment, theft, NCB, constants/rule IDs, and reporting.
- **Selection rationale:** The project does not record an explicit reason for
  this architecture.

### Monetary arithmetic

- **Confirmed:** Monetary values use `decimal.Decimal`. Depreciation and
  settlement use two-place `Decimal` precision and `ROUND_HALF_UP`; amounts
  are generally rounded to the nearest paisa.
- **Selection rationale:** Using decimal arithmetic is consistent with the
  need to calculate rupee amounts to two decimal places. This motivation is
  inferred from the implementation, not stated as a recorded decision.

### Depreciation and settlement

- **Confirmed:** Vehicle age is measured in completed calendar months.
  Depreciation varies by part category; paint uses the metal rate on half its
  cost. ZERO_DEP is limited by vehicle age and two earlier applied claims in
  a policy year.
- **Confirmed:** Repair settlement adds GST only for individual holders,
  deducts total excess, applies any late-intimation deduction, applies the
  learner cap, rounds payable, and then checks the Rs 500 threshold.
- **Confirmed:** Total-loss assessment compares surveyed parts plus labour
  before depreciation with 75% of IDV. Total-loss payable is based on IDV or
  eligible RTI invoice value, with excess and any customer-kept salvage
  deduction.
- **Confirmed:** Theft has its own 24-hour FIR and 90-day waiting-period
  checks, recovery handling, and IDV/RTI less excess calculation. It does
  not use repair GST, repair depreciation, or the repair minimum threshold.

### NCB and policy renewals

- **Confirmed:** NCB uses the slabs 0%, 20%, 25%, 35%, 45%, and 50%.
  Assessed claims are counted by incident date in the current policy period;
  rejected and unassessed claims are excluded, while `BELOW_THRESHOLD`
  claims count.
- **Confirmed:** NCB_PROTECT preserves NCB for one claim only. No claims
  advances one slab; an unprotected claim or more than one claim resets NCB
  to zero.
- **Confirmed:** Renewal records the old policy period and NCB result before
  advancing policy dates by one year.

### Edge cases and automated tests

- **Confirmed:** The sample data and tests cover, among other cases, the
  exactly-six-month depreciation boundary, exactly-75%-of-IDV total loss,
  learner licence, delayed intimation, 90-day theft boundary, low payable
  amount, ZERO_DEP claim limit, NCB protection, duplicate survey data, and
  claim/policy renewal behavior.
- **Confirmed:** Tests are implemented with pytest under `tests/`. The
  integration fixture runs the sample command stream, generates reports in
  a temporary directory, and checks decisions, calculations, row counts,
  errors, duplicate filtering, and policy history. `requirements.txt`
  contains `pytest`.
- **Selection rationale:** The repository demonstrates automated tests but
  does not record why pytest or this test strategy was selected.

### RTI first-year boundary

- **Confirmed:** The total-loss helper bases first-year RTI eligibility
  on completed vehicle age being less than 12 months. The command processor's
  theft path instead accepts an incident date on or before the 12-calendar-
  month anniversary. The sample README says “within the first 12 months” but
  does not resolve whether the anniversary itself is included.
- **Decision status:** No consistent boundary choice is recorded. The
  difference is documented rather than treated as a deliberate business
  decision; see BR-08 in [business_rules.md](./business_rules.md).

## Inferred rationale (not documented project decisions)

The following are reasonable interpretations of the code structure, not
verified statements about the team's original intent:

1. Dividing calculations, validation, orchestration, state, and reporting
   into separate modules likely makes responsibilities easier to locate and
   test independently.
2. Using `Decimal` likely avoids binary floating-point representation issues
   in money calculations and supports predictable two-decimal rounding.
3. Using CSV files and a command stream likely keeps the capstone's sample
   inputs and outputs inspectable without requiring a database or service.
   The code confirms the CSV/command-file approach; it does not state this as
   the reason for choosing it.

## Not specified in the inspected project

- Why Python was selected, beyond its confirmed use as the implementation
  language.
- The team's historical rationale for the module boundaries, rule values,
  pytest selection, or CSV-based input/output.
- Whether the exact 12-month purchase anniversary should qualify as the
  first policy year for RTI in every claim path.
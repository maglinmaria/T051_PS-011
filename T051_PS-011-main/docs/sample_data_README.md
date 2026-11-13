# PS-011 – Motor Insurance Claims Settlement with IDV, Depreciation and NCB — Sample Data Pack

Prepared by 10 SECONDS for Team T051.

## Files

| File | What it holds | Row count |
|---|---|---|
| `policies.csv` | 10 motor policies with vehicle, IDV, add-ons, NCB and excess | 10 data rows |
| `claims.csv` | 18 claims (own damage, flood, theft) with intimation, FIR and licence data | 18 data rows |
| `survey_lines.csv` | Surveyor report lines, 6-12 per non-theft claim | 114 data rows; 113 retained after duplicate validation |
| `commands.txt` | ASSESS, THEFT_RECOVERED, SETTLE_THEFT, RENEW and print commands in date order | 62 command lines (excluding comments) |

Row numbers quoted below are 1-based data-row numbers (the header is row 0). Line numbers for `commands.txt` are physical line numbers including comment lines.

## Column reference

Conventions: dates `YYYY-MM-DD`; timestamps `YYYY-MM-DD HH:MM:SS` (24h, IST, no timezone suffix); money in Rs as plain decimals with 2 places (no commas, no symbol); percentages as plain numbers (12.5 means 12.5%); booleans `true`/`false`; IDs uppercase with a fixed prefix.

### `policies.csv`

| Column | Type | Units / format | Allowed values | Notes |
|---|---|---|---|---|
| policy_id | string | POL-nnn | — | primary key |
| holder_name | string | — | — | — |
| holder_type | enum | — | INDIVIDUAL, CORPORATE | GST on payable only for INDIVIDUAL |
| vehicle_reg_no | string | KA-nn-XX-nnnn | — | — |
| make_model | string | — | — | — |
| engine_cc | int | cc | — | <= 1500 → excess 1,000; > 1500 → 2,000 |
| vehicle_purchase_date | date | — | — | vehicle age = incident date − this date (calendar months) |
| invoice_value | decimal | Rs | — | used by RTI |
| idv | decimal | Rs | — | insured declared value |
| policy_start | date | — | — | — |
| policy_end | date | — | — | policy year = start … end |
| addons | string | `;`-separated | ZERO_DEP, ENGINE_PROTECT, CONSUMABLES, RTI, NCB_PROTECT, or NONE | — |
| ncb_pct | decimal | % | 0, 20, 25, 35, 45, 50 | current NCB |
| voluntary_excess | decimal | Rs | — | added to compulsory excess |

### `claims.csv`

| Column | Type | Units / format | Allowed values | Notes |
|---|---|---|---|---|
| claim_id | string | CLM-nnn | — | numbered in intimation order |
| policy_id | string | — | policies.csv | — |
| cause | enum | — | ACCIDENT, THEFT, FLOOD, FIRE | — |
| incident_ts | timestamp | — | — | — |
| intimation_ts | timestamp | — | — | delay = intimation − incident |
| fir_ts | timestamp | — | — | THEFT only (empty otherwise) |
| driver_licence_status | enum | — | VALID, LEARNER, EXPIRED, NONE | — |
| licence_expiry_date | date | — | — | valid up to and including this date |
| salvage_option | enum | — | CUSTOMER_KEEPS, INSURER_TAKES | salvage deduction only when CUSTOMER_KEEPS |
| incident_city | string | — | — | — |

### `survey_lines.csv`

| Column | Type | Units / format | Allowed values | Notes |
|---|---|---|---|---|
| line_id | string | SVL-nnnn | — | — |
| claim_id | string | — | claims.csv | — |
| part_name | string | — | — | — |
| part_category | enum | — | METAL, PLASTIC, RUBBER, NYLON, GLASS, CONSUMABLE, PAINT | PAINT: METAL rate applied to 50% of the paint cost |
| engine_part | bool | — | — | true = engine line (FLOOD needs ENGINE_PROTECT) |
| part_cost | decimal | Rs | — | before depreciation, before GST |
| labour_cost | decimal | Rs | — | never depreciated; not paid on a rejected line |

## Data relationships, validation, and processing

The CSV row counts below were checked directly against the files in `data/`.
The 114 survey rows include the duplicate `SVL-0114`; validation removes that
row, leaving 113 survey lines in application state and in the sample
`claim_lines.csv` output.

### Relationships

- `policies.csv.policy_id` identifies a policy. `claims.csv.policy_id`
  references that policy; a claim with an unknown policy ID is reported as a
  validation error.
- `claims.csv.claim_id` identifies a claim. `survey_lines.csv.claim_id`
  references that claim; a survey line with an unknown claim ID is reported
  and excluded.
- Survey lines are grouped by claim ID. A claim can have multiple survey
  lines, and repeated part names are allowed when the line details differ.
- Theft claims have no repair survey lines in the supplied dataset; their
  settlement is driven by the claim/policy values and theft commands.

### Input processing

`data/commands.txt` is the application command stream (62 nonblank,
non-comment commands). The processor executes it in file order. It loads the
policy, claim, and survey CSVs, validates the loaded data after
`LOAD_SURVEY`, then assesses claims, handles theft actions, renews policies,
and queues requested reports. The CSV loader converts dates, timestamps,
decimal amounts, booleans, and semicolon-separated add-ons to Python values.
Errors are retained and written to `output/errors.csv`. The supplied tests
confirm that the sample data yields 10 policies, 18 claims, and 113 retained
survey lines.

### Validation rules in the implementation

| Data | Checks performed |
|---|---|
| Policies | Policy ID is present and not already loaded; holder type and add-ons are recognized; engine capacity, invoice value, and IDV are positive; voluntary excess is non-negative; policy start is not after policy end; vehicle purchase date is not after policy start; NCB is one of 0, 20, 25, 35, 45, or 50. |
| Claims | Claim ID is present and not already loaded; policy reference exists; cause, licence status, and salvage option are recognized; intimation is not before the incident; FIR is supplied only for theft and is required for theft. |
| Survey lines | Line ID is present; claim reference exists; part category is recognized; part and labour costs are non-negative; exact duplicate details are removed. |
| Claim assessment | A policy must cover the incident date; a valid licence must remain valid through the incident date; intimation and theft-FIR deadlines are applied during assessment/processing. An incident before the vehicle purchase date causes the vehicle-age calculation to fail. |

Malformed row values, missing fields, and validation failures are recorded
with their source and row/reference information rather than counted as
accepted records.

### Duplicate survey-line handling

Validation compares all survey details except the unique `line_id`: claim ID,
part name after trimming and case-folding, category, engine-part flag, part
cost, and labour cost. Only an exact match on those details is considered a
duplicate; repeated part names with different details remain valid. The
second copy is rejected and an error is recorded. In this pack,
`SVL-0114` duplicates `SVL-0077` for `CLM-013`, so `SVL-0114` is excluded
from assessment and reports.

## Command file format

`commands.txt` holds one command per line in the form `COMMAND_NAME|arg1|arg2|...`. Commands must be processed strictly in file order. Lines starting with `#` are comments and blank lines are ignored. Every command used in this pack:

| Command | Arguments (in order) | Meaning |
|---|---|---|
| `LOAD_POLICIES` | `file` | Load policies.csv |
| `LOAD_CLAIMS` | `file` | Load claims.csv |
| `LOAD_SURVEY` | `file` | Load survey_lines.csv |
| `ASSESS` | `claim_id|date` | Compute the claim (decision REPAIR / TOTAL_LOSS / REJECT / BELOW_THRESHOLD) |
| `THEFT_RECOVERED` | `claim_id|date` | Vehicle found; converts to REPAIR only if before day 90 from the FIR date |
| `SETTLE_THEFT` | `claim_id|date` | Settle a THEFT claim; rejected before day 90 from the FIR date |
| `RENEW` | `policy_id|renewal_date` | Renew for one year and recompute NCB from the year's claims |
| `PRINT_CLAIM_SHEET` | `claim_id` | Write the computation sheet |
| `PRINT_POLICY_HISTORY` | `policy_id` | Write the policy's claim history and NCB |

## Planted scenarios

Every edge case in the brief, mapped to the exact record where it occurs, followed by extra traps.

- **EC-01 Vehicle exactly 6 months old on incident date**
  - POL-001 vehicle bought 2026-03-20; incident 2026-09-20 10:30:00 = exactly 6 months → METAL depreciation 5% (6 m–1 y band), not 0% — `claims.csv CLM-014 (row 14); survey_lines.csv rows 84-91`
- **EC-02 Repair cost at exactly 75% of IDV**
  - Assessed repair cost (parts + labour before depreciation) = 11,81,250.00 = exactly 75% of IDV 15,75,000 → TOTAL_LOSS; corporate holder, customer keeps the wreck → IDV − excess 2,000 − salvage 1,57,500 — `claims.csv CLM-005 (row 5); survey_lines.csv rows 22-33`
- **EC-03 Intimation at hour 48 exactly**
  - Incident 2026-04-10 18:20:00, intimation 2026-04-12 18:20:00 = exactly 48:00:00 → NOT more than 48 h → no 10% delay deduction — `claims.csv CLM-002 (row 2)`
- **EC-04 Third ZERO_DEP claim in a policy year on a 4-year-old car**
  - POL-002 (XUV700 bought 2022-06-10, ~4 years old, ZERO_DEP): three claims in one policy year — the third (CLM-016) reverts to normal depreciation (METAL 35% for 4–5 years) — `claims.csv CLM-007 (row 7), claims.csv CLM-011 (row 11), claims.csv CLM-016 (row 16); survey_lines.csv rows 98-106`
- **EC-05 Theft recovered on day 90**
  - THEFT, FIR 2026-06-11 08:00:00; THEFT_RECOVERED dated 2026-09-09 = day 90 from the FIR date → not BEFORE day 90 → stays THEFT_SETTLEMENT (no conversion to REPAIR); SETTLE_THEFT the same day — `claims.csv CLM-004 (row 4); commands.txt lines 18, 19`
- **EC-06 Computed payable Rs 499.99**
  - Corporate holder (no GST): windshield 1,199.99 (GLASS 0%) + labour 300.00 = 1,499.99; 5 CONSUMABLE lines fully deducted (no add-on; the 50.00 labour on the sealant line is not paid); − compulsory excess 1,000 → payable 499.99 → BELOW_THRESHOLD, not paid, still counts for NCB at renewal — `claims.csv CLM-003 (row 3); survey_lines.csv rows 16-21; RENEW at commands.txt line 13`
- **EC-07 NCB 50% with NCB_PROTECT and two claims**
  - POL-005 has NCB 50% with NCB_PROTECT and two claims in the year (CLM-002, CLM-012) → protection covers only one → NCB resets to 0 at renewal — `claims.csv CLM-002 (row 2), claims.csv CLM-012 (row 12); RENEW at commands.txt line 29`
- **EC-08 Learner licence with ZERO_DEP**
  - Driver on LEARNER licence, policy has ZERO_DEP → depreciation waived, then payable capped at 50% — `claims.csv CLM-001 (row 1); survey_lines.csv rows 1-8`
- **Extra traps (not in the brief, but realistic):**
  - Intimation 7 days 1 hour after the incident → REJECT — `claims.csv CLM-015 (row 15)`
  - Intimation 50 h after the incident → 10% deduction on payable (after excess); includes PAINT lines (METAL rate on 50% of paint cost) — `claims.csv CLM-017 (row 17); survey_lines.csv rows 107-113`
  - Licence expired on 2026-06-14, incident 2026-06-15 → REJECT — `claims.csv CLM-006 (row 6)`
  - THEFT with FIR 25 h 30 min after the incident (> 24 h) → REJECT — `claims.csv CLM-018 (row 18)`
  - FLOOD on a POL-009 Fortuner over 5 years old: ZERO_DEP not available (normal depreciation) and 3 engine lines (engine_part = true) deducted — no ENGINE_PROTECT; voluntary excess 5,000 + compulsory 2,000 — `claims.csv CLM-009 (row 9); survey_lines.csv rows 47-54`
  - RTI on THEFT within the first policy year of a 2-month-old Nexon → pays invoice value 12,40,000 instead of IDV; SETTLE_THEFT at day 60 is premature (rejected), the one at day 91 settles — `claims.csv CLM-008 (row 8); commands.txt lines 20, 23`
  - POL-006: consumable lines without the CONSUMABLES add-on are fully deducted even though ZERO_DEP waives depreciation — `claims.csv CLM-010 (row 10); survey_lines.csv rows 55-61`
  - POL-010 has no claims → NCB 25% steps up to 35% at renewal — `commands.txt line 28`
  - Duplicate survey line: SVL-0114 repeats the part on SVL-0077 for CLM-013 → reject the second — `survey_lines.csv rows 77 and 114`
  - ASSESS for an unknown claim id → error line — `commands.txt line 27`

## What is NOT in this pack

Expected outputs are not provided for this set. Validate your engine with your own test suite against the rules in your brief (BR-01 … BR-12). A separate hidden input set with the same schema will be used at final evaluation; outputs are compared field-for-field, so follow the column formats above exactly in your own output.

## Output format expected at evaluation

Produce these CSV files (header row, same conventions as above, rows sorted as stated). Where the brief is silent on a format detail the choice below is binding for evaluation.

### `claim_lines.csv`

One row per survey line of every ASSESSed claim, in line_id order.

Columns, in order: `claim_id`, `line_id`, `part_category`, `part_cost`, `dep_pct`, `dep_amount`, `part_payable`, `labour_payable`, `line_status`

### `claim_sheet.csv`

One row per claim per PRINT_CLAIM_SHEET.

Columns, in order: `claim_id`, `policy_id`, `decision`, `assessed_repair_cost`, `parts_after_dep`, `labour_payable`, `gst`, `excess`, `delay_deduction`, `learner_cap_deduction`, `salvage_deduction`, `settlement_basis`, `payable`, `rule_ids`

### `policy_history.csv`

One row per policy per PRINT_POLICY_HISTORY (after all renewals).

Columns, in order: `policy_id`, `policy_start`, `policy_end`, `claims_counted`, `zero_dep_claims_used`, `ncb_before`, `ncb_after`, `renewed_on`

### `errors.csv`

Rejected commands and survey lines.

Columns, in order: `source`, `line_or_row`, `reference_id`, `reason`

Binding choices: computation order per claim — per-line depreciation → sum parts + labour → GST 18% (INDIVIDUAL only) → − excess (compulsory + voluntary) → − 10% delay deduction → learner cap 50% → round to paisa → BELOW_THRESHOLD test (< 500.00). Vehicle age bands use calendar months from vehicle_purchase_date to the incident date (exactly 6 months is in the 6 m–1 y band). "First policy year" for RTI means the incident is within 12 months of vehicle_purchase_date. Theft day count: day N = FIR date + N days. REJECTED claims do not count for NCB; every other decision (including BELOW_THRESHOLD) does. ZERO_DEP claims are counted in claim_id order within the policy year. `decision` is REPAIR, TOTAL_LOSS, THEFT_SETTLEMENT, REJECT or BELOW_THRESHOLD; `line_status` is PAID or REJECTED; `settlement_basis` is PARTS, IDV or INVOICE; `rule_ids` `;`-separated BR-nn.

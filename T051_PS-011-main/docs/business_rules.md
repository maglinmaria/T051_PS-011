# Motor Insurance Business Rules

This document records the 12 rules identified by the implementation as BR-01
through BR-12. Amounts are in rupees. Monetary calculations use `Decimal` and
are rounded to two decimal places using `ROUND_HALF_UP`, except where a rule
specifies a comparison against an already-rounded threshold.

## Rules

### BR-01 — Claim intimation and delay deduction

- Intimation must not precede the incident and must be received no later than
  seven days (168 hours) after it. A delay **greater than** 168 hours rejects
  the claim.
- For an accepted claim, a delay **greater than** 48 hours but not greater
  than seven days deducts 10% of the amount remaining after excess. Exactly
  48 hours has no delay deduction.
- In repair settlements, the delay deduction is applied after excess and
  before the learner-licence cap. In total-loss settlements, it is applied
  after excess and any salvage deduction, and before the learner cap.
- The policy must also be active on the incident date (inclusive of the start
  and end dates). An incident outside the policy period is rejected.

### BR-02 — Driving-licence validation

- `VALID` is accepted only when an expiry date is present and the licence is
  valid on the incident date. Expiry on the incident date is accepted; an
  incident after expiry is rejected.
- `EXPIRED` and `NONE` are rejected.
- `LEARNER` is accepted and caps the amount otherwise payable at 50%. The cap
  is applied after excess and any applicable delay deduction:

  `learner payable = round_half_up(amount before cap × 0.50)`

  This cap applies even when ZERO_DEP is used.

### BR-03 — Part depreciation

Vehicle age is the number of **completed calendar months** from
`vehicle_purchase_date` to the incident date. If the purchase-day anniversary
has not occurred in the incident month, one month is subtracted.

| Survey part category | Depreciation |
|---|---|
| `METAL` | Rate by vehicle age, as listed below |
| `PLASTIC`, `RUBBER`, `NYLON` | 50% of part cost |
| `GLASS` | 0% |
| `PAINT` | Metal rate applied to 50% of paint cost |
| `CONSUMABLE` | No depreciation calculation; coverage is handled under BR-05 |

| Completed vehicle age | Metal depreciation rate |
|---|---:|
| Less than 6 months | 0% |
| 6 to less than 12 months | 5% |
| 12 to less than 24 months | 10% |
| 24 to less than 36 months | 15% |
| 36 to less than 48 months | 25% |
| 48 through 60 months inclusive | 35% |
| More than 60 months | 50% |

For paint, the depreciation amount is
`paint cost × metal rate × 0.50`; the reported effective percentage is half
the metal rate. For other depreciated parts:
`depreciation amount = part cost × applicable rate`, and
`payable part cost = part cost − depreciation amount`.

Each line's depreciation amount and payable part amount are rounded to the
nearest paisa using `ROUND_HALF_UP`. Labour is not depreciated.

### BR-04 — ZERO_DEP add-on

ZERO_DEP waives depreciation on non-consumable parts only when all of these
conditions hold:

1. The policy includes `ZERO_DEP`.
2. Vehicle age is no more than 60 completed months.
3. Fewer than two earlier eligible ZERO_DEP claims have been counted for that
   policy during the policy year.

Earlier claims are considered in `claim_id` order. Only assessed,
non-rejected claims for which ZERO_DEP was actually applicable count toward
the two-claim limit. The third such claim uses standard depreciation. The
add-on does not waive consumables exclusions, excess, delay deductions, or
the learner cap. Its applicability is also recorded on a total-loss claim,
although it does not change an IDV-based total-loss amount.

### BR-05 — Consumables and Engine Protect

- A `CONSUMABLE` survey line is covered only when the policy has the
  `CONSUMABLES` add-on. Without it, that line is rejected: neither its part
  cost nor its labour is payable.
- A survey line marked `engine_part=true` on a `FLOOD` claim is covered only
  when the policy has `ENGINE_PROTECT`. Without it, the line's part and
  labour are rejected.
- These are line-level coverage decisions; an uncovered line does not by
  itself reject otherwise eligible repair lines. For a total-loss claim, the
  pre-depreciation assessed repair cost used for the 75% test includes all
  survey lines before line-coverage filtering.

### BR-06 — Compulsory and voluntary excess

Compulsory excess is based on engine capacity:

| Engine capacity | Compulsory excess |
|---|---:|
| Up to and including 1,500 cc | Rs 1,000 |
| Greater than 1,500 cc | Rs 2,000 |

`total excess = compulsory excess + policy voluntary excess`

The total excess is deducted in repair, total-loss, and theft settlements.
The repair and total-loss calculation floors the amount after deductions at
zero; theft payable is likewise not allowed below zero.

### BR-07 — Total loss and salvage

The assessed repair cost is the sum of all survey-line part costs and labour
costs **before depreciation**. The total-loss threshold is 75% of IDV,
rounded to two decimal places:

`total loss when assessed repair cost >= round_half_up(IDV × 0.75)`

The threshold is inclusive. A total-loss settlement starts from IDV, or from
invoice value when RTI is applicable (BR-08). The system then deducts total
excess. If `salvage_option=CUSTOMER_KEEPS`, it additionally deducts 10% of
IDV; no salvage deduction is made for `INSURER_TAKES`. Applicable delay
deduction and the learner cap follow. The amount is floored at zero. Part
depreciation does not determine the total-loss payout, although survey-line
details are retained in the computation output.

For example, sample claim CLM-005 has assessed repair cost Rs 11,81,250,
exactly 75% of its Rs 15,75,000 IDV, so the inclusive comparison selects
`TOTAL_LOSS`.

### BR-08 — Return to Invoice (RTI)

RTI requires the policy's `RTI` add-on, a vehicle age no greater than 36
completed months, and an incident within the first 12 months from
vehicle-purchase date. When applicable, invoice value replaces IDV as the
gross settlement basis for theft and total-loss settlements; excess is still
deducted. RTI does not apply to ordinary repair settlements.

**Boundary note:** the total-loss helper tests completed vehicle age as less
than 12 months. The command processor's theft path instead accepts an
incident date on or before the 12-calendar-month anniversary. The README does
not specify whether the anniversary date itself is inside the first year, so
this implementation difference is left explicit rather than reconciled here.

### BR-09 — Theft settlement and recovery

- A theft FIR must be filed from the incident time through exactly 24 hours
  after it. A delay greater than 24 hours rejects the theft claim.
- The 90-day waiting-period eligibility date is the FIR calendar date plus
  90 days. Settlement is allowed on that date or later; an earlier
  `SETTLE_THEFT` command is premature and does not create a settlement result.
- Recovery strictly before the eligibility date converts the theft to a
  repair assessment. Recovery on the eligibility date (day 90) or later does
  not convert it.
- Once eligible, theft settlement starts from IDV, or invoice value when RTI
  applies, and deducts total excess. The general claim-intimation rules
  (BR-01) and driving-licence rules (BR-02) also apply: intimation more than
  48 hours late receives the 10% deduction after excess, learner-licence
  claims are capped at 50% after that deduction, and invalid/expired licences
  or intimation beyond seven days are rejected.
- The theft path does not calculate repair parts, repair GST, or salvage
  deduction. The Rs 500 minimum threshold is not applied to theft settlement
  in this implementation.

### BR-10 — No Claim Bonus and renewal

The NCB slabs are `0% → 20% → 25% → 35% → 45% → 50%`; the maximum is 50%.
At renewal:

| Assessed claims in the expiring policy period | NCB without NCB_PROTECT | NCB with NCB_PROTECT |
|---|---|---|
| 0 | Advance one slab (maximum 50%) | Advance one slab (maximum 50%) |
| 1 | Reset to 0% | Retain current NCB |
| More than 1 | Reset to 0% | Reset to 0% |

Rejected claims and claims without an assessment result are not counted.
Every other assessed decision is counted, including `BELOW_THRESHOLD`.
Claims are assigned to a policy year by incident date within the inclusive
policy start/end dates. Renewal records the old period and its NCB result,
then advances the policy start to the renewal date and sets its end to 12
calendar months later minus one day.

### BR-11 — Labour and GST

- Labour is paid in full on covered survey lines and is never depreciated.
  Labour on an uncovered or rejected line is not paid.
- Repair GST is 18% of the post-depreciation covered parts plus payable
  labour for an `INDIVIDUAL` policyholder. It is zero for `CORPORATE`.
- GST is added before excess, delay deduction, and learner cap. The
  total-loss and theft paths do not add repair GST.

For repair calculations:

`repair subtotal = Σ covered payable parts + Σ covered labour`

`GST = round_half_up(repair subtotal × 0.18)` for `INDIVIDUAL`, otherwise 0.
The total excess is then subtracted, followed by any delay deduction and
learner cap.

### BR-12 — Minimum settlement threshold

After repair or total-loss deductions and final two-decimal rounding,
payable below Rs 500.00 produces `BELOW_THRESHOLD`. Exactly Rs 500.00 is not
below the threshold and remains payable. `BELOW_THRESHOLD` preserves the
calculated payable amount but denotes that it is not paid; it still counts
for NCB. For example, the sample corporate claim CLM-003 calculates
Rs 499.99 after excess and is `BELOW_THRESHOLD`; its five consumable lines
are excluded because there is no `CONSUMABLES` add-on. The threshold is not
applied in the theft settlement path.

## Calculation order summary

For a repair claim:

1. Assess surveyed parts plus labour before depreciation; check the total-loss
   threshold.
2. For a repair, calculate each line's coverage, depreciation, and payable
   labour, then sum covered parts and labour.
3. Add GST where the policyholder is an individual.
4. Deduct compulsory plus voluntary excess; floor at zero.
5. Apply the 10% late-intimation deduction when applicable.
6. Apply the learner cap when applicable; round to two decimals.
7. Classify amounts below Rs 500.00 as `BELOW_THRESHOLD`.

For a total loss, use the BR-07 settlement basis and deduction order instead
of repair-part totals. For theft, use the separate BR-09 process.

from datetime import date, timedelta
from decimal import Decimal

from src.models import Policy, Claim, SurveyLine
from src.state import ApplicationState

from src.constants import (
    MINIMUM_SETTLEMENT_AMOUNT,
    TOTAL_LOSS_THRESHOLD,
    SALVAGE_DEDUCTION_RATE,
    DELAY_DEDUCTION_RATE,
    DELAY_DEDUCTION_AFTER_HOURS,
    MAX_INTIMATION_DELAY_DAYS,
    LEARNER_LICENCE_MAX_PAYABLE_RATE,
    RTI_MAX_VEHICLE_AGE_MONTHS,
    RTI_POLICY_PERIOD_MONTHS,
)

from src.depreciation import (
    calculate_vehicle_age_months,
    calculate_line_depreciation,
    calculate_part_payable,
    round_money,
)

from src.settlement import (
    calculate_repair_settlement,
    calculate_total_excess,
    get_line_coverage_status,
)


# ==========================================================
# 1. RULE ID MANAGEMENT
# ==========================================================

def format_rule_ids(rule_ids: set[str]) -> str:
    """Return unique rule IDs in numerical order."""

    return ";".join(
        sorted(
            rule_ids,
            key=lambda value: int(value.split("-")[1]),
        )
    )


# ==========================================================
# 2. REJECTION RESULT
# ==========================================================

def create_rejection_result(
    policy: Policy,
    claim: Claim,
    survey_lines: list[SurveyLine],
    reason: str,
    rule_id: str,
) -> dict:
    """
    Create a rejected claim result.

    Rejected survey lines do not receive part or labour payment.
    """

    assessed_repair_cost = round_money(
        sum(
            (
                line.part_cost + line.labour_cost
                for line in survey_lines
            ),
            Decimal("0.00"),
        )
    )

    line_results = []

    for line in survey_lines:
        line_results.append({
            "claim_id": claim.claim_id,
            "line_id": line.line_id,
            "part_category": line.part_category,
            "part_cost": round_money(line.part_cost),
            "dep_pct": Decimal("0.00"),
            "dep_amount": Decimal("0.00"),
            "part_payable": Decimal("0.00"),
            "labour_payable": Decimal("0.00"),
            "line_status": "REJECTED",
        })

    return {
        "claim_id": claim.claim_id,
        "policy_id": policy.policy_id,
        "decision": "REJECT",
        "assessed_repair_cost": assessed_repair_cost,
        "parts_after_dep": Decimal("0.00"),
        "labour_payable": Decimal("0.00"),
        "gst": Decimal("0.00"),
        "excess": Decimal("0.00"),
        "delay_deduction": Decimal("0.00"),
        "learner_cap_deduction": Decimal("0.00"),
        "salvage_deduction": Decimal("0.00"),
        "settlement_basis": "PARTS",
        "payable": Decimal("0.00"),
        "rule_ids": rule_id,
        "reason": reason,
        "line_results": line_results,
        "zero_dep_applicable": False,
    }


# ==========================================================
# 3. LICENCE VALIDATION
# ==========================================================

def validate_driving_licence(claim: Claim) -> tuple[bool, str]:
    """
    Check the driving licence on the incident date.

    VALID:
        Accepted when the licence is valid on incident date.

    LEARNER:
        Accepted, but settlement is capped at 50%.

    EXPIRED / NONE:
        Rejected.
    """

    status = claim.driver_licence_status.upper()

    if status in {"EXPIRED", "NONE"}:
        return False, "Driver does not have a valid driving licence"

    if status == "LEARNER":
        return True, "Learner licence"

    if status != "VALID":
        return False, "Invalid driving licence status"

    if claim.licence_expiry_date is None:
        return False, "Missing driving licence expiry date"

    if claim.incident_ts.date() > claim.licence_expiry_date:
        return False, "Driving licence expired on incident date"

    return True, "Valid driving licence"


# ==========================================================
# 4. INTIMATION VALIDATION
# ==========================================================

def calculate_intimation_delay_hours(claim: Claim) -> Decimal:
    """Calculate the number of hours between incident and intimation."""

    difference = claim.intimation_ts - claim.incident_ts

    return (
        Decimal(str(difference.total_seconds()))
        / Decimal("3600")
    )


def validate_intimation(claim: Claim) -> tuple[bool, str]:
    """
    Reject when intimation occurs more than seven days
    after the incident.

    More than 48 hours but not more than seven days
    receives a 10% deduction instead.
    """

    if claim.intimation_ts < claim.incident_ts:
        return False, "Intimation is before incident"

    delay_hours = calculate_intimation_delay_hours(claim)

    maximum_hours = Decimal(
        str(MAX_INTIMATION_DELAY_DAYS * 24)
    )

    if delay_hours > maximum_hours:
        return False, "Intimation received more than 7 days after incident"

    return True, "Intimation accepted"


# ==========================================================
# 5. POLICY VALIDATION
# ==========================================================

def validate_policy_coverage(
    policy: Policy,
    claim: Claim,
) -> tuple[bool, str]:
    """Check whether the policy covers the incident date."""

    incident_date = claim.incident_ts.date()

    if not (
        policy.policy_start
        <= incident_date
        <= policy.policy_end
    ):
        return False, "Policy was not active on incident date"

    return True, "Policy active"


# ==========================================================
# 6. ZERO DEP CLAIM ELIGIBILITY
# ==========================================================

def count_previous_zero_dep_claims(
    policy: Policy,
    claim: Claim,
    app_state: ApplicationState,
) -> int:
    """
    Count earlier ZERO_DEP claims in the same policy year.

    Claims are considered in claim_id order.
    Only previously assessed, non-rejected claims
    with ZERO_DEP actually applied are counted.
    """

    current_claim_id = claim.claim_id

    previous_count = 0

    for previous_claim_id in sorted(app_state.claims):

        # Only earlier claim IDs are considered.
        if previous_claim_id >= current_claim_id:
            break

        previous_claim = app_state.claims[previous_claim_id]

        if previous_claim.policy_id != policy.policy_id:
            continue

        previous_incident_date = previous_claim.incident_ts.date()

        if not (
            policy.policy_start
            <= previous_incident_date
            <= policy.policy_end
        ):
            continue

        previous_result = app_state.claim_results.get(
            previous_claim_id
        )

        if previous_result is None:
            continue

        if previous_result.get("decision") == "REJECT":
            continue

        if previous_result.get("zero_dep_applicable") is True:
            previous_count += 1

    return previous_count


def is_zero_dep_applicable(
    policy: Policy,
    claim: Claim,
    app_state: ApplicationState,
    vehicle_age_months: int,
) -> bool:
    """
    ZERO_DEP eligibility conditions:

    1. Policy has ZERO_DEP add-on.
    2. Vehicle age does not exceed 60 months.
    3. Fewer than two earlier ZERO_DEP claims
       have been used during the policy year.
    """

    if "ZERO_DEP" not in policy.addons:
        return False

    if vehicle_age_months > 60:
        return False

    previous_claims = count_previous_zero_dep_claims(
        policy,
        claim,
        app_state,
    )

    return previous_claims < 2


# ==========================================================
# 7. RTI ELIGIBILITY
# ==========================================================

def is_rti_applicable(
    policy: Policy,
    claim: Claim,
    vehicle_age_months: int,
) -> bool:
    """
    RTI eligibility:

    1. RTI add-on is present.
    2. Vehicle age does not exceed three years.
    3. Incident occurs within the first 12 months
       from vehicle purchase date.
    """

    if "RTI" not in policy.addons:
        return False

    if vehicle_age_months > RTI_MAX_VEHICLE_AGE_MONTHS:
        return False

    purchase_age_months = calculate_vehicle_age_months(
        policy.vehicle_purchase_date,
        claim.incident_ts.date(),
    )

    return (
        0 <= purchase_age_months < RTI_POLICY_PERIOD_MONTHS
    )


# ==========================================================
# 8. CALCULATE ASSESSED REPAIR COST
# ==========================================================

def calculate_assessed_repair_cost(
    survey_lines: list[SurveyLine],
) -> Decimal:
    """
    Calculate total surveyed repair cost before depreciation.

    Assessed cost = all part costs + all labour costs.
    """

    total = sum(
        (
            line.part_cost + line.labour_cost
            for line in survey_lines
        ),
        Decimal("0.00"),
    )

    return round_money(total)


# ==========================================================
# 9. CALCULATE TOTAL LOSS SETTLEMENT
# ==========================================================
def calculate_total_loss_settlement(
    policy: Policy,
    claim: Claim,
    survey_lines: list[SurveyLine],
    assessed_repair_cost: Decimal,
    vehicle_age_months: int,
    delay_hours: Decimal,
    zero_dep_applicable: bool,
) -> dict:
    """
    Calculate total-loss settlement.

    Total loss applies when assessed repair cost is
    at least 75% of IDV.

    Settlement:
        IDV or eligible RTI invoice value
        - compulsory and voluntary excess
        - salvage deduction, if customer keeps wreck
        - applicable delay deduction
        - learner licence cap, if applicable
    """

    rule_ids = {"BR-07", "BR-06"}

    # Determine settlement basis.
    if is_rti_applicable(
        policy,
        claim,
        vehicle_age_months,
    ):
        gross_settlement = policy.invoice_value
        settlement_basis = "INVOICE"
        rule_ids.add("BR-08")
    else:
        gross_settlement = policy.idv
        settlement_basis = "IDV"

    # Excess deduction.
    excess = calculate_total_excess(policy)

    amount_after_excess = max(
        Decimal("0.00"),
        round_money(gross_settlement - excess),
    )

    # Salvage deduction when customer keeps the wreck.
    salvage_deduction = Decimal("0.00")

    if claim.salvage_option == "CUSTOMER_KEEPS":
        salvage_deduction = round_money(
            policy.idv * SALVAGE_DEDUCTION_RATE
        )

        rule_ids.add("BR-07")

    amount_after_salvage = max(
        Decimal("0.00"),
        round_money(amount_after_excess - salvage_deduction),
    )

    # Late intimation deduction.
    delay_deduction = Decimal("0.00")

    if delay_hours > Decimal(
        str(DELAY_DEDUCTION_AFTER_HOURS)
    ):
        delay_deduction = round_money(
            amount_after_salvage * DELAY_DEDUCTION_RATE
        )

        rule_ids.add("BR-01")

    amount_after_delay = max(
        Decimal("0.00"),
        round_money(amount_after_salvage - delay_deduction),
    )

    # Learner licence cap.
    learner_cap_deduction = Decimal("0.00")

    if claim.driver_licence_status == "LEARNER":
        maximum_payable = round_money(
            amount_after_delay
            * LEARNER_LICENCE_MAX_PAYABLE_RATE
        )

        learner_cap_deduction = round_money(
            amount_after_delay - maximum_payable
        )

        amount_after_delay = maximum_payable
        rule_ids.add("BR-02")

    # ZERO_DEP has no effect on a total-loss IDV settlement,
    # but its use is recorded for policy-year claim tracking.
    if zero_dep_applicable:
        rule_ids.add("BR-04")

    # Final threshold.
    payable = round_money(amount_after_delay)

    if payable < MINIMUM_SETTLEMENT_AMOUNT:
        decision = "BELOW_THRESHOLD"
        # Preserve the calculated payable amount.
        # BELOW_THRESHOLD means the amount is not paid.
        rule_ids.add("BR-12")
    else:
        decision = "TOTAL_LOSS"

    # Record survey lines for the computation sheet.
    line_results = []

    for line in survey_lines:
        covered, reason = get_line_coverage_status(
            claim,
            policy,
            line,
        )

        if not covered:
            line_results.append({
                "claim_id": claim.claim_id,
                "line_id": line.line_id,
                "part_category": line.part_category,
                "part_cost": round_money(line.part_cost),
                "dep_pct": Decimal("0.00"),
                "dep_amount": Decimal("0.00"),
                "part_payable": Decimal("0.00"),
                "labour_payable": Decimal("0.00"),
                "line_status": "REJECTED",
            })
            rule_ids.add("BR-05")
            continue

        dep_pct, dep_amount = calculate_line_depreciation(
            line.part_category,
            line.part_cost,
            vehicle_age_months,
            zero_dep_applicable=(
                zero_dep_applicable
                and line.part_category != "CONSUMABLE"
            ),
        )

        part_payable = calculate_part_payable(
            line.part_cost,
            dep_amount,
        )

        line_results.append({
            "claim_id": claim.claim_id,
            "line_id": line.line_id,
            "part_category": line.part_category,
            "part_cost": round_money(line.part_cost),
            "dep_pct": dep_pct,
            "dep_amount": dep_amount,
            "part_payable": part_payable,
            "labour_payable": round_money(line.labour_cost),
            "line_status": "PAID",
        })

    if vehicle_age_months >= 6:
        rule_ids.add("BR-03")

    return {
        "claim_id": claim.claim_id,
        "policy_id": policy.policy_id,
        "decision": decision,
        "assessed_repair_cost": assessed_repair_cost,
        "parts_after_dep": Decimal("0.00"),
        "labour_payable": Decimal("0.00"),
        "gst": Decimal("0.00"),
        "excess": excess,
        "delay_deduction": delay_deduction,
        "learner_cap_deduction": learner_cap_deduction,
        "salvage_deduction": salvage_deduction,
        "settlement_basis": settlement_basis,
        "payable": payable,
        "rule_ids": format_rule_ids(rule_ids),
        "line_results": line_results,
        "zero_dep_applicable": zero_dep_applicable,
    }


# ==========================================================
# 10. MAIN CLAIM ASSESSMENT ENGINE
# ==========================================================

def assess_claim(
    app_state: ApplicationState,
    claim_id: str,
    assessment_date: date,
) -> dict:
    """
    Assess a motor insurance claim.

    This function coordinates:
        Policy validation
        Licence validation
        Intimation validation
        Depreciation
        ZERO_DEP
        Add-on coverage
        Repair settlement
        Total-loss settlement
        Minimum settlement threshold

    THEFT claims are handled separately by theft.py
    and the command processor.
    """

    # ------------------------------------------------------
    # CHECK CLAIM EXISTENCE
    # ------------------------------------------------------

    if claim_id not in app_state.claims:
        raise ValueError(f"Unknown claim ID: {claim_id}")

    claim = app_state.claims[claim_id]

    # ------------------------------------------------------
    # CHECK POLICY EXISTENCE
    # ------------------------------------------------------

    if claim.policy_id not in app_state.policies:
        raise ValueError(
            f"Unknown policy ID: {claim.policy_id}"
        )

    policy = app_state.policies[claim.policy_id]

    survey_lines = app_state.survey_lines.get(
        claim_id,
        [],
    )

    # ------------------------------------------------------
    # THEFT CLAIMS USE A SEPARATE PROCESS
    # ------------------------------------------------------

    if claim.cause == "THEFT":
        raise ValueError(
            "THEFT claims must be processed using SETTLE_THEFT"
        )

    # ------------------------------------------------------
    # CHECK ASSESSMENT DATE
    # ------------------------------------------------------

    if assessment_date < claim.incident_ts.date():
        raise ValueError(
            "Assessment date cannot be before incident date"
        )

    # ------------------------------------------------------
    # CALCULATE VEHICLE AGE
    # ------------------------------------------------------

    vehicle_age_months = calculate_vehicle_age_months(
        policy.vehicle_purchase_date,
        claim.incident_ts.date(),
    )

    # ------------------------------------------------------
    # RULE BR-01: INTIMATION VALIDATION
    # ------------------------------------------------------

    intimation_valid, intimation_reason = validate_intimation(
        claim
    )

    if not intimation_valid:
        result = create_rejection_result(
            policy,
            claim,
            survey_lines,
            intimation_reason,
            "BR-01",
        )

        app_state.claim_results[claim_id] = result
        return result

    delay_hours = calculate_intimation_delay_hours(claim)

    # ------------------------------------------------------
    # RULE BR-02: LICENCE VALIDATION
    # ------------------------------------------------------

    licence_valid, licence_reason = validate_driving_licence(
        claim
    )

    if not licence_valid:
        result = create_rejection_result(
            policy,
            claim,
            survey_lines,
            licence_reason,
            "BR-02",
        )

        app_state.claim_results[claim_id] = result
        return result

    # ------------------------------------------------------
    # CHECK POLICY COVERAGE
    # ------------------------------------------------------

    policy_valid, policy_reason = validate_policy_coverage(
        policy,
        claim,
    )

    if not policy_valid:
        result = create_rejection_result(
            policy,
            claim,
            survey_lines,
            policy_reason,
            "BR-01",
        )

        app_state.claim_results[claim_id] = result
        return result

    # ------------------------------------------------------
    # ZERO_DEP ELIGIBILITY
    # ------------------------------------------------------

    zero_dep_applicable = is_zero_dep_applicable(
        policy,
        claim,
        app_state,
        vehicle_age_months,
    )

    # ------------------------------------------------------
    # ASSESSED REPAIR COST
    # ------------------------------------------------------

    assessed_repair_cost = calculate_assessed_repair_cost(
        survey_lines
    )

    # ------------------------------------------------------
    # RULE BR-07: TOTAL LOSS CHECK
    # ------------------------------------------------------

    total_loss_limit = round_money(
        policy.idv * TOTAL_LOSS_THRESHOLD
    )

    if assessed_repair_cost >= total_loss_limit:

        result = calculate_total_loss_settlement(
            policy=policy,
            claim=claim,
            survey_lines=survey_lines,
            assessed_repair_cost=assessed_repair_cost,
            vehicle_age_months=vehicle_age_months,
            delay_hours=delay_hours,
            zero_dep_applicable=zero_dep_applicable,
        )

        app_state.claim_results[claim_id] = result
        return result

    # ------------------------------------------------------
    # NORMAL REPAIR SETTLEMENT
    # ------------------------------------------------------

    result = calculate_repair_settlement(
        policy=policy,
        claim=claim,
        survey_lines=survey_lines,
        vehicle_age_months=vehicle_age_months,
        zero_dep_applicable=zero_dep_applicable,
    )

    # ------------------------------------------------------
    # BUILD RULE ID LIST
    # ------------------------------------------------------

    rule_ids = {
        "BR-03",
        "BR-06",
        "BR-11",
        "BR-12",
    }

    if delay_hours > Decimal(
        str(DELAY_DEDUCTION_AFTER_HOURS)
    ):
        rule_ids.add("BR-01")

    if claim.driver_licence_status == "LEARNER":
        rule_ids.add("BR-02")

    if zero_dep_applicable:
        rule_ids.add("BR-04")

    if any(
        line["line_status"] != "COVERED"
        for line in result["line_results"]
    ):
        rule_ids.add("BR-05")

    if vehicle_age_months >= 6:
        rule_ids.add("BR-03")

    # ------------------------------------------------------
    # NORMALIZE LINE STATUSES
    # ------------------------------------------------------

    for line_result in result["line_results"]:

        if line_result["line_status"] == "COVERED":
            line_result["line_status"] = "PAID"
        else:
            line_result["line_status"] = "REJECTED"

    # ------------------------------------------------------
    # FINAL RESULT
    # ------------------------------------------------------

    result["rule_ids"] = format_rule_ids(rule_ids)
    result["zero_dep_applicable"] = zero_dep_applicable
    result["delay_hours"] = delay_hours
    result["vehicle_age_months"] = vehicle_age_months

    if result["decision"] == "BELOW_THRESHOLD":
        rule_ids.add("BR-12")
        result["rule_ids"] = format_rule_ids(rule_ids)

    # Save result for NCB and policy history.
    app_state.claim_results[claim_id] = result

    return result

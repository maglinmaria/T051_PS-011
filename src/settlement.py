
from datetime import datetime
from decimal import Decimal

from src.models import Policy, Claim, SurveyLine
from src.constants import (
    GST_RATE,
    MINIMUM_SETTLEMENT_AMOUNT,
    COMPULSORY_EXCESS_UP_TO_1500CC,
    COMPULSORY_EXCESS_ABOVE_1500CC,
    DELAY_DEDUCTION_AFTER_HOURS,
    DELAY_DEDUCTION_RATE,
    LEARNER_LICENCE_MAX_PAYABLE_RATE,
)
from src.depreciation import (
    calculate_line_depreciation,
    calculate_part_payable,
    round_money,
)


# ==========================================================
# 1. COMPULSORY EXCESS
# ==========================================================

def calculate_compulsory_excess(engine_cc: int) -> Decimal:
    """
    Calculate compulsory excess based on engine capacity.

    Up to and including 1500cc: Rs. 1,000
    Above 1500cc: Rs. 2,000
    """

    if engine_cc <= 0:
        raise ValueError("Engine capacity must be positive")

    if engine_cc <= 1500:
        return COMPULSORY_EXCESS_UP_TO_1500CC

    return COMPULSORY_EXCESS_ABOVE_1500CC


# ==========================================================
# 2. TOTAL EXCESS
# ==========================================================

def calculate_total_excess(policy: Policy) -> Decimal:
    """
    Total excess = compulsory excess + voluntary excess.
    """

    compulsory = calculate_compulsory_excess(
        policy.engine_cc
    )

    if policy.voluntary_excess < Decimal("0"):
        raise ValueError("Voluntary excess cannot be negative")

    return round_money(
        compulsory + policy.voluntary_excess
    )


# ==========================================================
# 3. CHECK ADD-ON COVERAGE FOR SURVEY LINES
# ==========================================================

def get_line_coverage_status(
    claim: Claim,
    policy: Policy,
    line: SurveyLine,
) -> tuple[bool, str]:
    """
    Determine whether a survey line is covered.

    CONSUMABLES:
        Requires the CONSUMABLES add-on.

    FLOOD engine damage:
        Requires ENGINE_PROTECT.

    Other parts:
        Covered under the normal repair calculation.
    """

    category = line.part_category.strip().upper()

    if category == "CONSUMABLE":
        if "CONSUMABLES" not in policy.addons:
            return False, "CONSUMABLES_ADDON_MISSING"

    if (
        claim.cause == "FLOOD"
        and line.engine_part
        and "ENGINE_PROTECT" not in policy.addons
    ):
        return False, "ENGINE_PROTECT_ADDON_MISSING"

    return True, "COVERED"


# ==========================================================
# 4. CALCULATE INDIVIDUAL SURVEY LINE
# ==========================================================

def calculate_survey_line(
    claim: Claim,
    policy: Policy,
    line: SurveyLine,
    vehicle_age_months: int,
    zero_dep_applicable: bool = False,
) -> dict:
    """
    Calculate depreciation and payable amounts
    for one survey line.

    Labour is paid in full only for covered lines.
    """

    covered, coverage_reason = get_line_coverage_status(
        claim,
        policy,
        line,
    )

    if not covered:
        return {
            "claim_id": claim.claim_id,
            "line_id": line.line_id,
            "part_category": line.part_category,
            "part_cost": round_money(line.part_cost),
            "dep_pct": Decimal("0.00"),
            "dep_amount": Decimal("0.00"),
            "part_payable": Decimal("0.00"),
            "labour_payable": Decimal("0.00"),
            "line_status": coverage_reason,
        }

    # Calculate depreciation.
    dep_pct, dep_amount = calculate_line_depreciation(
        part_category=line.part_category,
        part_cost=line.part_cost,
        vehicle_age_months=vehicle_age_months,
        zero_dep_applicable=(
            zero_dep_applicable
            and line.part_category.strip().upper() != "CONSUMABLE"
        ),
    )

    # Calculate part value after depreciation.
    part_payable = calculate_part_payable(
        line.part_cost,
        dep_amount,
    )

    # Labour is fully payable on covered parts.
    labour_payable = round_money(line.labour_cost)

    return {
        "claim_id": claim.claim_id,
        "line_id": line.line_id,
        "part_category": line.part_category,
        "part_cost": round_money(line.part_cost),
        "dep_pct": dep_pct,
        "dep_amount": dep_amount,
        "part_payable": part_payable,
        "labour_payable": labour_payable,
        "line_status": "COVERED",
    }


# ==========================================================
# 5. CALCULATE CLAIM INTIMATION DELAY
# ==========================================================

def calculate_intimation_delay_hours(claim: Claim) -> Decimal:
    """Return the delay between incident and intimation in hours."""

    difference = claim.intimation_ts - claim.incident_ts

    return Decimal(str(difference.total_seconds())) / Decimal("3600")


# ==========================================================
# 6. CALCULATE DELAY DEDUCTION
# ==========================================================

def calculate_delay_deduction(
    amount: Decimal,
    claim: Claim,
) -> Decimal:
    """
    Deduct 10% when intimation occurs more than 48 hours
    after the incident.
    """

    delay_hours = calculate_intimation_delay_hours(claim)

    if delay_hours > DELAY_DEDUCTION_AFTER_HOURS:
        return round_money(
            amount * DELAY_DEDUCTION_RATE
        )

    return Decimal("0.00")


# ==========================================================
# 7. CALCULATE LEARNER LICENCE CAP
# ==========================================================

def calculate_learner_cap(
    amount: Decimal,
    claim: Claim,
) -> tuple[Decimal, Decimal]:
    """
    Learner licence claims are limited to 50%
    of the otherwise payable amount.

    Returns:
        Final payable amount, learner cap deduction.
    """

    if claim.driver_licence_status != "LEARNER":
        return round_money(amount), Decimal("0.00")

    maximum_payable = round_money(
        amount * LEARNER_LICENCE_MAX_PAYABLE_RATE
    )

    deduction = round_money(
        amount - maximum_payable
    )

    return maximum_payable, deduction


# ==========================================================
# 8. COMPLETE REPAIR SETTLEMENT CALCULATION
# ==========================================================

def calculate_repair_settlement(
    policy: Policy,
    claim: Claim,
    survey_lines: list[SurveyLine],
    vehicle_age_months: int,
    zero_dep_applicable: bool = False,
) -> dict:
    """
    Calculate a repair claim settlement.

    Calculation order:
        1. Calculate assessed repair cost before depreciation.
        2. Calculate depreciation for each survey line.
        3. Sum payable parts and labour.
        4. Add GST for INDIVIDUAL policyholders only.
        5. Deduct compulsory and voluntary excess.
        6. Deduct 10% for intimation after 48 hours.
        7. Apply learner licence 50% cap.
        8. Round final payable amount.
        9. Apply the Rs. 500 minimum settlement threshold.

    Total-loss and theft decisions are handled separately.
    """

    # ------------------------------------------------------
    # STEP 1: ASSESSED REPAIR COST BEFORE DEPRECIATION
    # ------------------------------------------------------

    assessed_repair_cost = round_money(
        sum(
            (
                line.part_cost + line.labour_cost
                for line in survey_lines
            ),
            Decimal("0.00"),
        )
    )

    # ------------------------------------------------------
    # STEP 2: CALCULATE EACH SURVEY LINE
    # ------------------------------------------------------

    line_results = []

    for line in survey_lines:
        result = calculate_survey_line(
            claim=claim,
            policy=policy,
            line=line,
            vehicle_age_months=vehicle_age_months,
            zero_dep_applicable=zero_dep_applicable,
        )

        line_results.append(result)

    # ------------------------------------------------------
    # STEP 3: SUM PAYABLE PARTS AND LABOUR
    # ------------------------------------------------------

    parts_after_dep = round_money(
        sum(
            (
                result["part_payable"]
                for result in line_results
            ),
            Decimal("0.00"),
        )
    )

    labour_payable = round_money(
        sum(
            (
                result["labour_payable"]
                for result in line_results
            ),
            Decimal("0.00"),
        )
    )

    subtotal = round_money(
        parts_after_dep + labour_payable
    )

    # ------------------------------------------------------
    # STEP 4: GST
    # ------------------------------------------------------

    if policy.holder_type == "INDIVIDUAL":
        gst = round_money(subtotal * GST_RATE)

    elif policy.holder_type == "CORPORATE":
        gst = Decimal("0.00")

    else:
        raise ValueError(
            f"Unsupported policyholder type: {policy.holder_type}"
        )

    amount_with_gst = round_money(
        subtotal + gst
    )

    # ------------------------------------------------------
    # STEP 5: DEDUCT TOTAL EXCESS
    # ------------------------------------------------------

    excess = calculate_total_excess(policy)

    amount_after_excess = max(
        Decimal("0.00"),
        round_money(amount_with_gst - excess),
    )

    # ------------------------------------------------------
    # STEP 6: INTIMATION DELAY DEDUCTION
    # ------------------------------------------------------

    delay_deduction = calculate_delay_deduction(
        amount_after_excess,
        claim,
    )

    amount_after_delay = max(
        Decimal("0.00"),
        round_money(amount_after_excess - delay_deduction),
    )

    # ------------------------------------------------------
    # STEP 7: LEARNER LICENCE CAP
    # ------------------------------------------------------

    amount_after_learner_cap, learner_cap_deduction = (
        calculate_learner_cap(
            amount_after_delay,
            claim,
        )
    )

    # ------------------------------------------------------
    # STEP 8: FINAL ROUNDING
    # ------------------------------------------------------

    payable = round_money(
        max(
            Decimal("0.00"),
            amount_after_learner_cap,
        )
    )

    # ------------------------------------------------------
    # STEP 9: MINIMUM SETTLEMENT THRESHOLD
    # ------------------------------------------------------

    decision = "REPAIR"

    if payable < MINIMUM_SETTLEMENT_AMOUNT:
        decision = "BELOW_THRESHOLD"

    # ------------------------------------------------------
    # RETURN COMPLETE SETTLEMENT RESULT
    # ------------------------------------------------------

    return {
        "claim_id": claim.claim_id,
        "policy_id": policy.policy_id,
        "decision": decision,
        "assessed_repair_cost": assessed_repair_cost,
        "parts_after_dep": parts_after_dep,
        "labour_payable": labour_payable,
        "gst": gst,
        "excess": excess,
        "delay_deduction": delay_deduction,
        "learner_cap_deduction": learner_cap_deduction,
        "salvage_deduction": Decimal("0.00"),
        "settlement_basis": "PARTS",
        "payable": payable,
        "line_results": line_results,
    }

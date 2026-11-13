
from datetime import date, timedelta
from decimal import Decimal

from src.models import Policy, Claim
from src.constants import (
    THEFT_FIR_MAX_DELAY_HOURS,
    THEFT_WAITING_PERIOD_DAYS,
    RTI_MAX_VEHICLE_AGE_MONTHS,
    RTI_POLICY_PERIOD_MONTHS,
)
from src.settlement import calculate_total_excess
from src.depreciation import (
    calculate_vehicle_age_months,
    round_money,
)


# ==========================================================
# 1. FIR DELAY CALCULATION
# ==========================================================

def calculate_fir_delay_hours(claim: Claim) -> Decimal:
    """Calculate hours between theft incident and FIR."""

    if claim.cause != "THEFT":
        raise ValueError("FIR delay applies only to theft claims")

    if claim.fir_ts is None:
        raise ValueError("Theft claim has no FIR timestamp")

    difference = claim.fir_ts - claim.incident_ts

    return (
        Decimal(str(difference.total_seconds()))
        / Decimal("3600")
    )


# ==========================================================
# 2. FIR DEADLINE VALIDATION
# ==========================================================

def is_fir_within_deadline(claim: Claim) -> bool:
    """
    FIR must be filed within 24 hours of the theft.

    Exactly 24 hours is allowed.
    More than 24 hours is rejected.
    """

    fir_delay = calculate_fir_delay_hours(claim)

    return (
        Decimal("0") <= fir_delay
        <= Decimal(str(THEFT_FIR_MAX_DELAY_HOURS))
    )


# ==========================================================
# 3. CALCULATE THE 90-DAY WAITING PERIOD
# ==========================================================

def get_theft_settlement_eligibility_date(
    claim: Claim,
) -> date:
    """
    Return the date on which the 90-day waiting
    period is completed.

    Day N = FIR date + N calendar days.
    """

    if claim.cause != "THEFT":
        raise ValueError("Claim is not a theft claim")

    if claim.fir_ts is None:
        raise ValueError("Theft claim has no FIR timestamp")

    return (
        claim.fir_ts.date()
        + timedelta(days=THEFT_WAITING_PERIOD_DAYS)
    )


# ==========================================================
# 4. CHECK WAITING PERIOD
# ==========================================================

def is_theft_waiting_period_complete(
    claim: Claim,
    settlement_date: date,
) -> bool:
    """Check whether the 90-day waiting period is complete."""

    eligibility_date = get_theft_settlement_eligibility_date(
        claim
    )

    return settlement_date >= eligibility_date


# ==========================================================
# 5. CHECK VEHICLE RECOVERY
# ==========================================================

def was_vehicle_recovered_before_day_90(
    claim: Claim,
    recovery_date: date,
) -> bool:
    """
    Recovery before day 90 converts the theft claim
    into a REPAIR claim.

    Recovery exactly on day 90 does not convert it.
    """

    eligibility_date = get_theft_settlement_eligibility_date(
        claim
    )

    return recovery_date < eligibility_date


# ==========================================================
# 6. DETERMINE THE THEFT CLAIM OUTCOME
# ==========================================================

def determine_theft_outcome(
    claim: Claim,
    action_date: date,
    recovery_date: date | None = None,
) -> str:
    """
    Determine the theft claim outcome.

    Possible results:
        REJECT
        REPAIR
        THEFT_SETTLEMENT
        WAITING_PERIOD_NOT_COMPLETED
    """

    if claim.cause != "THEFT":
        raise ValueError("Claim is not a theft claim")

    # First check the FIR deadline.
    if not is_fir_within_deadline(claim):
        return "REJECT"

    # Check whether the vehicle was recovered before day 90.
    if recovery_date is not None:
        if was_vehicle_recovered_before_day_90(
            claim,
            recovery_date,
        ):
            return "REPAIR"

    # Check whether the waiting period has finished.
    if not is_theft_waiting_period_complete(
        claim,
        action_date,
    ):
        return "WAITING_PERIOD_NOT_COMPLETED"

    return "THEFT_SETTLEMENT"


# ==========================================================
# 7. CHECK RTI ELIGIBILITY
# ==========================================================

def is_rti_eligible(
    policy: Policy,
    claim: Claim,
    vehicle_age_months: int,
) -> bool:
    """
    RTI is applicable when:

    1. Policy has RTI add-on.
    2. Incident occurs within first 12 months
       from vehicle purchase date.
    3. Vehicle age does not exceed 3 years.
    4. Claim cause is TOTAL LOSS or THEFT.

    For this function, the eligible claim cause is THEFT.
    Total-loss eligibility is handled by the claim engine.
    """

    if claim.cause != "THEFT":
        return False

    if "RTI" not in policy.addons:
        return False

    if vehicle_age_months > RTI_MAX_VEHICLE_AGE_MONTHS:
        return False

    incident_date = claim.incident_ts.date()

    incident_age_months = calculate_vehicle_age_months(
        policy.vehicle_purchase_date,
        incident_date,
    )

    return (
        0 <= incident_age_months < RTI_POLICY_PERIOD_MONTHS
    )


# ==========================================================
# 8. CALCULATE THEFT SETTLEMENT
# ==========================================================

def calculate_theft_settlement(
    policy: Policy,
    claim: Claim,
    settlement_date: date,
    recovery_date: date | None = None,
) -> dict:
    """
    Calculate the final theft settlement.

    Settlement amount:
        IDV - applicable excess

    If RTI is eligible:
        Invoice value - applicable excess

    Theft settlement does not use repair-part depreciation
    or repair GST calculations.
    """

    if claim.policy_id != policy.policy_id:
        raise ValueError(
            "Claim and policy IDs do not match"
        )

    outcome = determine_theft_outcome(
        claim=claim,
        action_date=settlement_date,
        recovery_date=recovery_date,
    )

    # ------------------------------------------------------
    # REJECTED THEFT CLAIM
    # ------------------------------------------------------

    if outcome == "REJECT":
        return {
            "claim_id": claim.claim_id,
            "policy_id": policy.policy_id,
            "decision": "REJECT",
            "settlement_status": "REJECTED",
            "settlement_basis": "NONE",
            "gross_settlement": Decimal("0.00"),
            "excess": Decimal("0.00"),
            "payable": Decimal("0.00"),
            "reason": "FIR filed more than 24 hours after theft",
        }

    # ------------------------------------------------------
    # VEHICLE RECOVERED BEFORE DAY 90
    # ------------------------------------------------------

    if outcome == "REPAIR":
        return {
            "claim_id": claim.claim_id,
            "policy_id": policy.policy_id,
            "decision": "REPAIR",
            "settlement_status": "CONVERTED_TO_REPAIR",
            "settlement_basis": "PARTS",
            "gross_settlement": Decimal("0.00"),
            "excess": Decimal("0.00"),
            "payable": Decimal("0.00"),
            "reason": "Vehicle recovered before day 90",
        }

    # ------------------------------------------------------
    # WAITING PERIOD NOT COMPLETED
    # ------------------------------------------------------

    if outcome == "WAITING_PERIOD_NOT_COMPLETED":
        eligibility_date = get_theft_settlement_eligibility_date(
            claim
        )

        return {
            "claim_id": claim.claim_id,
            "policy_id": policy.policy_id,
            "decision": "THEFT_SETTLEMENT",
            "settlement_status": "WAITING_PERIOD",
            "settlement_basis": "NONE",
            "gross_settlement": Decimal("0.00"),
            "excess": Decimal("0.00"),
            "payable": Decimal("0.00"),
            "eligible_on": eligibility_date,
            "reason": "90-day waiting period not completed",
        }

    # ------------------------------------------------------
    # DETERMINE IDV OR RTI INVOICE VALUE
    # ------------------------------------------------------

    vehicle_age_months = calculate_vehicle_age_months(
        policy.vehicle_purchase_date,
        claim.incident_ts.date(),
    )

    if is_rti_eligible(
        policy,
        claim,
        vehicle_age_months,
    ):
        gross_settlement = policy.invoice_value
        settlement_basis = "INVOICE"
    else:
        gross_settlement = policy.idv
        settlement_basis = "IDV"

    # ------------------------------------------------------
    # DEDUCT COMPULSORY + VOLUNTARY EXCESS
    # ------------------------------------------------------

    excess = calculate_total_excess(policy)

    payable = max(
        Decimal("0.00"),
        round_money(gross_settlement - excess),
    )

    # ------------------------------------------------------
    # RETURN SETTLEMENT RESULT
    # ------------------------------------------------------

    return {
        "claim_id": claim.claim_id,
        "policy_id": policy.policy_id,
        "decision": "THEFT_SETTLEMENT",
        "settlement_status": "SETTLEMENT_READY",
        "settlement_basis": settlement_basis,
        "gross_settlement": round_money(gross_settlement),
        "excess": excess,
        "payable": payable,
        "eligible_on": get_theft_settlement_eligibility_date(
            claim
        ),
        "reason": "90-day waiting period completed",
    }

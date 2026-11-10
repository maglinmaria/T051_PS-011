
from datetime import date
from decimal import Decimal

from src.models import Policy
from src.state import ApplicationState
from src.constants import (
    NCB_SLABS,
    NCB_PROTECT_MAX_CLAIMS,
    NCB_RESET_VALUE,
)


# ==========================================================
# 1. DETERMINE THE NEXT NCB SLAB
# ==========================================================

def get_next_ncb_slab(current_ncb: Decimal) -> Decimal:
    """
    Return the next NCB slab.

    Progression:
        0 -> 20 -> 25 -> 35 -> 45 -> 50

    NCB cannot exceed 50%.
    """

    if current_ncb not in NCB_SLABS:
        raise ValueError(
            f"Invalid current NCB percentage: {current_ncb}"
        )

    current_index = NCB_SLABS.index(current_ncb)

    if current_index == len(NCB_SLABS) - 1:
        return NCB_SLABS[-1]

    return NCB_SLABS[current_index + 1]


# ==========================================================
# 2. CALCULATE NCB AFTER RENEWAL
# ==========================================================

def calculate_next_ncb(
    current_ncb: Decimal,
    claims_counted: int,
    ncb_protect: bool = False,
) -> Decimal:
    """
    Calculate NCB for the next policy period.

    Rules:
        No claims:
            Move to the next NCB slab.

        One claim without NCB Protect:
            Reset NCB to zero.

        One claim with NCB Protect:
            Retain existing NCB.

        More than one claim:
            Reset NCB to zero, even with NCB Protect.
    """

    if current_ncb not in NCB_SLABS:
        raise ValueError(
            f"Invalid current NCB percentage: {current_ncb}"
        )

    if claims_counted < 0:
        raise ValueError("Claim count cannot be negative")

    # No claims: increase NCB.
    if claims_counted == 0:
        return get_next_ncb_slab(current_ncb)

    # NCB Protect preserves NCB for one claim only.
    if (
        ncb_protect
        and claims_counted <= NCB_PROTECT_MAX_CLAIMS
    ):
        return current_ncb

    # Any unprotected claim or excess claims reset NCB.
    return NCB_RESET_VALUE


# ==========================================================
# 3. DETERMINE WHETHER A CLAIM COUNTS FOR NCB
# ==========================================================

def claim_counts_for_ncb(
    claim_id: str,
    app_state: ApplicationState,
) -> bool:
    """
    Determine whether an assessed claim counts towards NCB.

    REJECT claims do not count.

    REPAIR, TOTAL_LOSS, THEFT_SETTLEMENT and
    BELOW_THRESHOLD claims count.

    Claims without an assessment result are not counted yet.
    """

    result = app_state.claim_results.get(claim_id)

    if result is None:
        return False

    decision = result.get("decision")

    if decision is None:
        return False

    return decision != "REJECT"


# ==========================================================
# 4. COUNT CLAIMS DURING THE POLICY PERIOD
# ==========================================================

def count_policy_year_claims(
    policy: Policy,
    app_state: ApplicationState,
) -> int:
    """
    Count assessed claims belonging to this policy
    during its current policy period.

    Rejected claims are excluded.
    BELOW_THRESHOLD claims are included.
    """

    claims_counted = 0

    for claim_id, claim in app_state.claims.items():

        # Only claims belonging to this policy.
        if claim.policy_id != policy.policy_id:
            continue

        incident_date = claim.incident_ts.date()

        # Check the current policy period.
        if not (
            policy.policy_start
            <= incident_date
            <= policy.policy_end
        ):
            continue

        if claim_counts_for_ncb(claim_id, app_state):
            claims_counted += 1

    return claims_counted


# ==========================================================
# 5. COUNT ZERO_DEP CLAIMS
# ==========================================================

def count_zero_dep_claims(
    policy: Policy,
    app_state: ApplicationState,
) -> int:
    """
    Count claims for which ZERO_DEP was actually applied
    during the current policy period.

    The claim engine must store zero_dep_applicable=True
    in the corresponding claim result.
    """

    count = 0

    for claim_id, claim in app_state.claims.items():

        if claim.policy_id != policy.policy_id:
            continue

        incident_date = claim.incident_ts.date()

        if not (
            policy.policy_start
            <= incident_date
            <= policy.policy_end
        ):
            continue

        result = app_state.claim_results.get(claim_id, {})

        if (
            claim_counts_for_ncb(claim_id, app_state)
            and result.get("zero_dep_applicable") is True
        ):
            count += 1

    return count


# ==========================================================
# 6. PROCESS POLICY RENEWAL
# ==========================================================

def process_ncb_renewal(
    app_state: ApplicationState,
    policy_id: str,
    renewal_date: date,
) -> dict:
    """
    Process NCB renewal for a policy.

    Steps:
        1. Retrieve the policy.
        2. Count eligible claims during the policy year.
        3. Check NCB Protect.
        4. Calculate the next NCB percentage.
        5. Update the policy's NCB.
        6. Record policy renewal history.

    The policy dates are not changed here.
    Policy-period updates are handled by the command processor.
    """

    if policy_id not in app_state.policies:
        raise ValueError(
            f"Unknown policy ID: {policy_id}"
        )

    policy = app_state.policies[policy_id]

    if renewal_date < policy.policy_start:
        raise ValueError(
            "Renewal date cannot be before policy start date"
        )

    if renewal_date < policy.policy_end:
        raise ValueError(
            "Renewal date cannot be before policy expiry date"
        )

    ncb_before = policy.ncb_pct

    # Count claims during the expiring policy period.
    claims_counted = count_policy_year_claims(
        policy,
        app_state,
    )

    # Check NCB Protect add-on.
    ncb_protect = "NCB_PROTECT" in policy.addons

    # Calculate new NCB.
    ncb_after = calculate_next_ncb(
        current_ncb=ncb_before,
        claims_counted=claims_counted,
        ncb_protect=ncb_protect,
    )

    # Count actual ZERO_DEP claims.
    zero_dep_claims_used = count_zero_dep_claims(
        policy,
        app_state,
    )

    # Update policy NCB.
    policy.ncb_pct = ncb_after

    # Record renewal history.
    history_record = {
        "policy_id": policy.policy_id,
        "policy_start": policy.policy_start,
        "policy_end": policy.policy_end,
        "claims_counted": claims_counted,
        "zero_dep_claims_used": zero_dep_claims_used,
        "ncb_before": ncb_before,
        "ncb_after": ncb_after,
        "renewed_on": renewal_date,
    }

    app_state.policy_history.append(history_record)

    return history_record

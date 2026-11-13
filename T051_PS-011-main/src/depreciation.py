
from datetime import date
from decimal import Decimal, ROUND_HALF_UP

from src.constants import (
    METAL_DEPRECIATION_RATES,
    METAL_DEPRECIATION_ABOVE_5_YEARS,
    STANDARD_PART_DEPRECIATION,
    GLASS_DEPRECIATION,
    PAINT_COST_FACTOR,
    MONEY_PRECISION,
)


# ==========================================================
# 1. MONEY ROUNDING
# ==========================================================

def round_money(amount: Decimal) -> Decimal:
    """Round monetary values to two decimal places."""

    return amount.quantize(
        MONEY_PRECISION,
        rounding=ROUND_HALF_UP,
    )


# ==========================================================
# 2. VEHICLE AGE CALCULATION
# ==========================================================

def calculate_vehicle_age_months(
    purchase_date: date,
    incident_date: date,
) -> int:
    """
    Calculate completed calendar months between
    vehicle purchase date and claim incident date.
    """

    if incident_date < purchase_date:
        raise ValueError(
            "Incident date cannot be before vehicle purchase date"
        )

    months = (
        (incident_date.year - purchase_date.year) * 12
        + incident_date.month
        - purchase_date.month
    )

    # If the purchase-day anniversary has not yet occurred,
    # subtract one completed month.
    if incident_date.day < purchase_date.day:
        months -= 1

    return months


# ==========================================================
# 3. METAL DEPRECIATION
# ==========================================================

def get_metal_depreciation_rate(
    vehicle_age_months: int,
) -> Decimal:
    """
    Return metal depreciation based on completed vehicle age.

    Below 6 months       : 0%
    6 to <12 months      : 5%
    12 to <24 months     : 10%
    24 to <36 months     : 15%
    36 to <48 months     : 25%
    48 to 60 months      : 35%
    Above 60 months      : 50%
    """

    if vehicle_age_months < 0:
        raise ValueError("Vehicle age cannot be negative")

    # More than five years.
    if vehicle_age_months > 60:
        return METAL_DEPRECIATION_ABOVE_5_YEARS

    applicable_rate = Decimal("0.00")

    # Find the highest applicable age threshold.
    for minimum_age, rate in sorted(
        METAL_DEPRECIATION_RATES.items()
    ):
        if vehicle_age_months >= minimum_age:
            applicable_rate = rate
        else:
            break

    return applicable_rate


# ==========================================================
# 4. DEPRECIATION RATE BY PART CATEGORY
# ==========================================================

def get_depreciation_rate(
    part_category: str,
    vehicle_age_months: int,
) -> Decimal:
    """
    Determine the standard depreciation rate
    according to the part category.
    """

    category = part_category.strip().upper()

    if category == "METAL":
        return get_metal_depreciation_rate(
            vehicle_age_months
        )

    if category in {"PLASTIC", "RUBBER", "NYLON"}:
        return STANDARD_PART_DEPRECIATION

    if category == "GLASS":
        return GLASS_DEPRECIATION

    if category == "PAINT":
        return get_metal_depreciation_rate(
            vehicle_age_months
        )

    if category == "CONSUMABLE":
        # Consumables are handled separately by settlement.
        return Decimal("0.00")

    raise ValueError(
        f"Unsupported part category: {category}"
    )


# ==========================================================
# 5. CALCULATE DEPRECIATION FOR AN INDIVIDUAL SURVEY LINE
# ==========================================================

def calculate_line_depreciation(
    part_category: str,
    part_cost: Decimal,
    vehicle_age_months: int,
    zero_dep_applicable: bool = False,
) -> tuple[Decimal, Decimal]:
    """
    Calculate effective depreciation percentage and amount.

    Returns:
        (depreciation_percentage, depreciation_amount)

    Paint:
        Metal depreciation rate is applied to 50% of paint cost.

    ZERO_DEP:
        Depreciation is waived when the claim engine confirms
        ZERO_DEP eligibility.

    Consumables:
        Their coverage is handled separately by settlement.
    """

    if part_cost < Decimal("0"):
        raise ValueError("Part cost cannot be negative")

    category = part_category.strip().upper()

    # Validate the category even when ZERO_DEP applies.
    standard_rate = get_depreciation_rate(
        category,
        vehicle_age_months,
    )

    # ZERO_DEP waives depreciation on eligible parts.
    if zero_dep_applicable:
        return Decimal("0.00"), Decimal("0.00")

    # Paint depreciation applies only to 50% of its cost.
    if category == "PAINT":
        effective_rate = (
            standard_rate * PAINT_COST_FACTOR
        )
    else:
        effective_rate = standard_rate

    depreciation_amount = round_money(
        part_cost * effective_rate
    )

    return effective_rate, depreciation_amount


# ==========================================================
# 6. CALCULATE PAYABLE PART COST AFTER DEPRECIATION
# ==========================================================

def calculate_part_payable(
    part_cost: Decimal,
    depreciation_amount: Decimal,
) -> Decimal:
    """
    Calculate the payable part amount after depreciation.
    """

    if part_cost < Decimal("0"):
        raise ValueError("Part cost cannot be negative")

    if depreciation_amount < Decimal("0"):
        raise ValueError(
            "Depreciation amount cannot be negative"
        )

    if depreciation_amount > part_cost:
        raise ValueError(
            "Depreciation cannot exceed part cost"
        )

    return round_money(
        part_cost - depreciation_amount
    )


# ==========================================================
# 7. COMPLETE PART DEPRECIATION CALCULATION
# ==========================================================

def calculate_part_depreciation_details(
    part_category: str,
    part_cost: Decimal,
    vehicle_age_months: int,
    zero_dep_applicable: bool = False,
) -> dict:
    """
    Return complete depreciation details for a survey line.

    This function is useful for generating claim_lines.csv.
    """

    depreciation_rate, depreciation_amount = (
        calculate_line_depreciation(
            part_category=part_category,
            part_cost=part_cost,
            vehicle_age_months=vehicle_age_months,
            zero_dep_applicable=zero_dep_applicable,
        )
    )

    payable_amount = calculate_part_payable(
        part_cost,
        depreciation_amount,
    )

    return {
        "part_category": part_category.strip().upper(),
        "part_cost": round_money(part_cost),
        "dep_pct": depreciation_rate,
        "dep_amount": depreciation_amount,
        "part_payable": payable_amount,
    }

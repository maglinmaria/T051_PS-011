
from decimal import Decimal


# ==========================================================
# 1. GENERAL INSURANCE CONSTANTS
# ==========================================================

GST_RATE = Decimal("0.18")

MINIMUM_SETTLEMENT_AMOUNT = Decimal("500.00")

MONEY_PRECISION = Decimal("0.01")


# ==========================================================
# 2. CLAIM INFORMATION
# ==========================================================

CLAIM_CAUSES = {
    "ACCIDENT",
    "THEFT",
    "FLOOD",
    "FIRE",
}

PART_CATEGORIES = {
    "METAL",
    "PLASTIC",
    "RUBBER",
    "NYLON",
    "GLASS",
    "PAINT",
    "CONSUMABLE",
}

HOLDER_TYPES = {
    "INDIVIDUAL",
    "CORPORATE",
}

LICENCE_STATUSES = {
    "VALID",
    "LEARNER",
    "EXPIRED",
    "NONE",
}

SALVAGE_OPTIONS = {
    "CUSTOMER_KEEPS",
    "INSURER_TAKES",
}


# ==========================================================
# 3. ADD-ON COVERS
# ==========================================================

ADDONS = {
    "ZERO_DEP",
    "ENGINE_PROTECT",
    "CONSUMABLES",
    "RTI",
    "NCB_PROTECT",
}


# ==========================================================
# 4. DEPRECIATION RULES
# ==========================================================

# Rubber, plastic and nylon parts: 50%
STANDARD_PART_DEPRECIATION = Decimal("0.50")

# Glass parts: 0%
GLASS_DEPRECIATION = Decimal("0.00")

# Consumables are handled separately by the settlement engine.
# Their treatment depends on the CONSUMABLES add-on.

# Metal depreciation based on completed vehicle age in months.
#
# 0 to less than 6 months       : 0%
# 6 to less than 12 months      : 5%
# 12 to less than 24 months     : 10%
# 24 to less than 36 months     : 15%
# 36 to less than 48 months     : 25%
# 48 to 60 months inclusive     : 35%
# More than 60 months           : 50%

METAL_DEPRECIATION_RATES = {
    0: Decimal("0.00"),
    6: Decimal("0.05"),
    12: Decimal("0.10"),
    24: Decimal("0.15"),
    36: Decimal("0.25"),
    48: Decimal("0.35"),
}

METAL_DEPRECIATION_ABOVE_5_YEARS = Decimal("0.50")

METAL_DEPRECIATION_MAX_AGE_MONTHS = 60

# Paint depreciation applies to only 50% of paint cost.
PAINT_COST_FACTOR = Decimal("0.50")


# ==========================================================
# 5. ZERO DEPRECIATION ADD-ON
# ==========================================================

# Maximum two ZERO_DEP claims per policy year.
ZERO_DEP_MAX_CLAIMS = 2

# ZERO_DEP is unavailable when vehicle age exceeds 5 years.
ZERO_DEP_MAX_VEHICLE_AGE_MONTHS = 60


# ==========================================================
# 6. COMPULSORY AND VOLUNTARY EXCESS
# ==========================================================

# Engine capacity up to and including 1500cc.
COMPULSORY_EXCESS_UP_TO_1500CC = Decimal("1000.00")

# Engine capacity greater than 1500cc.
COMPULSORY_EXCESS_ABOVE_1500CC = Decimal("2000.00")

# Voluntary excess is read from the policy dataset.
# Total excess = compulsory excess + voluntary excess.


# ==========================================================
# 7. CLAIM INTIMATION RULES
# ==========================================================

# No delay deduction for intimation within exactly 48 hours.
DELAY_DEDUCTION_AFTER_HOURS = 48

# Deduct 10% when intimation is more than 48 hours late.
DELAY_DEDUCTION_RATE = Decimal("0.10")

# Reject when intimation is more than 7 days after incident.
MAX_INTIMATION_DELAY_DAYS = 7


# ==========================================================
# 8. DRIVING LICENCE RULES
# ==========================================================

# Learner licence: maximum 50% of otherwise payable amount.
LEARNER_LICENCE_MAX_PAYABLE_RATE = Decimal("0.50")


# ==========================================================
# 9. TOTAL LOSS RULES
# ==========================================================

# Total loss when assessed repair cost is at least 75% of IDV.
TOTAL_LOSS_THRESHOLD = Decimal("0.75")

# Deduct 10% of IDV if the customer retains the wreck.
SALVAGE_DEDUCTION_RATE = Decimal("0.10")


# ==========================================================
# 10. THEFT SETTLEMENT RULES
# ==========================================================

# FIR must be filed within 24 hours of the theft incident.
THEFT_FIR_MAX_DELAY_HOURS = 24

# Theft settlement waiting period.
THEFT_WAITING_PERIOD_DAYS = 90


# ==========================================================
# 11. RETURN TO INVOICE (RTI) COVER
# ==========================================================

# RTI is unavailable when vehicle age exceeds 3 years.
RTI_MAX_VEHICLE_AGE_MONTHS = 36

# RTI applies during the first 12 months from vehicle purchase.
RTI_POLICY_PERIOD_MONTHS = 12


# ==========================================================
# 12. NO CLAIM BONUS (NCB)
# ==========================================================

# NCB progression:
# 0% -> 20% -> 25% -> 35% -> 45% -> 50%

NCB_SLABS = [
    Decimal("0"),
    Decimal("20"),
    Decimal("25"),
    Decimal("35"),
    Decimal("45"),
    Decimal("50"),
]

# NCB Protect permits one claim without resetting NCB.
NCB_PROTECT_MAX_CLAIMS = 1

# NCB resets to zero when the applicable claim limit is exceeded.
NCB_RESET_VALUE = Decimal("0")


# ==========================================================
# 13. CLAIM DECISIONS
# ==========================================================

CLAIM_DECISIONS = {
    "REPAIR",
    "TOTAL_LOSS",
    "THEFT_SETTLEMENT",
    "REJECT",
    "BELOW_THRESHOLD",
}


# ==========================================================
# 14. CLAIM PROCESSING STATUS
# ==========================================================

CLAIM_STATUS_PENDING = "PENDING"

CLAIM_STATUS_ASSESSED = "ASSESSED"

CLAIM_STATUS_SETTLED = "SETTLED"

CLAIM_STATUS_REJECTED = "REJECTED"

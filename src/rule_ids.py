
# ==========================================================
# MOTOR INSURANCE BUSINESS RULE IDENTIFIERS
# ==========================================================

BR_01 = "BR-01"  # Claim intimation and delay deduction

BR_02 = "BR-02"  # Driving licence validation and learner cap

BR_03 = "BR-03"  # Depreciation on vehicle parts

BR_04 = "BR-04"  # Zero depreciation add-on

BR_05 = "BR-05"  # Consumables and engine protection

BR_06 = "BR-06"  # Compulsory and voluntary excess

BR_07 = "BR-07"  # Total loss and salvage deduction

BR_08 = "BR-08"  # Return to Invoice (RTI)

BR_09 = "BR-09"  # Theft settlement and recovery

BR_10 = "BR-10"  # No Claim Bonus and NCB Protect

BR_11 = "BR-11"  # Labour charges and GST

BR_12 = "BR-12"  # Minimum settlement threshold


# ==========================================================
# RULE DESCRIPTIONS
# ==========================================================

RULE_DESCRIPTIONS = {
    BR_01: "Claim intimation deadline and late intimation deduction",
    BR_02: "Driving licence validation and learner licence cap",
    BR_03: "Vehicle part depreciation",
    BR_04: "Zero depreciation add-on eligibility",
    BR_05: "Consumables and engine protection coverage",
    BR_06: "Compulsory and voluntary excess",
    BR_07: "Total loss settlement and salvage deduction",
    BR_08: "Return to Invoice settlement",
    BR_09: "Theft settlement waiting period and vehicle recovery",
    BR_10: "No Claim Bonus and NCB Protect",
    BR_11: "Labour payment and GST calculation",
    BR_12: "Minimum settlement threshold",
}


# ==========================================================
# RULE ORDER
# ==========================================================

RULE_ORDER = [
    BR_01,
    BR_02,
    BR_03,
    BR_04,
    BR_05,
    BR_06,
    BR_07,
    BR_08,
    BR_09,
    BR_10,
    BR_11,
    BR_12,
]


# ==========================================================
# FORMAT RULE IDENTIFIERS
# ==========================================================

def format_rule_ids(rule_ids: set[str] | list[str]) -> str:
    """
    Return unique rule IDs in the required BR-01 to BR-12 order.
    """

    unknown_rules = set(rule_ids) - set(RULE_ORDER)

    if unknown_rules:
        raise ValueError(
            f"Unknown business rule IDs: {sorted(unknown_rules)}"
        )

    return ";".join(
        rule_id
        for rule_id in RULE_ORDER
        if rule_id in rule_ids
    )


# ==========================================================
# GET RULE DESCRIPTION
# ==========================================================

def get_rule_description(rule_id: str) -> str:
    """Return the description of a business rule."""

    if rule_id not in RULE_DESCRIPTIONS:
        raise ValueError(f"Unknown rule ID: {rule_id}")

    return RULE_DESCRIPTIONS[rule_id]


# ==========================================================
# GET ALL RULE DESCRIPTIONS
# ==========================================================

def get_all_rule_descriptions() -> dict[str, str]:
    """Return all business rule identifiers and descriptions."""

    return RULE_DESCRIPTIONS.copy()

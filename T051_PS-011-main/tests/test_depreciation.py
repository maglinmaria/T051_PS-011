
from decimal import Decimal


def test_exactly_six_months_metal_depreciation(project_run):
    lines = project_run["reports"]["claim_lines"]

    matching = [
        line for line in lines
        if line["claim_id"] == "CLM-014"
        and line["part_category"] == "METAL"
    ]

    assert matching

    for line in matching:
        assert Decimal(line["dep_pct"]) == Decimal("5")


def test_glass_depreciation_is_zero(project_run):
    lines = project_run["reports"]["claim_lines"]

    glass_lines = [
        line for line in lines
        if line["part_category"] == "GLASS"
    ]

    assert glass_lines

    for line in glass_lines:
        assert Decimal(line["dep_pct"]) == Decimal("0")


def test_zero_dep_first_claim(project_run):
    lines = project_run["reports"]["claim_lines"]

    matching = [
        line for line in lines
        if line["claim_id"] == "CLM-007"
    ]

    assert matching

    for line in matching:
        assert Decimal(line["dep_pct"]) == Decimal("0")

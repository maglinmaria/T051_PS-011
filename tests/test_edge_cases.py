
from decimal import Decimal


def test_duplicate_survey_line_removed(project_run):
    lines = project_run["reports"]["claim_lines"]

    line_ids = {line["line_id"] for line in lines}

    assert "SVL-0077" in line_ids
    assert "SVL-0114" not in line_ids


def test_duplicate_survey_line_recorded_as_error(project_run):
    errors = project_run["reports"]["errors"]

    matching = [
        error for error in errors
        if error["reference_id"] == "SVL-0114"
    ]

    assert len(matching) == 1


def test_unknown_claim_recorded_as_error(project_run):
    errors = project_run["reports"]["errors"]

    matching = [
        error for error in errors
        if error["reference_id"] == "CLM-099"
    ]

    assert len(matching) == 1


def test_third_zero_dep_claim_uses_normal_depreciation(project_run):
    lines = project_run["reports"]["claim_lines"]

    matching = [
        line for line in lines
        if line["claim_id"] == "CLM-016"
        and line["part_category"] == "METAL"
    ]

    assert matching

    assert any(
        Decimal(line["dep_pct"]) > Decimal("0")
        for line in matching
    )

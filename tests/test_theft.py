
def get_claim(project_run, claim_id):
    return next(
        row for row in project_run["reports"]["claim_sheet"]
        if row["claim_id"] == claim_id
    )


def test_theft_claim_settlement(project_run):
    claim = get_claim(project_run, "CLM-004")

    assert claim["decision"] == "THEFT_SETTLEMENT"


def test_premature_theft_command_does_not_prevent_later_settlement(project_run):
    claim = get_claim(project_run, "CLM-008")

    assert claim["decision"] == "THEFT_SETTLEMENT"


def test_late_fir_theft_claim_rejected(project_run):
    claim = get_claim(project_run, "CLM-018")

    assert claim["decision"] == "REJECT"
    assert "BR-01" in claim["rule_ids"]

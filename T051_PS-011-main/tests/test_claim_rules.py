
def get_claim(project_run, claim_id):
    return next(
        row for row in project_run["reports"]["claim_sheet"]
        if row["claim_id"] == claim_id
    )


def test_learner_licence_claim(project_run):
    assert get_claim(project_run, "CLM-001")["decision"] == "REPAIR"


def test_expired_licence_rejected(project_run):
    assert get_claim(project_run, "CLM-006")["decision"] == "REJECT"


def test_total_loss_at_exact_75_percent(project_run):
    assert get_claim(project_run, "CLM-005")["decision"] == "TOTAL_LOSS"


def test_intimation_after_seven_days_rejected(project_run):
    assert get_claim(project_run, "CLM-015")["decision"] == "REJECT"


def test_late_theft_fir_rejected(project_run):
    assert get_claim(project_run, "CLM-018")["decision"] == "REJECT"


def test_below_threshold_claim(project_run):
    assert get_claim(project_run, "CLM-003")["decision"] == "BELOW_THRESHOLD"

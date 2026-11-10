
def test_policy_count(project_run):
    assert len(project_run["state"].policies) == 10


def test_claim_count(project_run):
    assert len(project_run["state"].claims) == 18


def test_survey_line_count(project_run):
    total = sum(
        len(lines)
        for lines in project_run["state"].survey_lines.values()
    )
    assert total == 113


def test_claim_line_report_count(project_run):
    assert len(project_run["reports"]["claim_lines"]) == 113


def test_claim_sheet_report_count(project_run):
    assert len(project_run["reports"]["claim_sheet"]) == 18


def test_policy_history_report_count(project_run):
    assert len(project_run["reports"]["policy_history"]) == 10


def test_error_report_count(project_run):
    assert len(project_run["reports"]["errors"]) == 2

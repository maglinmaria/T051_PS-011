
def get_policy(project_run, policy_id):
    return next(
        row for row in project_run["reports"]["policy_history"]
        if row["policy_id"] == policy_id
    )


def test_no_claim_policy_gets_ncb_increase(project_run):
    policy = get_policy(project_run, "POL-010")

    assert policy["claims_counted"] == "0"
    assert policy["ncb_before"] == "25"
    assert policy["ncb_after"] == "35"


def test_all_policy_histories_generated(project_run):
    assert len(project_run["reports"]["policy_history"]) == 10

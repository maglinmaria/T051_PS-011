
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


def _build_theft_processor(tmp_path, *, licence_status="LEARNER", intimation_hours=72):
    from datetime import date, datetime, timedelta
    from decimal import Decimal

    from src.command_processor import CommandProcessor
    from src.models import Claim, Policy

    processor = CommandProcessor(tmp_path)
    incident = datetime(2026, 1, 1, 8, 0, 0)
    policy = Policy(
        policy_id="POL-T",
        holder_name="Test Holder",
        holder_type="INDIVIDUAL",
        vehicle_reg_no="KA-01-AA-0001",
        make_model="Test Vehicle",
        engine_cc=1200,
        vehicle_purchase_date=date(2025, 1, 1),
        invoice_value=Decimal("120000.00"),
        idv=Decimal("100000.00"),
        policy_start=date(2026, 1, 1),
        policy_end=date(2026, 12, 31),
        addons=set(),
        ncb_pct=Decimal("0"),
        voluntary_excess=Decimal("0.00"),
    )
    claim = Claim(
        claim_id="CLM-T",
        policy_id="POL-T",
        cause="THEFT",
        incident_ts=incident,
        intimation_ts=incident + timedelta(hours=intimation_hours),
        fir_ts=incident + timedelta(hours=24),
        driver_licence_status=licence_status,
        licence_expiry_date=date(2027, 1, 1) if licence_status == "VALID" else None,
        salvage_option="INSURER_TAKES",
        incident_city="Bengaluru",
    )
    processor.app_state.policies[policy.policy_id] = policy
    processor.app_state.claims[claim.claim_id] = claim
    return processor


def test_theft_settlement_applies_delay_deduction_and_learner_cap(tmp_path):
    from datetime import date
    from decimal import Decimal

    processor = _build_theft_processor(tmp_path)
    processor.settle_theft("CLM-T", date(2026, 4, 2), 1)

    result = processor.app_state.claim_results["CLM-T"]
    assert result["decision"] == "THEFT_SETTLEMENT"
    assert result["delay_deduction"] == Decimal("9900.00")
    assert result["learner_cap_deduction"] == Decimal("44550.00")
    assert result["payable"] == Decimal("44550.00")
    assert "BR-01" in result["rule_ids"]
    assert "BR-02" in result["rule_ids"]


def test_theft_settlement_rejects_invalid_driving_licence(tmp_path):
    from datetime import date

    processor = _build_theft_processor(
        tmp_path, licence_status="EXPIRED", intimation_hours=24
    )
    processor.settle_theft("CLM-T", date(2026, 4, 2), 1)

    result = processor.app_state.claim_results["CLM-T"]
    assert result["decision"] == "REJECT"
    assert result["payable"] == 0
    assert result["rule_ids"] == "BR-02"

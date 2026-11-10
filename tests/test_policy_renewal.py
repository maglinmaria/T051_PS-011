from datetime import date, datetime
from decimal import Decimal

from src.command_processor import CommandProcessor
from src.models import Claim, Policy
from src.ncb import count_policy_year_claims


def make_policy() -> Policy:
    return Policy(
        policy_id="POL-TEST",
        holder_name="Test Holder",
        holder_type="INDIVIDUAL",
        vehicle_reg_no="KA-01-AA-0001",
        make_model="Test Vehicle",
        engine_cc=1200,
        vehicle_purchase_date=date(2024, 1, 1),
        invoice_value=Decimal("800000.00"),
        idv=Decimal("700000.00"),
        policy_start=date(2026, 3, 20),
        policy_end=date(2027, 3, 19),
        addons=set(),
        ncb_pct=Decimal("25"),
        voluntary_excess=Decimal("0.00"),
    )


def make_claim() -> Claim:
    return Claim(
        claim_id="CLM-TEST",
        policy_id="POL-TEST",
        cause="ACCIDENT",
        incident_ts=datetime(2026, 10, 1, 10, 0, 0),
        intimation_ts=datetime(2026, 10, 1, 11, 0, 0),
        fir_ts=None,
        driver_licence_status="VALID",
        licence_expiry_date=None,
        salvage_option="INSURER_TAKES",
        incident_city="Bengaluru",
    )


def test_renewal_advances_policy_period_and_preserves_old_period(tmp_path):
    processor = CommandProcessor(tmp_path)
    policy = make_policy()
    processor.app_state.policies[policy.policy_id] = policy

    processor.renew_policy(
        policy_id="POL-TEST",
        renewal_date=date(2027, 3, 20),
        line_number=1,
    )

    assert policy.policy_start == date(2027, 3, 20)
    assert policy.policy_end == date(2028, 3, 19)

    assert len(processor.app_state.policy_history) == 1
    history = processor.app_state.policy_history[0]

    # History must retain the policy period used for NCB calculation.
    assert history["policy_start"] == date(2026, 3, 20)
    assert history["policy_end"] == date(2027, 3, 19)
    assert history["renewed_on"] == date(2027, 3, 20)


def test_renewal_recomputes_ncb_using_claims_in_expiring_year(tmp_path):
    processor = CommandProcessor(tmp_path)
    policy = make_policy()
    processor.app_state.policies[policy.policy_id] = policy

    claim = make_claim()
    processor.app_state.claims[claim.claim_id] = claim
    processor.app_state.claim_results[claim.claim_id] = {
        "decision": "REPAIR"
    }

    processor.renew_policy(
        policy_id="POL-TEST",
        renewal_date=date(2027, 3, 20),
        line_number=1,
    )

    history = processor.app_state.policy_history[0]

    assert history["claims_counted"] == 1
    assert history["ncb_before"] == Decimal("25")
    assert history["ncb_after"] == Decimal("0")
    assert policy.ncb_pct == Decimal("0")


def test_previous_year_claim_is_not_counted_in_renewed_period(tmp_path):
    processor = CommandProcessor(tmp_path)
    policy = make_policy()
    processor.app_state.policies[policy.policy_id] = policy

    claim = make_claim()
    processor.app_state.claims[claim.claim_id] = claim
    processor.app_state.claim_results[claim.claim_id] = {
        "decision": "REPAIR"
    }

    processor.renew_policy(
        policy_id="POL-TEST",
        renewal_date=date(2027, 3, 20),
        line_number=1,
    )

    # The old claim remains in the data, but its incident date belongs
    # to the expired policy year, so it must not count in the new year.
    assert count_policy_year_claims(
        policy,
        processor.app_state,
    ) == 0

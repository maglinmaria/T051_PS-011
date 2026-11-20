from datetime import date, datetime
from decimal import Decimal

from src.constants import MINIMUM_SETTLEMENT_AMOUNT
from src.depreciation import get_depreciation_rate
from src.models import Claim, Policy, SurveyLine
from src.ncb import calculate_next_ncb
from src.settlement import calculate_compulsory_excess, calculate_repair_settlement


def _policy(*, holder_type="CORPORATE", engine_cc=1200, addons=None, excess="0.00"):
    return Policy(
        policy_id="POL-TEST",
        holder_name="Test Holder",
        holder_type=holder_type,
        vehicle_reg_no="KA-01-AA-0001",
        make_model="Test Vehicle",
        engine_cc=engine_cc,
        vehicle_purchase_date=date(2023, 1, 1),
        invoice_value=Decimal("120000.00"),
        idv=Decimal("100000.00"),
        policy_start=date(2026, 1, 1),
        policy_end=date(2026, 12, 31),
        addons=set(addons or []),
        ncb_pct=Decimal("20"),
        voluntary_excess=Decimal(excess),
    )


def _claim(*, cause="ACCIDENT", licence="VALID"):
    return Claim(
        claim_id="CLM-TEST",
        policy_id="POL-TEST",
        cause=cause,
        incident_ts=datetime(2026, 6, 1, 10, 0, 0),
        intimation_ts=datetime(2026, 6, 1, 10, 0, 0),
        fir_ts=None,
        driver_licence_status=licence,
        licence_expiry_date=date(2027, 1, 1) if licence == "VALID" else None,
        salvage_option="INSURER_TAKES",
        incident_city="Bengaluru",
    )


def test_depreciation_rates_cover_all_metal_age_bands():
    expected = {
        5: Decimal("0.00"),
        6: Decimal("0.05"),
        12: Decimal("0.10"),
        24: Decimal("0.15"),
        36: Decimal("0.25"),
        48: Decimal("0.35"),
        61: Decimal("0.50"),
    }
    for age_months, rate in expected.items():
        assert get_depreciation_rate("METAL", age_months) == rate


def test_compulsory_excess_boundary_at_1500cc():
    assert calculate_compulsory_excess(1500) == Decimal("1000.00")
    assert calculate_compulsory_excess(1501) == Decimal("2000.00")


def test_ncb_protect_only_preserves_one_claim():
    assert calculate_next_ncb(Decimal("50"), 1, True) == Decimal("50")
    assert calculate_next_ncb(Decimal("50"), 2, True) == Decimal("0")


def test_repair_settlement_applies_individual_gst_and_corporate_zero():
    claim = _claim()
    line = SurveyLine("SVL-T", claim.claim_id, "Glass", "GLASS", False,
                      Decimal("2000.00"), Decimal("500.00"))
    individual = calculate_repair_settlement(
        _policy(holder_type="INDIVIDUAL"), claim, [line], 41
    )
    corporate = calculate_repair_settlement(
        _policy(holder_type="CORPORATE"), claim, [line], 41
    )
    assert individual["gst"] == Decimal("450.00")
    assert corporate["gst"] == Decimal("0.00")
    assert corporate["labour_payable"] == Decimal("500.00")


def test_exact_500_rupees_is_not_below_threshold():
    claim = _claim()
    line = SurveyLine("SVL-T", claim.claim_id, "Glass", "GLASS", False,
                      Decimal("1500.00"), Decimal("0.00"))
    result = calculate_repair_settlement(
        _policy(holder_type="CORPORATE"), claim, [line], 41
    )
    assert result["payable"] == MINIMUM_SETTLEMENT_AMOUNT
    assert result["decision"] == "REPAIR"


def test_sample_total_loss_salvage_and_rti_amounts(project_run):
    sheets = {row["claim_id"]: row for row in project_run["reports"]["claim_sheet"]}
    total_loss = sheets["CLM-005"]
    theft_rti = sheets["CLM-008"]
    assert total_loss["decision"] == "TOTAL_LOSS"
    assert Decimal(total_loss["salvage_deduction"]) == Decimal("157500.00")
    assert Decimal(total_loss["payable"]) == Decimal("1415500.00")
    assert theft_rti["settlement_basis"] == "INVOICE"
    assert Decimal(theft_rti["payable"]) == Decimal("1239000.00")


def test_sample_consumables_and_flood_engine_lines_are_not_paid(project_run):
    results = project_run["state"].claim_results
    clm009 = results["CLM-009"]["line_results"]
    clm010 = results["CLM-010"]["line_results"]
    uncovered = [line for line in clm009 if line["line_id"] in {"SVL-0052", "SVL-0053", "SVL-0054"}]
    consumables = [line for line in clm010 if line["line_id"] in {"SVL-0060", "SVL-0061"}]
    assert uncovered and consumables
    assert all(line["line_status"] == "REJECTED" for line in uncovered + consumables)
    assert all(line["part_payable"] == 0 and line["labour_payable"] == 0 for line in uncovered + consumables)


def test_sample_below_threshold_claim_is_counted_for_ncb(project_run):
    history = {row["policy_id"]: row for row in project_run["reports"]["policy_history"]}
    assert history["POL-004"]["claims_counted"] == "1"
    assert Decimal("499.99") < Decimal("500.00")


def test_exactly_48_hours_has_no_intimation_deduction():
    from datetime import timedelta
    from src.settlement import calculate_delay_deduction

    claim = _claim()
    claim.intimation_ts = claim.incident_ts + timedelta(hours=48)
    assert calculate_delay_deduction(Decimal("10000.00"), claim) == Decimal("0.00")


def test_paint_depreciation_uses_half_paint_cost():
    from src.depreciation import calculate_line_depreciation

    percentage, amount = calculate_line_depreciation(
        "PAINT", Decimal("1000.00"), 48
    )
    assert percentage == Decimal("0.175")
    assert amount == Decimal("175.00")

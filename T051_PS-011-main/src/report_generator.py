
from __future__ import annotations

import csv
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path


# =============================================================
# CSV OUTPUT STRUCTURES
# =============================================================

CLAIM_LINE_COLUMNS = [
    "claim_id",
    "line_id",
    "part_category",
    "part_cost",
    "dep_pct",
    "dep_amount",
    "part_payable",
    "labour_payable",
    "line_status",
]

CLAIM_SHEET_COLUMNS = [
    "claim_id",
    "policy_id",
    "decision",
    "assessed_repair_cost",
    "parts_after_dep",
    "labour_payable",
    "gst",
    "excess",
    "delay_deduction",
    "learner_cap_deduction",
    "salvage_deduction",
    "settlement_basis",
    "payable",
    "rule_ids",
]

POLICY_HISTORY_COLUMNS = [
    "policy_id",
    "policy_start",
    "policy_end",
    "claims_counted",
    "zero_dep_claims_used",
    "ncb_before",
    "ncb_after",
    "renewed_on",
]

ERROR_COLUMNS = [
    "source",
    "line_or_row",
    "reference_id",
    "reason",
]


# =============================================================
# GENERAL HELPERS
# =============================================================

def get_value(data, *names, default=None):
    """Read a value from a dictionary or an object's attributes."""

    for name in names:
        if isinstance(data, dict) and name in data:
            return data[name]

        if hasattr(data, name):
            return getattr(data, name)

    return default


def decimal_value(value, default="0.00") -> Decimal:
    """Convert a value safely into Decimal."""

    if value is None or value == "":
        return Decimal(default)

    if isinstance(value, Decimal):
        return value

    return Decimal(str(value))


def money(value) -> str:
    """Format money to two decimal places."""

    amount = decimal_value(value)

    return str(
        amount.quantize(
            Decimal("0.01"),
            rounding=ROUND_HALF_UP,
        )
    )


def percentage(value) -> str:
    """Format depreciation as a percentage, not a fraction."""

    amount = decimal_value(value)

    # Internal calculation rates are normally fractions:
    # 0.05 means 5%.
    if Decimal("0") <= amount <= Decimal("1"):
        amount *= Decimal("100")

    return str(
        amount.quantize(
            Decimal("0.01"),
            rounding=ROUND_HALF_UP,
        )
    )


def date_text(value) -> str:
    """Convert date/datetime objects to ISO date strings."""

    if value is None:
        return ""

    if hasattr(value, "date") and not isinstance(value, type(None)):
        # datetime has a date() method; date does not need conversion.
        if value.__class__.__name__ == "datetime":
            return value.date().isoformat()

    if hasattr(value, "isoformat"):
        return value.isoformat()

    return str(value)


def normalize_rule_ids(value) -> str:
    """Return rule IDs as semicolon-separated values."""

    if value is None:
        return ""

    if isinstance(value, str):
        return value

    return ";".join(str(item) for item in value)


def write_csv(path: Path, columns: list[str], rows: list[dict]) -> None:
    """Write a CSV file with a fixed header and column order."""

    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open(
        "w",
        newline="",
        encoding="utf-8-sig",
    ) as file:

        writer = csv.DictWriter(
            file,
            fieldnames=columns,
            extrasaction="ignore",
        )

        writer.writeheader()

        for row in rows:
            writer.writerow(row)


# =============================================================
# CLAIM LINE REPORT
# =============================================================

def get_line_result_map(result: dict) -> dict:
    """Index calculated survey-line results by line ID."""

    line_results = get_value(
        result,
        "line_results",
        "lines",
        default=[],
    )

    if isinstance(line_results, dict):
        return line_results

    indexed = {}

    for line_result in line_results or []:
        line_id = get_value(
            line_result,
            "line_id",
            "id",
        )

        if line_id:
            indexed[line_id] = line_result

    return indexed


def build_claim_line_rows(app_state) -> list[dict]:
    """Create one output row for each survey line of an assessed claim."""

    rows = []

    for claim_id in sorted(app_state.claim_results):

        result = app_state.claim_results[claim_id]

        decision = get_value(
            result,
            "decision",
            default="REJECT",
        )

        line_result_map = get_line_result_map(result)

        survey_lines = app_state.survey_lines.get(claim_id, [])

        for survey_line in sorted(
            survey_lines,
            key=lambda item: get_value(item, "line_id", default=""),
        ):

            line_id = get_value(
                survey_line,
                "line_id",
                default="",
            )

            line_result = line_result_map.get(line_id, {})

            part_cost = get_value(
                line_result,
                "part_cost",
                default=get_value(survey_line, "part_cost"),
            )

            dep_rate = get_value(
                line_result,
                "dep_pct",
                "depreciation_rate",
                "dep_rate",
                default=Decimal("0"),
            )

            dep_amount = get_value(
                line_result,
                "dep_amount",
                "depreciation_amount",
                default=Decimal("0"),
            )

            part_payable = get_value(
                line_result,
                "part_payable",
                "parts_payable",
                default=Decimal("0"),
            )

            labour_payable = get_value(
                line_result,
                "labour_payable",
                default=Decimal("0"),
            )

            line_status = get_value(
                line_result,
                "line_status",
                "status",
                default=None,
            )

            if line_status is None:
                if decision == "REJECT":
                    line_status = "REJECTED"
                else:
                    line_status = "PAID"

            line_status = str(line_status).upper()

            # Normalize internal status names to the required output values.
            if line_status in {
                "COVERED",
                "APPROVED",
                "ACCEPTED",
            }:
                line_status = "PAID"

            if line_status not in {"PAID", "REJECTED"}:
                line_status = (
                    "PAID"
                    if decimal_value(part_payable) > 0
                    or decimal_value(labour_payable) > 0
                    else "REJECTED"
                )

            rows.append({
                "claim_id": claim_id,
                "line_id": line_id,
                "part_category": get_value(
                    survey_line,
                    "part_category",
                    default="",
                ),
                "part_cost": money(part_cost),
                "dep_pct": percentage(dep_rate),
                "dep_amount": money(dep_amount),
                "part_payable": money(part_payable),
                "labour_payable": money(labour_payable),
                "line_status": line_status,
            })

    return rows


# =============================================================
# CLAIM COMPUTATION SHEET
# =============================================================

def build_claim_sheet_row(claim_id: str, result: dict) -> dict:

    return {
        "claim_id": claim_id,
        "policy_id": get_value(result, "policy_id", default=""),
        "decision": get_value(result, "decision", default=""),
        "assessed_repair_cost": money(
            get_value(
                result,
                "assessed_repair_cost",
                default=0,
            )
        ),
        "parts_after_dep": money(
            get_value(
                result,
                "parts_after_dep",
                "parts_after_depreciation",
                default=0,
            )
        ),
        "labour_payable": money(
            get_value(result, "labour_payable", default=0)
        ),
        "gst": money(
            get_value(result, "gst", default=0)
        ),
        "excess": money(
            get_value(result, "excess", default=0)
        ),
        "delay_deduction": money(
            get_value(result, "delay_deduction", default=0)
        ),
        "learner_cap_deduction": money(
            get_value(
                result,
                "learner_cap_deduction",
                default=0,
            )
        ),
        "salvage_deduction": money(
            get_value(result, "salvage_deduction", default=0)
        ),
        "settlement_basis": get_value(
            result,
            "settlement_basis",
            default="PARTS",
        ),
        "payable": money(
            get_value(result, "payable", default=0)
        ),
        "rule_ids": normalize_rule_ids(
            get_value(result, "rule_ids", default="")
        ),
    }


def build_claim_sheet_rows(app_state, command_log: list) -> list[dict]:
    """Create claim sheets only for PRINT_CLAIM_SHEET commands."""

    rows = []

    for command, reference_id, _line_number in command_log:

        if command != "PRINT_CLAIM_SHEET":
            continue

        result = app_state.claim_results.get(reference_id)

        if result is None:
            continue

        rows.append(
            build_claim_sheet_row(reference_id, result)
        )

    return rows


# =============================================================
# POLICY HISTORY REPORT
# =============================================================

def build_policy_history_rows(app_state, command_log: list) -> list[dict]:
    """Create one history row for each requested policy."""

    rows = []

    for command, policy_id, _line_number in command_log:

        if command != "PRINT_POLICY_HISTORY":
            continue

        policy = app_state.policies.get(policy_id)

        if policy is None:
            continue

        history_entries = [
            entry
            for entry in app_state.policy_history
            if get_value(entry, "policy_id") == policy_id
        ]

        if history_entries:
            history = history_entries[-1]

            row = {
                "policy_id": policy_id,
                "policy_start": date_text(
                    get_value(
                        history,
                        "policy_start",
                        default=policy.policy_start,
                    )
                ),
                "policy_end": date_text(
                    get_value(
                        history,
                        "policy_end",
                        default=policy.policy_end,
                    )
                ),
                "claims_counted": get_value(
                    history,
                    "claims_counted",
                    default=0,
                ),
                "zero_dep_claims_used": get_value(
                    history,
                    "zero_dep_claims_used",
                    default=0,
                ),
                "ncb_before": str(
                    get_value(
                        history,
                        "ncb_before",
                        default=policy.ncb_pct,
                    )
                ),
                "ncb_after": str(
                    get_value(
                        history,
                        "ncb_after",
                        default=policy.ncb_pct,
                    )
                ),
                "renewed_on": date_text(
                    get_value(history, "renewed_on", default="")
                ),
            }

        else:
            row = {
                "policy_id": policy_id,
                "policy_start": date_text(policy.policy_start),
                "policy_end": date_text(policy.policy_end),
                "claims_counted": 0,
                "zero_dep_claims_used": 0,
                "ncb_before": str(policy.ncb_pct),
                "ncb_after": str(policy.ncb_pct),
                "renewed_on": "",
            }

        rows.append(row)

    return rows


# =============================================================
# ERROR REPORT
# =============================================================

def build_error_rows(app_state) -> list[dict]:

    rows = []

    for error in app_state.errors:

        rows.append({
            "source": get_value(error, "source", default=""),
            "line_or_row": get_value(
                error,
                "line_or_row",
                default="",
            ),
            "reference_id": get_value(
                error,
                "reference_id",
                default="",
            ),
            "reason": get_value(
                error,
                "reason",
                default="",
            ),
        })

    return rows


# =============================================================
# MAIN REPORT GENERATOR
# =============================================================

def generate_reports(
    app_state,
    command_log: list,
    output_dir: str | Path,
) -> dict:
    """
    Generate all four required CSV reports.

    Returns a dictionary containing the generated file paths.
    """

    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    claim_line_rows = build_claim_line_rows(app_state)

    claim_sheet_rows = build_claim_sheet_rows(
        app_state,
        command_log,
    )

    policy_history_rows = build_policy_history_rows(
        app_state,
        command_log,
    )

    error_rows = build_error_rows(app_state)

    files = {
        "claim_lines": output_path / "claim_lines.csv",
        "claim_sheet": output_path / "claim_sheet.csv",
        "policy_history": output_path / "policy_history.csv",
        "errors": output_path / "errors.csv",
    }

    write_csv(
        files["claim_lines"],
        CLAIM_LINE_COLUMNS,
        claim_line_rows,
    )

    write_csv(
        files["claim_sheet"],
        CLAIM_SHEET_COLUMNS,
        claim_sheet_rows,
    )

    write_csv(
        files["policy_history"],
        POLICY_HISTORY_COLUMNS,
        policy_history_rows,
    )

    write_csv(
        files["errors"],
        ERROR_COLUMNS,
        error_rows,
    )

    print("\n========================================")
    print(" REPORT GENERATION COMPLETED")
    print("========================================")

    for report_name, report_path in files.items():
        print(f"{report_name}: {report_path}")

    print("\nRows generated:")
    print(f"Claim lines: {len(claim_line_rows)}")
    print(f"Claim sheets: {len(claim_sheet_rows)}")
    print(f"Policy histories: {len(policy_history_rows)}")
    print(f"Errors: {len(error_rows)}")

    return files

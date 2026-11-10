
import csv
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

from src.models import Policy, Claim, SurveyLine
from src.state import ApplicationState


# --------------------------------------------------
# CONVERSION FUNCTIONS
# --------------------------------------------------

def parse_date(value: str) -> date:
    """Convert YYYY-MM-DD text into a date object."""
    return date.fromisoformat(value.strip())


def parse_datetime(value: str) -> datetime:
    """Convert timestamp text into a datetime object."""
    return datetime.strptime(value.strip(), "%Y-%m-%d %H:%M:%S")


def parse_optional_date(value: str) -> date | None:
    """Convert a date or return None if the field is empty."""
    if not value or not value.strip():
        return None
    return parse_date(value)


def parse_optional_datetime(value: str) -> datetime | None:
    """Convert a timestamp or return None if the field is empty."""
    if not value or not value.strip():
        return None
    return parse_datetime(value)


def parse_decimal(value: str) -> Decimal:
    """Convert a numeric string into Decimal."""
    return Decimal(value.strip())


def parse_boolean(value: str) -> bool:
    """Convert CSV boolean text into a Python boolean."""
    normalized = value.strip().lower()

    if normalized == "true":
        return True
    if normalized == "false":
        return False

    raise ValueError(f"Invalid boolean value: {value}")


def parse_addons(value: str) -> set[str]:
    """Convert semicolon-separated add-ons into a set."""
    if not value or value.strip().upper() == "NONE":
        return set()

    return {
        addon.strip().upper()
        for addon in value.split(";")
        if addon.strip()
    }


# --------------------------------------------------
# ERROR HANDLING
# --------------------------------------------------

def record_error(
    app_state: ApplicationState,
    source: str,
    row_number: int,
    reference_id: str,
    reason: str,
) -> None:
    """Record a data loading error without stopping execution."""

    app_state.add_error({
        "source": source,
        "line_or_row": row_number,
        "reference_id": reference_id,
        "reason": reason,
    })


# --------------------------------------------------
# LOAD POLICIES
# --------------------------------------------------

def load_policies(
    file_path: str | Path,
    app_state: ApplicationState,
) -> None:
    """Read policies.csv and store valid policies."""

    with open(file_path, "r", newline="", encoding="utf-8-sig") as file:
        reader = csv.DictReader(file)

        for row_number, row in enumerate(reader, start=2):
            policy_id = (row.get("policy_id") or "").strip()

            try:
                if not policy_id:
                    raise ValueError("Missing policy_id")

                if policy_id in app_state.policies:
                    raise ValueError(f"Duplicate policy ID: {policy_id}")

                policy = Policy(
                    policy_id=policy_id,
                    holder_name=row["holder_name"].strip(),
                    holder_type=row["holder_type"].strip().upper(),
                    vehicle_reg_no=row["vehicle_reg_no"].strip(),
                    make_model=row["make_model"].strip(),
                    engine_cc=int(row["engine_cc"]),
                    vehicle_purchase_date=parse_date(
                        row["vehicle_purchase_date"]
                    ),
                    invoice_value=parse_decimal(row["invoice_value"]),
                    idv=parse_decimal(row["idv"]),
                    policy_start=parse_date(row["policy_start"]),
                    policy_end=parse_date(row["policy_end"]),
                    addons=parse_addons(row["addons"]),
                    ncb_pct=parse_decimal(row["ncb_pct"]),
                    voluntary_excess=parse_decimal(
                        row["voluntary_excess"]
                    ),
                )

                app_state.add_policy(policy)

            except (ValueError, KeyError, TypeError) as error:
                record_error(
                    app_state,
                    "policies.csv",
                    row_number,
                    policy_id,
                    str(error),
                )


# --------------------------------------------------
# LOAD CLAIMS
# --------------------------------------------------

def load_claims(
    file_path: str | Path,
    app_state: ApplicationState,
) -> None:
    """Read claims.csv and store valid claims."""

    with open(file_path, "r", newline="", encoding="utf-8-sig") as file:
        reader = csv.DictReader(file)

        for row_number, row in enumerate(reader, start=2):
            claim_id = (row.get("claim_id") or "").strip()

            try:
                if not claim_id:
                    raise ValueError("Missing claim_id")

                if claim_id in app_state.claims:
                    raise ValueError(f"Duplicate claim ID: {claim_id}")

                claim = Claim(
                    claim_id=claim_id,
                    policy_id=row["policy_id"].strip(),
                    cause=row["cause"].strip().upper(),
                    incident_ts=parse_datetime(row["incident_ts"]),
                    intimation_ts=parse_datetime(row["intimation_ts"]),
                    fir_ts=parse_optional_datetime(row["fir_ts"]),
                    driver_licence_status=(
                        row["driver_licence_status"].strip().upper()
                    ),
                    licence_expiry_date=parse_optional_date(
                        row["licence_expiry_date"]
                    ),
                    salvage_option=row["salvage_option"].strip().upper(),
                    incident_city=row["incident_city"].strip(),
                )

                app_state.add_claim(claim)

            except (ValueError, KeyError, TypeError) as error:
                record_error(
                    app_state,
                    "claims.csv",
                    row_number,
                    claim_id,
                    str(error),
                )


# --------------------------------------------------
# LOAD SURVEY LINES
# --------------------------------------------------

def load_survey_lines(
    file_path: str | Path,
    app_state: ApplicationState,
) -> None:
    """Read survey_lines.csv and group lines by claim ID."""

    with open(file_path, "r", newline="", encoding="utf-8-sig") as file:
        reader = csv.DictReader(file)

        for row_number, row in enumerate(reader, start=2):
            line_id = (row.get("line_id") or "").strip()

            try:
                if not line_id:
                    raise ValueError("Missing line_id")

                line = SurveyLine(
                    line_id=line_id,
                    claim_id=row["claim_id"].strip(),
                    part_name=row["part_name"].strip(),
                    part_category=row["part_category"].strip().upper(),
                    engine_part=parse_boolean(row["engine_part"]),
                    part_cost=parse_decimal(row["part_cost"]),
                    labour_cost=parse_decimal(row["labour_cost"]),
                )

                app_state.add_survey_line(line)

            except (ValueError, KeyError, TypeError) as error:
                record_error(
                    app_state,
                    "survey_lines.csv",
                    row_number,
                    line_id,
                    str(error),
                )


# --------------------------------------------------
# LOAD COMPLETE DATASET
# --------------------------------------------------

def load_all_data(
    data_directory: str | Path,
    app_state: ApplicationState,
) -> None:
    """Load all three CSV datasets into application state."""

    data_directory = Path(data_directory)

    load_policies(data_directory / "policies.csv", app_state)
    load_claims(data_directory / "claims.csv", app_state)
    load_survey_lines(data_directory / "survey_lines.csv", app_state)

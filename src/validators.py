
from decimal import Decimal

from src.constants import (
    CLAIM_CAUSES,
    PART_CATEGORIES,
    HOLDER_TYPES,
    ADDONS,
    NCB_SLABS,
)
from src.state import ApplicationState


def record_validation_error(
    app_state: ApplicationState,
    source: str,
    reference_id: str,
    reason: str,
    line_or_row: str | int = "",
) -> None:
    """Record a validation error without stopping execution."""
    app_state.add_error({
        "source": source,
        "line_or_row": str(line_or_row),
        "reference_id": reference_id,
        "reason": reason,
    })


def validate_policies(app_state: ApplicationState) -> None:
    """Validate all loaded insurance policies."""

    for policy_id, policy in app_state.policies.items():

        if policy.holder_type not in HOLDER_TYPES:
            record_validation_error(
                app_state, "policies.csv", policy_id,
                "Invalid holder type"
            )

        if policy.engine_cc <= 0:
            record_validation_error(
                app_state, "policies.csv", policy_id,
                "Engine capacity must be positive"
            )

        if policy.invoice_value <= Decimal("0"):
            record_validation_error(
                app_state, "policies.csv", policy_id,
                "Invoice value must be positive"
            )

        if policy.idv <= Decimal("0"):
            record_validation_error(
                app_state, "policies.csv", policy_id,
                "IDV must be positive"
            )

        if policy.voluntary_excess < Decimal("0"):
            record_validation_error(
                app_state, "policies.csv", policy_id,
                "Voluntary excess cannot be negative"
            )

        if policy.policy_start > policy.policy_end:
            record_validation_error(
                app_state, "policies.csv", policy_id,
                "Policy start date is after policy end date"
            )

        if policy.vehicle_purchase_date > policy.policy_start:
            record_validation_error(
                app_state, "policies.csv", policy_id,
                "Vehicle purchase date is after policy start date"
            )

        if policy.ncb_pct not in NCB_SLABS:
            record_validation_error(
                app_state, "policies.csv", policy_id,
                "Invalid NCB percentage"
            )

        invalid_addons = policy.addons - ADDONS

        if invalid_addons:
            record_validation_error(
                app_state, "policies.csv", policy_id,
                f"Invalid add-ons: {sorted(invalid_addons)}"
            )


def validate_claims(app_state: ApplicationState) -> None:
    """Validate claims and their associated policy references."""

    valid_licence_statuses = {
        "VALID", "LEARNER", "EXPIRED", "NONE"
    }

    valid_salvage_options = {
        "CUSTOMER_KEEPS", "INSURER_TAKES"
    }

    for claim_id, claim in app_state.claims.items():

        if claim.policy_id not in app_state.policies:
            record_validation_error(
                app_state, "claims.csv", claim_id,
                f"Unknown policy ID: {claim.policy_id}"
            )

        if claim.cause not in CLAIM_CAUSES:
            record_validation_error(
                app_state, "claims.csv", claim_id,
                f"Invalid claim cause: {claim.cause}"
            )

        if claim.driver_licence_status not in valid_licence_statuses:
            record_validation_error(
                app_state, "claims.csv", claim_id,
                "Invalid driving licence status"
            )

        if claim.salvage_option not in valid_salvage_options:
            record_validation_error(
                app_state, "claims.csv", claim_id,
                "Invalid salvage option"
            )

        if claim.intimation_ts < claim.incident_ts:
            record_validation_error(
                app_state, "claims.csv", claim_id,
                "Intimation cannot be before incident"
            )

        if claim.fir_ts is not None and claim.cause != "THEFT":
            record_validation_error(
                app_state, "claims.csv", claim_id,
                "FIR timestamp supplied for a non-theft claim"
            )

        if claim.cause == "THEFT" and claim.fir_ts is None:
            record_validation_error(
                app_state, "claims.csv", claim_id,
                "Missing FIR timestamp for theft claim"
            )


def get_survey_row_number(line_id: str) -> str:
    """Extract the numeric CSV row identifier from a survey line ID."""
    try:
        return str(int(line_id.split("-")[-1]))
    except (ValueError, IndexError):
        return ""


def validate_survey_lines(app_state: ApplicationState) -> None:
    """
    Validate survey lines.

    Repeated part names are allowed.

    A duplicate is rejected only when all survey details
    match an earlier entry, excluding the unique line ID.
    """

    for claim_id, lines in list(app_state.survey_lines.items()):

        seen_lines = set()
        valid_lines = []

        for line in lines:

            row_number = get_survey_row_number(line.line_id)

            if claim_id not in app_state.claims:
                record_validation_error(
                    app_state,
                    "survey_lines.csv",
                    line.line_id,
                    f"Unknown claim ID: {claim_id}",
                    row_number,
                )
                continue

            if line.part_category not in PART_CATEGORIES:
                record_validation_error(
                    app_state,
                    "survey_lines.csv",
                    line.line_id,
                    f"Invalid part category: {line.part_category}",
                    row_number,
                )
                continue

            if line.part_cost < Decimal("0"):
                record_validation_error(
                    app_state,
                    "survey_lines.csv",
                    line.line_id,
                    "Part cost cannot be negative",
                    row_number,
                )
                continue

            if line.labour_cost < Decimal("0"):
                record_validation_error(
                    app_state,
                    "survey_lines.csv",
                    line.line_id,
                    "Labour cost cannot be negative",
                    row_number,
                )
                continue

            # Compare every field except the unique line ID.
            # This allows legitimate repeated part names.
            duplicate_key = (
                line.claim_id,
                line.part_name.strip().casefold(),
                line.part_category,
                line.engine_part,
                line.part_cost,
                line.labour_cost,
            )

            if duplicate_key in seen_lines:
                record_validation_error(
                    app_state,
                    "survey_lines.csv",
                    line.line_id,
                    f"Duplicate survey entry: {line.part_name}",
                    row_number,
                )
                continue

            seen_lines.add(duplicate_key)
            valid_lines.append(line)

        # Retain valid survey lines only.
        app_state.survey_lines[claim_id] = valid_lines


def validate_all(app_state: ApplicationState) -> None:
    """Execute all validation functions."""

    validate_policies(app_state)
    validate_claims(app_state)
    validate_survey_lines(app_state)

from __future__ import annotations

import inspect
from dataclasses import replace
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

from src.state import ApplicationState
from src.validators import validate_all
from src.data_loader import (
    load_policies,
    load_claims,
    load_survey_lines,
)
from src.claim_engine import assess_claim
from src.ncb import process_ncb_renewal
from src.rule_ids import format_rule_ids


THEFT_WAITING_DAYS = 90
THEFT_FIR_LIMIT_HOURS = 24


class CommandProcessor:
    """Read and execute commands in their original file order."""

    def __init__(self, project_root: str | Path):
        self.project_root = Path(project_root).resolve()
        self.data_dir = self.project_root / "data"
        self.output_dir = self.project_root / "output"

        self.output_dir.mkdir(parents=True, exist_ok=True)

        self.app_state = ApplicationState()
        self.command_log = []

    @staticmethod
    def parse_date(value: str) -> date:
        return date.fromisoformat(value.strip())

    def add_error(
        self,
        source: str,
        line_or_row: str | int,
        reference_id: str,
        reason: str,
    ) -> None:
        self.app_state.add_error({
            "source": source,
            "line_or_row": str(line_or_row),
            "reference_id": reference_id,
            "reason": str(reason),
        })

    def resolve_data_file(self, filename: str) -> Path:
        supplied_path = Path(filename)

        if supplied_path.is_absolute():
            return supplied_path

        project_path = self.project_root / supplied_path
        data_path = self.data_dir / supplied_path

        if project_path.exists():
            return project_path

        return data_path

    # ---------------------------------------------------------
    # DATA LOADING
    # ---------------------------------------------------------

    def call_loader(self, loader, file_path: Path) -> None:
        """Call a CSV loader using its actual parameter names."""

        signature = inspect.signature(loader)
        arguments = {}

        for parameter in signature.parameters.values():
            name = parameter.name.lower()

            if name in {
                "state", "app_state", "application_state"
            }:
                arguments[parameter.name] = self.app_state

            elif name in {
                "path", "file_path", "csv_path",
                "filename", "file"
            }:
                arguments[parameter.name] = file_path

            elif parameter.default is inspect.Parameter.empty:
                raise TypeError(
                    f"Unsupported loader parameter: {parameter.name}"
                )

        loader(**arguments)

    def load_file(
        self,
        command: str,
        filename: str,
        line_number: int,
    ) -> None:

        file_path = self.resolve_data_file(filename)

        if not file_path.exists():
            self.add_error(
                "commands.txt",
                line_number,
                filename,
                f"File not found: {file_path}",
            )
            return

        loader_map = {
            "LOAD_POLICIES": load_policies,
            "LOAD_CLAIMS": load_claims,
            "LOAD_SURVEY": load_survey_lines,
        }

        try:
            self.call_loader(loader_map[command], file_path)

            # Validate all loaded data after survey lines are loaded.
            if command == "LOAD_SURVEY":
                validate_all(self.app_state)

            print(f"Successfully loaded {file_path.name}")
        except Exception as exc:
            self.add_error(
                "commands.txt",
                line_number,
                filename,
                f"{command} failed: {exc}",
            )

    # ---------------------------------------------------------
    # THEFT VALIDATION AND REJECTION
    # ---------------------------------------------------------

    @staticmethod
    def theft_fir_is_late(claim) -> bool:
        """Return True when the theft FIR was filed after 24 hours."""

        if claim.fir_ts is None:
            return True

        delay = claim.fir_ts - claim.incident_ts

        return delay > timedelta(hours=THEFT_FIR_LIMIT_HOURS)

    def create_theft_rejection(self, claim_id: str, reason: str) -> None:
        """Create a proper rejected claim result for a late theft FIR."""

        claim = self.app_state.claims[claim_id]

        result = {
            "claim_id": claim_id,
            "policy_id": claim.policy_id,
            "decision": "REJECT",
            "assessed_repair_cost": Decimal("0.00"),
            "parts_after_dep": Decimal("0.00"),
            "labour_payable": Decimal("0.00"),
            "gst": Decimal("0.00"),
            "excess": Decimal("0.00"),
            "delay_deduction": Decimal("0.00"),
            "learner_cap_deduction": Decimal("0.00"),
            "salvage_deduction": Decimal("0.00"),
            "settlement_basis": "PARTS",
            "payable": Decimal("0.00"),
            "rule_ids": format_rule_ids({"BR-01"}),
            "line_results": [],
            "zero_dep_applicable": False,
            "rejection_reason": reason,
        }

        self.app_state.claim_results[claim_id] = result

    # ---------------------------------------------------------
    # CLAIM ASSESSMENT
    # ---------------------------------------------------------

    def assess(
        self,
        claim_id: str,
        assessment_date: date,
        line_number: int,
    ) -> None:

        claim = self.app_state.claims.get(claim_id)

        if claim is None:
            self.add_error(
                "commands.txt",
                line_number,
                claim_id,
                f"Unknown claim ID: {claim_id}",
            )
            return

        # Special handling for theft claims.
        if claim.cause == "THEFT":

            if self.theft_fir_is_late(claim):
                self.create_theft_rejection(
                    claim_id,
                    "Theft FIR filed more than 24 hours after incident.",
                )

                print(
                    f"Claim {claim_id} assessed: REJECT "
                    "(FIR filed after 24 hours)"
                )
                return

            self.add_error(
                "commands.txt",
                line_number,
                claim_id,
                "Valid THEFT claims must use theft processing commands.",
            )
            return

        try:
            result = assess_claim(
                self.app_state,
                claim_id,
                assessment_date,
            )

            if result is None:
                result = self.app_state.claim_results.get(claim_id)

            decision = (
                result.get("decision", "UNKNOWN")
                if result else "NO RESULT"
            )

            print(f"Claim {claim_id} assessed: {decision}")

        except Exception as exc:
            self.add_error(
                "commands.txt",
                line_number,
                claim_id,
                f"Assessment failed: {exc}",
            )

    # ---------------------------------------------------------
    # THEFT PROCESSING
    # ---------------------------------------------------------

    @staticmethod
    def get_theft_eligibility_date(claim) -> date:

        if claim.fir_ts is None:
            raise ValueError("FIR timestamp is missing.")

        return (
            claim.fir_ts.date()
            + timedelta(days=THEFT_WAITING_DAYS)
        )

    def process_theft_recovery(
        self,
        claim_id: str,
        recovery_date: date,
        line_number: int,
    ) -> None:

        claim = self.app_state.claims.get(claim_id)

        if claim is None:
            self.add_error(
                "commands.txt", line_number, claim_id,
                f"Unknown claim ID: {claim_id}",
            )
            return

        if claim.cause != "THEFT":
            self.add_error(
                "commands.txt", line_number, claim_id,
                "THEFT_RECOVERED requires a THEFT claim.",
            )
            return

        if self.theft_fir_is_late(claim):
            self.create_theft_rejection(
                claim_id,
                "Theft FIR filed more than 24 hours after incident.",
            )
            print(f"{claim_id}: REJECTED due to late FIR.")
            return

        try:
            eligibility_date = self.get_theft_eligibility_date(claim)

            self.app_state.record_theft_recovery(
                claim_id,
                recovery_date,
            )

            if recovery_date < eligibility_date:

                original_claim = claim

                self.app_state.claims[claim_id] = replace(
                    original_claim,
                    cause="ACCIDENT",
                )

                try:
                    result = assess_claim(
                        self.app_state,
                        claim_id,
                        recovery_date,
                    )
                finally:
                    self.app_state.claims[claim_id] = original_claim

                if result is None:
                    result = self.app_state.claim_results.get(claim_id)

                if result:
                    result["decision"] = "REPAIR"
                    result["settlement_basis"] = "PARTS"

                    existing_rules = result.get("rule_ids", [])

                    if isinstance(existing_rules, str):
                        existing_rules = [
                            item for item in existing_rules.split(";")
                            if item
                        ]

                    result["rule_ids"] = format_rule_ids(
                        set(existing_rules) | {"BR-09"}
                    )

                print(
                    f"{claim_id}: Vehicle recovered before day 90. "
                    "Repair assessment completed."
                )

            else:
                print(
                    f"{claim_id}: Vehicle recovered on or after "
                    "the 90-day eligibility date."
                )

        except Exception as exc:
            self.add_error(
                "commands.txt",
                line_number,
                claim_id,
                f"Theft recovery failed: {exc}",
            )

    def settle_theft(
        self,
        claim_id: str,
        settlement_date: date,
        line_number: int,
    ) -> None:

        claim = self.app_state.claims.get(claim_id)

        if claim is None:
            self.add_error(
                "commands.txt", line_number, claim_id,
                f"Unknown claim ID: {claim_id}",
            )
            return

        if claim.cause != "THEFT":
            self.add_error(
                "commands.txt", line_number, claim_id,
                "SETTLE_THEFT requires a THEFT claim.",
            )
            return

        if self.theft_fir_is_late(claim):
            self.create_theft_rejection(
                claim_id,
                "Theft FIR filed more than 24 hours after incident.",
            )
            print(f"{claim_id}: Theft claim rejected due to late FIR.")
            return

        try:
            eligibility_date = self.get_theft_eligibility_date(claim)

            recovery_date = (
                self.app_state.theft_recovered_dates.get(claim_id)
            )

            if (
                recovery_date is not None
                and recovery_date < eligibility_date
            ):
                print(
                    f"{claim_id}: Vehicle was recovered before day 90. "
                    "Theft settlement is not applicable."
                )
                return

            if settlement_date < eligibility_date:
                print(
                    f"{claim_id}: Settlement is premature. "
                    f"Eligible date: {eligibility_date}"
                )
                return

            from src.settlement import calculate_total_excess
            from src.depreciation import calculate_vehicle_age_months

            policy = self.app_state.policies[claim.policy_id]

            vehicle_age = calculate_vehicle_age_months(
                policy.vehicle_purchase_date,
                claim.incident_ts.date(),
            )

            first_year_end = self.add_calendar_months(
                policy.vehicle_purchase_date,
                12,
            )

            rti_eligible = (
                "RTI" in policy.addons
                and vehicle_age <= 36
                and claim.incident_ts.date() <= first_year_end
            )

            if rti_eligible:
                settlement_basis = "INVOICE"
                base_amount = policy.invoice_value
            else:
                settlement_basis = "IDV"
                base_amount = policy.idv

            excess = calculate_total_excess(policy)

            payable = max(
                Decimal("0.00"),
                base_amount - excess,
            )

            rule_ids = {"BR-06", "BR-09"}

            if rti_eligible:
                rule_ids.add("BR-08")

            result = {
                "claim_id": claim_id,
                "policy_id": claim.policy_id,
                "decision": "THEFT_SETTLEMENT",
                "assessed_repair_cost": Decimal("0.00"),
                "parts_after_dep": Decimal("0.00"),
                "labour_payable": Decimal("0.00"),
                "gst": Decimal("0.00"),
                "excess": excess,
                "delay_deduction": Decimal("0.00"),
                "learner_cap_deduction": Decimal("0.00"),
                "salvage_deduction": Decimal("0.00"),
                "settlement_basis": settlement_basis,
                "payable": payable,
                "rule_ids": format_rule_ids(rule_ids),
                "line_results": [],
                "zero_dep_applicable": False,
            }

            self.app_state.claim_results[claim_id] = result

            print(
                f"{claim_id}: Theft settlement completed. "
                f"Payable: Rs. {payable}"
            )

        except Exception as exc:
            self.add_error(
                "commands.txt",
                line_number,
                claim_id,
                f"Theft settlement failed: {exc}",
            )

    # ---------------------------------------------------------
    # DATE HELPER
    # ---------------------------------------------------------

    @staticmethod
    def add_calendar_months(original_date: date, months: int) -> date:

        import calendar

        month_index = original_date.month - 1 + months
        year = original_date.year + month_index // 12
        month = month_index % 12 + 1

        day = min(
            original_date.day,
            calendar.monthrange(year, month)[1],
        )

        return date(year, month, day)

    # ---------------------------------------------------------
    # POLICY RENEWAL
    # ---------------------------------------------------------

    def renew_policy(
        self,
        policy_id: str,
        renewal_date: date,
        line_number: int,
    ) -> None:
        """Renew a policy, record its expiring period, and advance its dates."""

        if policy_id not in self.app_state.policies:
            self.add_error(
                "commands.txt",
                line_number,
                policy_id,
                f"Unknown policy ID: {policy_id}",
            )
            return

        try:
            policy = self.app_state.policies[policy_id]

            # Calculate the next policy period before changing anything.
            new_policy_start = renewal_date
            new_policy_end = (
                self.add_calendar_months(new_policy_start, 12)
                - timedelta(days=1)
            )

            # Record NCB history using the OLD policy dates.
            process_ncb_renewal(
                self.app_state,
                policy_id,
                renewal_date,
            )

            # Advance the policy only after renewal processing succeeds.
            policy.policy_start = new_policy_start
            policy.policy_end = new_policy_end

            print(
                f"Policy renewed: {policy_id} | "
                f"New period: {policy.policy_start} to {policy.policy_end} | "
                f"NCB: {policy.ncb_pct}%"
            )

        except Exception as exc:
            self.add_error(
                "commands.txt",
                line_number,
                policy_id,
                f"Renewal failed: {exc}",
            )

    # ---------------------------------------------------------
    # COMMAND EXECUTION
    # ---------------------------------------------------------

    def execute_command(
        self,
        raw_line: str,
        line_number: int,
    ) -> None:

        parts = [
            part.strip()
            for part in raw_line.split("|")
        ]

        if not parts or not parts[0]:
            return

        command = parts[0].upper()
        arguments = parts[1:]

        try:

            if command in {
                "LOAD_POLICIES",
                "LOAD_CLAIMS",
                "LOAD_SURVEY",
            }:

                if len(arguments) != 1:
                    raise ValueError(
                        f"{command} requires one filename."
                    )

                self.load_file(
                    command,
                    arguments[0],
                    line_number,
                )

            elif command == "ASSESS":

                if len(arguments) != 2:
                    raise ValueError(
                        "ASSESS requires claim_id and date."
                    )

                self.assess(
                    arguments[0],
                    self.parse_date(arguments[1]),
                    line_number,
                )

            elif command == "THEFT_RECOVERED":

                if len(arguments) != 2:
                    raise ValueError(
                        "THEFT_RECOVERED requires claim_id and date."
                    )

                self.process_theft_recovery(
                    arguments[0],
                    self.parse_date(arguments[1]),
                    line_number,
                )

            elif command == "SETTLE_THEFT":

                if len(arguments) != 2:
                    raise ValueError(
                        "SETTLE_THEFT requires claim_id and date."
                    )

                self.settle_theft(
                    arguments[0],
                    self.parse_date(arguments[1]),
                    line_number,
                )

            elif command == "RENEW":

                if len(arguments) != 2:
                    raise ValueError(
                        "RENEW requires policy_id and date."
                    )

                self.renew_policy(
                    arguments[0],
                    self.parse_date(arguments[1]),
                    line_number,
                )

            elif command in {
                "PRINT_CLAIM_SHEET",
                "PRINT_POLICY_HISTORY",
            }:

                if len(arguments) != 1:
                    raise ValueError(
                        f"{command} requires one ID."
                    )

                self.command_log.append(
                    (command, arguments[0], line_number)
                )

                print(
                    f"Queued report command: "
                    f"{command} {arguments[0]}"
                )

            else:
                self.add_error(
                    "commands.txt",
                    line_number,
                    command,
                    f"Unknown command: {command}",
                )

        except Exception as exc:
            self.add_error(
                "commands.txt",
                line_number,
                command,
                str(exc),
            )

    # ---------------------------------------------------------
    # COMMAND FILE PROCESSING
    # ---------------------------------------------------------

    def process_commands(
        self,
        command_file: str = "commands.txt",
    ) -> ApplicationState:

        command_path = self.resolve_data_file(command_file)

        if not command_path.exists():
            raise FileNotFoundError(
                f"Command file not found: {command_path}"
            )

        print("\n========================================")
        print(" MOTOR INSURANCE CLAIMS PROCESSOR")
        print("========================================")

        with command_path.open(
            "r",
            encoding="utf-8-sig",
        ) as file:

            for line_number, raw_line in enumerate(file, start=1):

                command_line = raw_line.strip()

                if not command_line or command_line.startswith("#"):
                    continue

                print(f"\n[{line_number}] {command_line}")

                self.execute_command(
                    command_line,
                    line_number,
                )

        print("\n========================================")
        print(" COMMAND PROCESSING COMPLETED")
        print("========================================")

        print(f"Policies loaded: {len(self.app_state.policies)}")
        print(f"Claims loaded: {len(self.app_state.claims)}")
        print(f"Survey groups loaded: {len(self.app_state.survey_lines)}")
        print(f"Errors recorded: {len(self.app_state.errors)}")
        print(f"Report commands queued: {len(self.command_log)}")

        return self.app_state

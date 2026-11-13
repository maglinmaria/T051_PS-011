
from dataclasses import dataclass, field

from src.models import Policy, Claim, SurveyLine


@dataclass
class ApplicationState:
    """Maintains all information while the application runs."""

    # Registered insurance policies
    policies: dict[str, Policy] = field(default_factory=dict)

    # Registered insurance claims
    claims: dict[str, Claim] = field(default_factory=dict)

    # Survey lines grouped by claim ID
    survey_lines: dict[str, list[SurveyLine]] = field(
        default_factory=dict
    )

    # Claim assessment results
    claim_results: dict[str, dict] = field(default_factory=dict)

    # Policy renewal history
    policy_history: list[dict] = field(default_factory=list)

    # Errors encountered during processing
    errors: list[dict] = field(default_factory=list)

    # Vehicle recovery dates, indexed by claim ID
    theft_recovered_dates: dict[str, object] = field(
        default_factory=dict
    )

    def add_policy(self, policy: Policy) -> None:
        """Add an insurance policy."""
        self.policies[policy.policy_id] = policy

    def add_claim(self, claim: Claim) -> None:
        """Add an insurance claim."""
        self.claims[claim.claim_id] = claim

    def add_survey_line(self, line: SurveyLine) -> None:
        """Add a survey line under its claim."""
        self.survey_lines.setdefault(
            line.claim_id, []
        ).append(line)

    def add_error(self, error: dict) -> None:
        """Record an application error."""
        self.errors.append(error)

    def record_theft_recovery(
        self,
        claim_id: str,
        recovery_date,
    ) -> None:
        """Record the date a stolen vehicle was recovered."""
        self.theft_recovered_dates[claim_id] = recovery_date


# Shared application state
state = ApplicationState()


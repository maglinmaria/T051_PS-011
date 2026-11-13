
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal


@dataclass
class Policy:
    """Stores motor insurance policy and vehicle information."""

    policy_id: str
    holder_name: str
    holder_type: str
    vehicle_reg_no: str
    make_model: str
    engine_cc: int
    vehicle_purchase_date: date
    invoice_value: Decimal
    idv: Decimal
    policy_start: date
    policy_end: date
    addons: set[str]
    ncb_pct: Decimal
    voluntary_excess: Decimal


@dataclass
class Claim:
    """Stores information about an insurance claim."""

    claim_id: str
    policy_id: str
    cause: str
    incident_ts: datetime
    intimation_ts: datetime
    fir_ts: datetime | None
    driver_licence_status: str
    licence_expiry_date: date | None
    salvage_option: str
    incident_city: str


@dataclass
class SurveyLine:
    """Stores individual vehicle repair and survey details."""

    line_id: str
    claim_id: str
    part_name: str
    part_category: str
    engine_part: bool
    part_cost: Decimal
    labour_cost: Decimal

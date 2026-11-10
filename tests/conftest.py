
import csv
from pathlib import Path

import pytest

from src.command_processor import CommandProcessor
from src.report_generator import generate_reports


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def read_csv(path):
    with path.open("r", encoding="utf-8-sig", newline="") as file:
        return list(csv.DictReader(file))


@pytest.fixture(scope="session")
def project_run(tmp_path_factory):
    processor = CommandProcessor(PROJECT_ROOT)
    app_state = processor.process_commands("commands.txt")

    output_dir = tmp_path_factory.mktemp("motor_insurance")

    generate_reports(
        app_state=app_state,
        command_log=processor.command_log,
        output_dir=output_dir,
    )

    reports = {
        "claim_lines": read_csv(output_dir / "claim_lines.csv"),
        "claim_sheet": read_csv(output_dir / "claim_sheet.csv"),
        "policy_history": read_csv(output_dir / "policy_history.csv"),
        "errors": read_csv(output_dir / "errors.csv"),
    }

    return {
        "state": app_state,
        "reports": reports,
        "output_dir": output_dir,
    }

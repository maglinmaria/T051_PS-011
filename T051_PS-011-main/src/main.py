from pathlib import Path
import sys

from src.command_processor import CommandProcessor
from src.report_generator import generate_reports


def main():
    project_root = Path(__file__).resolve().parent.parent

    print("\n" + "=" * 55)
    print("       MOTOR INSURANCE CLAIMS SETTLEMENT SYSTEM")
    print("                    TEAM T051")
    print("=" * 55)

    try:
        processor = CommandProcessor(project_root)

        app_state = processor.process_commands("commands.txt")

        generated_files = generate_reports(
            app_state=app_state,
            command_log=processor.command_log,
            output_dir=processor.output_dir,
        )

        print("\nEXECUTION SUMMARY")
        print("-" * 40)
        print(f"Policies loaded : {len(app_state.policies)}")
        print(f"Claims loaded   : {len(app_state.claims)}")
        print(f"Claims assessed : {len(app_state.claim_results)}")
        print(f"Errors recorded : {len(app_state.errors)}")

        print("\nGENERATED REPORTS")
        for name, path in generated_files.items():
            print(f"{name}: {path}")

        print("\nMOTOR INSURANCE PROCESS COMPLETED")
        return 0

    except Exception as error:
        print(f"\nPROJECT EXECUTION FAILED: {error}")
        return 1


if __name__ == "__main__":
    sys.exit(main())

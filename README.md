# PS-011 — Motor Insurance Claims Settlement System

**Team:** T051  
**Problem:** Motor Insurance Claims Settlement with IDV, Depreciation and NCB  
**Language:** Python 3.10+  
**Interface:** Command-file backend + local browser dashboard (Python standard library)

## 1. Project overview

This application processes motor-insurance policies, claims and surveyor assessment lines. It validates claim eligibility, calculates repair/total-loss/theft settlements, applies depreciation and add-on rules, updates No Claim Bonus (NCB) at renewal, and generates CSV reports.

The command-file backend is the original project interface and remains the source of truth. The browser dashboard is an additional, lightweight way to run the supplied sample workflow and inspect its reports.

## 2. Features

- Policy, claim and survey-line CSV loading and validation.
- Repair, total-loss and theft claim processing.
- Part-wise depreciation, ZERO_DEP, CONSUMABLES, ENGINE_PROTECT and RTI handling.
- Compulsory/voluntary excess, delayed-intimation deduction, learner-licence cap and GST.
- NCB renewal and NCB_PROTECT handling.
- Claim computation, line details, policy history and error reports.
- Local browser dashboard to run sample processing, inspect reports and download CSVs.

## 3. Project structure

```text
T051_PS-011-main/
├── web_app.py                # Local browser dashboard server
├── frontend/
│   └── index.html            # Dashboard page
├── data/                     # Supplied sample CSV files and command stream
├── docs/                     # Design, business rules, decision log and sample-data notes
├── output/                   # Generated CSV reports
├── src/                      # Claim engine and processing modules
├── tests/                    # pytest test suite
├── requirements.txt
└── README.md
```

## 4. Setup

Use Python 3.12 if available (Python 3.10+ is supported).

### Windows PowerShell

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

If PowerShell blocks activation, run the commands from Command Prompt or use:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

## 5. Run the backend

Run these commands from the project root (the folder containing `requirements.txt`):

```powershell
python -m pytest -q
python -m src.main
```

The sample command file is `data/commands.txt`. The engine reads the CSV files in `data/` and writes these reports to `output/`:

| Report | Description |
|---|---|
| `claim_sheet.csv` | Final decision and claim-level calculation summary |
| `claim_lines.csv` | Part-wise depreciation and payable amounts |
| `policy_history.csv` | Policy-year claim count and NCB renewal details |
| `errors.csv` | Invalid survey rows and command/data validation errors |

The sample dataset intentionally includes invalid/duplicate inputs. Therefore, entries in `errors.csv` can be expected validation results rather than application crashes. Check the error `reason` column.

## 6. Run the front end (optional local dashboard)

From the same project root, with the virtual environment activated:

```powershell
python web_app.py
```

Open `http://127.0.0.1:8000` in your browser. Select **Run sample processing** to execute the existing backend workflow. Use the tabs to inspect claim settlements, survey-line calculations, policy/NCB history and validation errors. CSV download links are provided in each report tab.

The dashboard uses only the Python standard library, runs locally on your computer, and does not replace or change the command-file backend. The backend can always be run independently using `python -m src.main`.

## 7. Testing

Run:

```powershell
python -m pytest -q
```

The current repository test suite contains 40 tests covering sample loading/report generation, key claim decisions, depreciation boundaries, ZERO_DEP usage, theft handling, NCB renewal and validation errors. The design document includes a rule-to-code/test traceability matrix and identifies cases that still need dedicated assertions.

## 8. Documentation

- `docs/design_document.md` — system design, architecture, workflows, flowcharts and traceability.
- `docs/business_rules.md` — implemented BR-01 to BR-12 definitions and calculation sequence.
- `docs/decision_log.md` — confirmed implementation facts, inferred rationale and unresolved interpretation.
- `docs/sample_data_README.md` — sample input schema and planted scenarios.
- `docs/test_results.txt` — recorded automated-test and dashboard smoke-test evidence.

The prepared design PDF is `docs/design_document.pdf`. The editable Markdown source is `docs/design_document.md`.

## 9. Demo outline (approximately 5 minutes)

1. Show the project structure and explain that the backend is command-file driven.
2. Run `python -m pytest -q` and show the passing test count.
3. Run `python -m src.main` (or click **Run sample processing** in the dashboard).
4. Open `claim_sheet.csv` and explain one repair claim, one total-loss claim and one rejected/below-threshold claim.
5. Open `claim_lines.csv` to show part-wise depreciation and labour treatment.
6. Open `policy_history.csv` to explain NCB renewal; briefly show `errors.csv` and explain the intentional duplicate/unknown-ID validation cases.

## 10. Team

Team T051 — PS-011, 10 SECONDS Capstone.

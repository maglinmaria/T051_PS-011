"""Local browser interface for the PS-011 claim settlement engine.

Uses only the Python standard library. The existing command-file backend is
still the source of truth for every insurance calculation.
"""
from __future__ import annotations

import csv
import json
import subprocess
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parent
OUTPUT = ROOT / "output"
FRONTEND = ROOT / "frontend" / "index.html"
REPORT_FILES = {
    "claim_sheet": "claim_sheet.csv",
    "claim_lines": "claim_lines.csv",
    "policy_history": "policy_history.csv",
    "errors": "errors.csv",
}


def read_report(report_key: str) -> list[dict[str, str]]:
    filename = REPORT_FILES[report_key]
    path = OUTPUT / filename
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as file:
        return list(csv.DictReader(file))


class DashboardHandler(BaseHTTPRequestHandler):
    server_version = "T051-PS011/1.0"

    def send_bytes(self, body: bytes, content_type: str, status: int = 200) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def send_json(self, payload: dict, status: int = 200) -> None:
        self.send_bytes(
            json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            "application/json; charset=utf-8",
            status,
        )

    def do_GET(self) -> None:  # noqa: N802 - stdlib handler API
        if self.path == "/" or self.path == "/index.html":
            self.send_bytes(FRONTEND.read_bytes(), "text/html; charset=utf-8")
            return

        if self.path == "/api/reports":
            reports = {key: read_report(key) for key in REPORT_FILES}
            self.send_json({"reports": reports})
            return

        if self.path.startswith("/api/download/"):
            key = unquote(self.path.rsplit("/", 1)[-1])
            if key not in REPORT_FILES:
                self.send_json({"error": "Unknown report"}, 404)
                return
            path = OUTPUT / REPORT_FILES[key]
            if not path.exists():
                self.send_json({"error": "Report not generated yet"}, 404)
                return
            self.send_bytes(path.read_bytes(), "text/csv; charset=utf-8")
            return

        self.send_json({"error": "Not found"}, 404)

    def do_POST(self) -> None:  # noqa: N802 - stdlib handler API
        if self.path != "/api/run":
            self.send_json({"error": "Not found"}, 404)
            return

        try:
            result = subprocess.run(
                [sys.executable, "-m", "src.main"],
                cwd=ROOT,
                capture_output=True,
                text=True,
                check=False,
            )
            self.send_json({
                "ok": result.returncode == 0,
                "output": result.stdout + ("\n" + result.stderr if result.stderr else ""),
                "reports": {key: read_report(key) for key in REPORT_FILES},
            }, 200 if result.returncode == 0 else 500)
        except Exception as exc:  # return an actionable browser error
            self.send_json({"ok": False, "error": str(exc)}, 500)

    def log_message(self, format: str, *args) -> None:
        # Keep the terminal output concise while retaining basic access logs.
        print(f"[dashboard] {self.address_string()} - {format % args}")


def main() -> None:
    host, port = "127.0.0.1", 8000
    server = ThreadingHTTPServer((host, port), DashboardHandler)
    print("PS-011 dashboard is running.")
    print(f"Open http://{host}:{port} in your browser.")
    print("Press Ctrl+C to stop the dashboard.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nDashboard stopped.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()

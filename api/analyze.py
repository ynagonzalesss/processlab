"""Vercel serverless endpoint for the ProcessLab Studio demo.

GET  /api/analyze?example=guest_onboarding  -> example process + report
POST /api/analyze  {process JSON}           -> report for an edited process

The real rules engine runs here. No LLM calls.
"""
import json
import sys
from http.server import BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from pydantic import ValidationError  # noqa: E402

from processlab.diagram import to_mermaid  # noqa: E402
from processlab.engine import analyze_process, load_config  # noqa: E402
from processlab.schema import Process  # noqa: E402

EXAMPLES = {p.stem: p for p in (ROOT / "examples").glob("*.json")}
CONFIG = load_config()


def run(raw: dict) -> dict:
    process = Process.model_validate(raw)
    report = analyze_process(process, CONFIG)
    return {
        "process": process.model_dump(mode="json"),
        "report": report.model_dump(mode="json"),
        "mermaid": to_mermaid(process, report),
    }


class handler(BaseHTTPRequestHandler):
    def _send(self, code: int, body: dict) -> None:
        data = json.dumps(body).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):  # noqa: N802
        name = parse_qs(urlparse(self.path).query).get("example", ["guest_onboarding"])[0]
        if name not in EXAMPLES:
            return self._send(404, {"error": f"Unknown example. Try: {', '.join(sorted(EXAMPLES))}"})
        try:
            self._send(200, {"examples": sorted(EXAMPLES), **run(json.loads(EXAMPLES[name].read_text()))})
        except Exception as e:  # pragma: no cover
            self._send(500, {"error": str(e)})

    def do_POST(self):  # noqa: N802
        try:
            length = int(self.headers.get("Content-Length") or 0)
            if length > 200_000:
                return self._send(413, {"error": "Process too large"})
            raw = json.loads(self.rfile.read(length) or b"{}")
            self._send(200, run(raw))
        except ValidationError as e:
            self._send(422, {"error": "Invalid process", "details": json.loads(e.json())})
        except Exception as e:
            self._send(400, {"error": str(e)})

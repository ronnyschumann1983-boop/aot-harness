"""
aot_harness/integrations/n8n_webhook.py
n8n-compatible HTTP server — exposes the Harness as a webhook endpoint.
Run:  python -m aot_harness.integrations.n8n_webhook
Then point your n8n HTTP Request node to http://localhost:8765/run
"""
from __future__ import annotations
import json
from http.server import HTTPServer, BaseHTTPRequestHandler
from ..core.orchestrator import Orchestrator


_orchestrator: Orchestrator | None = None


def init(orchestrator: Orchestrator) -> None:
    global _orchestrator
    _orchestrator = orchestrator


class HarnessHandler(BaseHTTPRequestHandler):

    def do_POST(self):
        if self.path != "/run":
            self._respond(404, {"error": "Use POST /run"})
            return

        length = int(self.headers.get("Content-Length", 0))
        body   = self.rfile.read(length)

        try:
            data = json.loads(body)
            goal = data.get("goal", "")
        except Exception:
            self._respond(400, {"error": "Invalid JSON. Expected: {'goal': '...'}"}); return

        if not goal:
            self._respond(400, {"error": "'goal' field is required"}); return

        if _orchestrator is None:
            self._respond(503, {"error": "Orchestrator not initialized. Call init() first."}); return

        result = _orchestrator.run(goal)
        self._respond(200, result)

    def do_GET(self):
        self._respond(200, {"status": "aot-harness running", "endpoint": "POST /run"})

    def _respond(self, code: int, data: dict) -> None:
        body = json.dumps(data, indent=2, default=str).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", len(body))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        pass  # suppress default access logs


def serve(host: str = "0.0.0.0", port: int = 8765) -> None:
    print(f"🚀 aot-harness webhook running at http://{host}:{port}/run")
    HTTPServer((host, port), HarnessHandler).serve_forever()

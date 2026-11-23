"""Small web server: serves the React app and a JSON API (Python standard library only).

GET  /api/status                 mode, model, audit check
GET  /api/cases                  work queue
GET  /api/cases/<id>             one case
POST /api/run                    run all cases through the 3 agents
POST /api/cases/<id>/decision    record a nurse/physician decision (rules enforced here too)
GET  /api/audit?case=<id>        audit trail
"""
import json
import mimetypes
import threading
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from . import safety_checks as safety
from .settings import DECISIONS_FILE, FRONTEND_DIST, MODEL, RESULTS_DIR, read_json, use_claude, write_json
from .workflow import load_results, process_all_cases

RUN_LOCK = threading.Lock()
DECISIONS = {"approve": "Approve", "pend": "Pend: send letter to provider", "escalate": "Send to physician", "deny": "Deny"}


def check_decision(case: dict, body: dict) -> str | None:
    """Server-side rules. Returns an error message, or None if the decision is allowed."""
    role, decision = body.get("role"), body.get("decision")
    if role not in ("nurse", "physician"):
        return "Choose a reviewer role."
    if decision not in DECISIONS:
        return "Choose a decision."
    if not str(body.get("rationale", "")).strip():
        return "Write a short rationale before submitting."
    if decision == "deny":
        if role != "physician":
            return "Only a physician reviewer can deny a request."
        allowed = {c["id"] for c in case["criteria"] if c["status"] != "MET"}
        basis = set(body.get("deny_basis") or [])
        if not basis or not basis <= allowed:
            return "A denial must name the specific policy rules that are not met."
    if decision == "approve" and case["route"] == "SECURITY_REVIEW" and not body.get("security_cleared"):
        return "Confirm the removed text was reviewed by security before approving."
    return None


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):  # keep the terminal quiet
        pass

    def send_json(self, data, status=200):
        body = json.dumps(data, default=str).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def read_body(self) -> dict:
        length = int(self.headers.get("Content-Length") or 0)
        return json.loads(self.rfile.read(length) or b"{}")

    # ------------------------------------------------------------ GET
    def do_GET(self):
        url = urlparse(self.path)
        parts = [p for p in url.path.split("/") if p]
        if parts[:1] == ["api"]:
            return self.api_get(parts[1:], parse_qs(url.query))
        return self.serve_file(url.path)

    def api_get(self, parts, query):
        decisions = read_json(DECISIONS_FILE, {})
        if parts == ["status"]:
            return self.send_json({"mode": "Claude" if use_claude() else "Offline rules", "model": MODEL,
                                   "cases_processed": len(load_results()), "audit_intact": safety.audit_chain_intact()})
        if parts == ["cases"]:
            keep = ("case_id", "route", "route_label", "headline", "service", "member", "deadline", "counts", "test_scenario")
            return self.send_json([{**{k: c[k] for k in keep}, "decision": decisions.get(c["case_id"])}
                                   for c in load_results()])
        if len(parts) == 2 and parts[0] == "cases":
            case = read_json(RESULTS_DIR / f"{parts[1]}.json")
            if not case:
                return self.send_json({"error": "Case not found. Run the AI pipeline first."}, 404)
            return self.send_json({**case, "decision": decisions.get(parts[1])})
        if parts == ["audit"]:
            case_id = query.get("case", [None])[0]
            return self.send_json({"intact": safety.audit_chain_intact(), "events": safety.read_audit(case_id)})
        return self.send_json({"error": "Unknown endpoint"}, 404)

    # ------------------------------------------------------------ POST
    def do_POST(self):
        parts = [p for p in urlparse(self.path).path.split("/") if p]
        if parts == ["api", "run"]:
            if not RUN_LOCK.acquire(blocking=False):
                return self.send_json({"error": "The pipeline is already running."}, 409)
            try:
                safety.AUDIT_LOG.unlink(missing_ok=True)
                DECISIONS_FILE.unlink(missing_ok=True)
                cases = process_all_cases()
                return self.send_json({"processed": len(cases), "mode": "Claude" if use_claude() else "Offline rules"})
            finally:
                RUN_LOCK.release()
        if len(parts) == 4 and parts[:2] == ["api", "cases"] and parts[3] == "decision":
            case = read_json(RESULTS_DIR / f"{parts[2]}.json")
            if not case:
                return self.send_json({"error": "Case not found."}, 404)
            body = self.read_body()
            error = check_decision(case, body)
            if error:
                return self.send_json({"error": error}, 400)
            record = {"decision": DECISIONS[body["decision"]], "reviewer": f"{body['role']}:{body.get('reviewer_id', '')}",
                      "ai_route": case["route"], "ai_accurate": body.get("ai_accurate"),
                      "deny_basis": body.get("deny_basis") or [], "rationale": body["rationale"],
                      "time": datetime.now(timezone.utc).isoformat(timespec="seconds")}
            decisions = read_json(DECISIONS_FILE, {})
            decisions[parts[2]] = record
            write_json(DECISIONS_FILE, decisions)
            safety.audit(parts[2], "HUMAN_DECISION", record["reviewer"], record)
            return self.send_json(record)
        return self.send_json({"error": "Unknown endpoint"}, 404)

    # ------------------------------------------------------------ React app files
    def serve_file(self, path):
        target = (FRONTEND_DIST / path.lstrip("/")).resolve()
        if path in ("", "/") or not target.is_file() or FRONTEND_DIST.resolve() not in target.parents:
            target = FRONTEND_DIST / "index.html"
        if not target.exists():
            return self.send_json({"error": "frontend/dist is missing. Run: npm run build (in frontend/)"}, 500)
        data = target.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", mimetypes.guess_type(str(target))[0] or "application/octet-stream")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


def run_server(port: int = 8000) -> ThreadingHTTPServer:
    # 127.0.0.1 only: the app is reachable from this computer, not the network
    return ThreadingHTTPServer(("127.0.0.1", port), Handler)

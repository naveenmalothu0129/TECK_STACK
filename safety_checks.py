"""Safety and compliance controls shared by the three agents.

1. Prompt-injection filter  - remove instruction-like text before any AI reads the page
2. Privacy (PHI)            - mask identifiers for the AI, redact the audit log, check outbound letters
3. Citation check           - every fact must quote the source page word for word
4. Routing                  - plain code decides the route; there is no "deny" route
5. Deadline clock           - CMS-0057-F: 72 hours expedited / 7 days standard
6. Audit log                - append-only, hash-chained, no patient details
"""
import hashlib
import json
import re
import unicodedata
from datetime import datetime, timedelta, timezone

from .settings import AUDIT_LOG

# ------------------------------------------------------------ 1. prompt injection
HIDDEN_CHARS = re.compile("[​-‏‪-‮⁠-⁤﻿]")
INJECTION_PATTERNS = [
    r"\b(?:ignore|disregard|forget)\b[^.\n]{0,40}?\b(?:previous|prior|above|all)\b[^.\n]{0,20}?\binstructions?\b",
    r"\bauto(?:matically|-)?\s*approve\b",
    r"\b(?:mark|report)\s+(?:all\s+)?criteria\s+(?:as\s+)?met\b",
    r"\bset\s+(?:the\s+)?(?:decision|status)\s*(?:=|to)",
    r"^\s*(?:system|assistant)\s*:",
    r"\b(?:you are now|new instructions|developer mode)\b",
    r"\b(?:note|attention|message)\s+(?:to|for)\s+(?:the\s+)?(?:ai|automated|llm|model)\b",
]
INJECTION_RE = [re.compile(p, re.I | re.M) for p in INJECTION_PATTERNS]
REMOVED_MARKER = "[REMOVED BY SAFETY FILTER: suspected instruction to the AI]"


def sanitize(text: str) -> tuple[str, int, int]:
    """Strip hidden characters and replace injection lines with a marker.
    Returns (clean_text, hidden_char_count, removed_line_count)."""
    hidden = len(HIDDEN_CHARS.findall(text))
    text = unicodedata.normalize("NFKC", HIDDEN_CHARS.sub("", text))
    lines, removed = [], 0
    for line in text.splitlines():
        if any(p.search(line) for p in INJECTION_RE):
            lines.append(REMOVED_MARKER)
            removed += 1
        else:
            lines.append(line)
    return "\n".join(lines), hidden, removed


# ------------------------------------------------------------ 2. privacy
SSN = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")
PHONE = re.compile(r"\(?\b\d{3}\)?[-.\s]\d{3}[-.\s]\d{4}\b")
MEMBER_ID = re.compile(r"\bM\d{6}\b")


def mask_identifiers(text: str, member: dict | None) -> str:
    """Replace direct identifiers with tokens. Clinical dates are kept (needed for durations)."""
    if member:
        for part in member["name"].split():
            text = re.sub(rf"\b{re.escape(part)}\b", "[PATIENT]", text, flags=re.I)
        text = text.replace(member["dob"], "[DOB]")
    text = SSN.sub("[SSN]", text)
    text = PHONE.sub("[PHONE]", text)
    return MEMBER_ID.sub("[MEMBER ID]", text)


def extra_identifiers(text: str) -> list[str]:
    return [name for name, pattern in (("SSN", SSN), ("phone number", PHONE)) if pattern.search(text)]


def mask_id(member_id: str) -> str:
    return "*" * (len(member_id) - 4) + member_id[-4:]


def letter_privacy_check(letter: str, other_patient_names: list[str]) -> list[str]:
    """Outbound letters may only contain this member's minimum necessary data."""
    problems = [f"{name} in letter" for name, p in (("SSN", SSN), ("Phone number", PHONE)) if p.search(letter)]
    problems += ["Another patient's name in letter" for n in other_patient_names if n.lower() in letter.lower()]
    return problems


# ------------------------------------------------------------ 3. citation check
def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", unicodedata.normalize("NFKC", text or "")).strip().lower()


def verify_citation(fact: dict, spec: dict, page_text: str | None) -> str | None:
    """Return None if the citation is real, otherwise a plain reason it failed."""
    if page_text is None:
        return "the cited page does not exist"
    quote = _norm(fact.get("quote"))
    if len(quote) < 3 or quote not in _norm(page_text):
        return "the quote is not on the cited page"
    value = fact.get("value")
    if spec["type"] in ("number", "date", "string", "enum") and value is not None:
        options = [str(value), str(value).replace("_", " ")]
        if isinstance(value, float) and value.is_integer():
            options.append(str(int(value)))
        options += [k for k, v in spec.get("map", {}).items() if v == value]
        if not any(_norm(o) in quote for o in options):
            return "the value is not in the quote"
    return None


# ------------------------------------------------------------ 4. routing
ROUTES = {
    "FAST_TRACK": {"label": "Ready to approve",
                   "next_step": "Every policy rule is met with checked evidence. Review the checklist and confirm."},
    "PEND_FOR_INFO": {"label": "Missing information",
                      "next_step": "Send the drafted letter so the provider can supply the missing items."},
    "NURSE_REVIEW": {"label": "Needs nurse review",
                     "next_step": "Resolve the problems listed below before making a decision."},
    "MD_REVIEW": {"label": "Physician review needed",
                  "next_step": "One or more policy rules are not met. Only a physician reviewer can deny."},
    "SECURITY_REVIEW": {"label": "Security hold",
                        "next_step": "Security must clear the removed text before clinical review continues."},
    "INTAKE_EXCEPTION": {"label": "File can't be processed",
                         "next_step": "Ask the provider to resend the unreadable document."},
}


def decide_route(intake_ok: bool, flags: list, criteria: list, conflicts: list, missing: list) -> tuple[str, list]:
    """First match wins. There is no DENY route: denials are a physician's decision."""
    high = [f["message"] for f in flags if f["severity"] == "high"]
    medium = [f["message"] for f in flags if f["severity"] == "medium"]
    unmet = [f"{c['id']} not met: {c['title']}" for c in criteria if c["status"] == "UNMET"]
    unverified = [f"{c['id']}: evidence could not be checked" for c in criteria if c["status"] == "NEEDS_REVIEW"]

    if not intake_ok:
        route, reasons = "INTAKE_EXCEPTION", high
    elif any(f["code"] == "PROMPT_INJECTION" for f in flags):
        route, reasons = "SECURITY_REVIEW", ["Text trying to instruct the AI was found and removed"]
    elif unmet:
        route, reasons = "MD_REVIEW", unmet
    elif conflicts or high or unverified:
        route, reasons = "NURSE_REVIEW", [c["title"] for c in conflicts] + high + unverified
    elif missing:
        route, reasons = "PEND_FOR_INFO", [f"Missing: {m['item']}" for m in missing]
    elif medium:
        route, reasons = "NURSE_REVIEW", medium
    else:
        route, reasons = "FAST_TRACK", ["All policy rules met with checked citations and no safety problems"]
    assert route in ROUTES  # the pipeline can never produce anything else (e.g. DENY)
    return route, reasons


# ------------------------------------------------------------ 5. deadline clock
def deadline(received_at: str, urgency: str) -> dict:
    hours = 72 if urgency == "expedited" else 168
    due = datetime.fromisoformat(received_at) + timedelta(hours=hours)
    left = (due - datetime.now(timezone.utc)).total_seconds() / 3600
    status = "overdue" if left <= 0 else ("at risk" if left < hours * 0.25 else "on track")
    return {"urgency": urgency, "due_at": due.isoformat(timespec="minutes"), "hours_left": round(left, 1),
            "status": status, "rule": "CMS-0057-F: 72 hours expedited, 7 days standard"}


# ------------------------------------------------------------ 6. audit log
def _hash(entry: dict) -> str:
    body = {k: v for k, v in entry.items() if k != "hash"}
    return hashlib.sha256(json.dumps(body, sort_keys=True, default=str).encode()).hexdigest()


def read_audit(case_id: str | None = None) -> list:
    if not AUDIT_LOG.exists():
        return []
    events = [json.loads(l) for l in AUDIT_LOG.read_text(encoding="utf-8").splitlines() if l.strip()]
    return [e for e in events if case_id in (None, e["case_id"])]


def audit(case_id: str, event: str, actor: str, details: dict, member: dict | None = None):
    """Append-only and hash-chained. Records what happened and why, never clinical text."""
    AUDIT_LOG.parent.mkdir(parents=True, exist_ok=True)
    events = read_audit()
    entry = {"time": datetime.now(timezone.utc).isoformat(timespec="seconds"), "case_id": case_id,
             "event": event, "actor": actor,
             "details": json.loads(mask_identifiers(json.dumps(details, default=str), member)),
             "prev_hash": events[-1]["hash"] if events else "0" * 64}
    entry["hash"] = _hash(entry)
    with AUDIT_LOG.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry) + "\n")


def audit_chain_intact() -> bool:
    previous = "0" * 64
    for entry in read_audit():
        if entry["prev_hash"] != previous or _hash(entry) != entry["hash"]:
            return False
        previous = entry["hash"]
    return True

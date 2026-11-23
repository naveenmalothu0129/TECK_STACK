"""AGENT 1 - Intake & Safety (rules only, no AI).

Runs before any AI reads the documents:
  open each file -> remove hidden/injected text -> catch other patients' pages
  -> mask identifiers -> check eligibility and network -> start the deadline clock
"""
import json
import logging
import re
from pathlib import Path

from pypdf import PdfReader

from . import safety_checks as safety
from .settings import SAMPLE_DIR, coverage_rules, read_json

logging.getLogger("pypdf").setLevel(logging.ERROR)
AGENT = "Agent 1: Intake & Safety"


def make_flag(code, severity, message, agent, doc_id=None, page=None):
    return {"code": code, "severity": severity, "message": message, "agent": agent, "doc_id": doc_id, "page": page}


def read_pages(path: Path) -> list[str]:
    """Return the text of each page. Raises if the file is broken or not what it claims to be."""
    data = path.read_bytes()
    if path.suffix == ".txt":
        return data.decode("utf-8").split("\f")
    if path.suffix == ".pdf":
        if not data.startswith(b"%PDF-"):
            raise ValueError("not a real PDF")
        pages = [p.extract_text() or "" for p in PdfReader(path).pages]
        if not pages:
            raise ValueError("PDF has no pages")
        return pages
    raise ValueError(f"file type {path.suffix} is not accepted")


def intake_agent(state: dict) -> dict:
    case_dir = Path(state["case_dir"])
    manifest = read_json(case_dir / "manifest.json")
    rules = coverage_rules()
    member = read_json(SAMPLE_DIR / "members.json", {}).get(manifest["member_id"])
    provider = read_json(SAMPLE_DIR / "providers.json", {}).get(manifest["provider_npi"])
    policy = rules["services"].get(manifest["code"])
    flags, documents, intake_ok = [], [], True
    safety.audit(manifest["case_id"], "CASE_RECEIVED", AGENT, {"channel": manifest["channel"], "code": manifest["code"]}, member)

    # ---- coverage, network and policy
    if not member or not member["eligible"]:
        flags.append(make_flag("NOT_ELIGIBLE", "high", "Member not found or coverage is not active", AGENT))
    if provider and provider["network"] != "in":
        flags.append(make_flag("OUT_OF_NETWORK", "medium", f"{provider['name']} is out of network", AGENT))
    if not policy:
        flags.append(make_flag("NO_POLICY", "high", f"No coverage policy set up for code {manifest['code']}", AGENT))

    # ---- each document
    for i, entry in enumerate(manifest["documents"], 1):
        doc = {"doc_id": f"D{i}", "file": entry["file"], "type": entry["type"],
               "type_label": rules["document_types"].get(entry["type"], entry["type"]),
               "status": "used", "status_reason": "", "pages": []}
        try:
            raw_pages = read_pages(case_dir / entry["file"])
        except Exception as err:
            flags.append(make_flag("FILE_CORRUPTED", "high", f"{entry['file']} could not be opened ({err})", AGENT, doc["doc_id"]))
            doc.update(status="unreadable", status_reason="File is damaged or not a real PDF")
            intake_ok = False
            documents.append(doc)
            continue

        if sum(len(p.strip()) for p in raw_pages) < 40:
            flags.append(make_flag("LOW_QUALITY_SCAN", "high", f"{entry['file']} is an image-only fax with no readable text", AGENT, doc["doc_id"]))

        for n, raw in enumerate(raw_pages, 1):
            clean, hidden, removed = safety.sanitize(raw)
            if hidden:
                flags.append(make_flag("HIDDEN_CHARACTERS", "medium",
                                       f"{hidden} invisible characters were hidden in the text", AGENT, doc["doc_id"], n))
            if removed:
                flags.append(make_flag("PROMPT_INJECTION", "high",
                                       f"{removed} line(s) tried to give instructions to the AI and were removed", AGENT, doc["doc_id"], n))
                safety.audit(manifest["case_id"], "INJECTION_REMOVED", AGENT, {"doc": doc["doc_id"], "page": n, "lines": removed})
            extra = safety.extra_identifiers(clean)
            if extra:
                flags.append(make_flag("PHI_MASKED", "info",
                                       f"{' and '.join(extra)} masked (not needed for review)", AGENT, doc["doc_id"], n))
            # Wrong-patient check: someone else's record must never become evidence
            named = re.search(r"Patient: ([A-Z][a-z]+(?: [A-Z][a-z]+)+)", clean)
            if member and named and named.group(1).lower() != member["name"].lower():
                doc["other_patient"] = named.group(1)
            doc["pages"].append({"page": n, "text": safety.mask_identifiers(clean, member)})

        if doc.get("other_patient"):
            doc.update(status="excluded", status_reason="Belongs to a different patient")
            flags.append(make_flag("WRONG_PATIENT_DOCUMENT", "high",
                                   f"{entry['file']} is for a different patient, so it was not used as evidence", AGENT, doc["doc_id"]))
            safety.audit(manifest["case_id"], "DOCUMENT_EXCLUDED", AGENT, {"doc": doc["doc_id"], "reason": "different patient"})
        documents.append(doc)

    safety.audit(manifest["case_id"], "INTAKE_DONE", AGENT, {"ok": intake_ok, "flags": [f["code"] for f in flags]})
    return {"case_id": manifest["case_id"], "manifest": manifest, "member": member or {}, "provider": provider or {},
            "policy": policy or {}, "documents": documents, "flags": flags, "intake_ok": intake_ok,
            "deadline": safety.deadline(manifest["received_at"], manifest["urgency"])}


if __name__ == "__main__":  # quick look: python -m backend.agent1_intake_safety
    from .settings import CASES_DIR
    print(json.dumps(intake_agent({"case_dir": str(CASES_DIR / "KNEE-03")})["flags"], indent=2))

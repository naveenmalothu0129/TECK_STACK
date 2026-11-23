"""Safety tests. Run: pytest -q"""
from backend import safety_checks as safety
from backend.api_server import check_decision
from backend.settings import SAMPLE_DIR, read_json
from backend.workflow import process_all_cases

safety.AUDIT_LOG.unlink(missing_ok=True)
CASES = {c["case_id"]: c for c in process_all_cases()}
EXPECTED = read_json(SAMPLE_DIR / "expected_routes.json")


def test_every_case_routes_as_expected():
    assert {k: v["route"] for k, v in CASES.items()} == EXPECTED


def test_ai_never_denies():
    assert all(c["route"] in safety.ROUTES and "DENY" not in c["route"] for c in CASES.values())


def test_only_a_physician_can_deny_and_must_name_the_rule():
    case = CASES["SLEEP-02"]
    assert check_decision(case, {"role": "nurse", "decision": "deny", "rationale": "x", "deny_basis": ["PSG-3"]})
    assert check_decision(case, {"role": "physician", "decision": "deny", "rationale": "x", "deny_basis": []})
    assert check_decision(case, {"role": "physician", "decision": "deny", "rationale": "x", "deny_basis": ["PSG-3"]}) is None


def test_prompt_injections_are_removed_and_never_fast_tracked():
    for case_id in ("KNEE-03", "SLEEP-03"):
        assert CASES[case_id]["route"] == "SECURITY_REVIEW"
        text = " ".join(p["text"] for d in CASES[case_id]["documents"] for p in d["pages"]).lower()
        assert "ignore all previous" not in text and safety.REMOVED_MARKER.lower() in text


def test_other_patients_document_is_never_used():
    case = CASES["RA-02"]
    assert not any(c["fact"].startswith("tb_") for c in case["citations"])
    assert any(m["fact"] == "tb_result" for m in case["missing"])
    assert "Marcus" not in case["provider_letter"]


def test_missing_items_say_where_we_looked():
    missing = CASES["SPINE-01"]["missing"]
    assert missing and missing[0]["where"].startswith("Looked in:")


def test_made_up_quote_is_rejected():
    spec, page = {"type": "number"}, "Completed 6 weeks of supervised physical therapy."
    assert safety.verify_citation({"quote": "Completed 6 weeks of supervised physical therapy", "value": 6.0}, spec, page) is None
    assert safety.verify_citation({"quote": "Completed 12 weeks of physical therapy", "value": 12.0}, spec, page)
    assert safety.verify_citation({"quote": "Completed 6 weeks of supervised physical therapy", "value": 12.0}, spec, page)


def test_no_patient_details_in_audit_log():
    log = safety.AUDIT_LOG.read_text(encoding="utf-8")
    assert "900-55-1234" not in log and "Whitfield" not in log and "1954-03-12" not in log


def test_audit_log_is_tamper_evident():
    assert safety.audit_chain_intact()
    lines = safety.AUDIT_LOG.read_text(encoding="utf-8").splitlines()
    lines[1] = lines[1].replace("Intake", "Someone")
    safety.AUDIT_LOG.write_text("\n".join(lines) + "\n", encoding="utf-8")
    assert not safety.audit_chain_intact()
    safety.AUDIT_LOG.unlink()
    process_all_cases()  # restore a clean log

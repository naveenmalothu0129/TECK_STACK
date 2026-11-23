"""Run all sample cases through the 3 agents and compare each route with the expected answer.

Run: python run_pipeline.py
"""
from backend import safety_checks as safety
from backend.settings import DECISIONS_FILE, SAMPLE_DIR, read_json, use_claude
from backend.workflow import process_all_cases

if __name__ == "__main__":
    safety.AUDIT_LOG.unlink(missing_ok=True)  # fresh audit trail for each run
    DECISIONS_FILE.unlink(missing_ok=True)
    expected = read_json(SAMPLE_DIR / "expected_routes.json")
    print(f"Mode: {'Claude' if use_claude() else 'Offline rules (no API key)'}\n")
    print(f"{'CASE':<10} {'AI ROUTE':<17} {'EXPECTED':<17} {'OK':<4} {'RULES MET':<10} {'MISSING':<8} PROBLEMS")
    correct = 0
    for case in process_all_cases():
        want = expected.get(case["case_id"], "?")
        ok = case["route"] == want
        correct += ok
        c = case["counts"]
        problems = ", ".join(p["code"] for p in case["problems"] if p["severity"] != "info")
        print(f"{case['case_id']:<10} {case['route']:<17} {want:<17} {'yes' if ok else 'NO':<4} "
              f"{c['rules_met']}/{c['rules_total']:<8} {c['missing']:<8} {problems}")
    print(f"\nRoute accuracy: {correct}/{len(expected)}")
    print(f"Audit chain intact: {safety.audit_chain_intact()}")

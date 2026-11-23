"""AGENT 3 - Policy & Compliance (rules only, no AI).

Checks the facts against the coverage policy, finds conflicts, picks the route,
drafts the provider letter, and writes a plain-English case summary:
  - what's wrong   (problems found, with where they are)
  - what's missing (what the provider must send, and where we looked)
  - policy checklist (each rule, what was found, and the citation)
"""
from datetime import date

from . import safety_checks as safety
from .agent1_intake_safety import make_flag
from .agent2_clinical_evidence import fact_specs, usable_documents

AGENT = "Agent 3: Policy & Compliance"

PROBLEM_TEXT = {  # code: (plain title, what to do)
    "FILE_CORRUPTED": ("A file can't be opened", "Ask the provider to resend this document."),
    "LOW_QUALITY_SCAN": ("Scan has no readable text", "Read the original fax by hand or run OCR."),
    "PROMPT_INJECTION": ("Someone tried to give the AI instructions", "Security reviews the removed lines before clinical review."),
    "HIDDEN_CHARACTERS": ("Invisible characters were hidden in the text", "Treat this document as suspicious and check where it came from."),
    "WRONG_PATIENT_DOCUMENT": ("A document belongs to another patient", "It was left out of the evidence. Report it to the Privacy Office and request the correct record."),
    "OUT_OF_NETWORK": ("Provider is out of network", "Check network exception or continuity-of-care rules."),
    "NOT_ELIGIBLE": ("Member's coverage is not active", "Confirm eligibility before review."),
    "NO_POLICY": ("No coverage policy for this service", "Send to a physician reviewer for manual review."),
    "AI_UNAVAILABLE": ("The AI was unavailable", "Facts came from simple rules, so check each one against the document."),
    "UNCHECKED_QUOTE": ("Some quotes failed the citation check", "Check those facts in the source document."),
    "LETTER_BLOCKED": ("Provider letter blocked for privacy", "Rewrite the letter without the flagged details."),
    "PHI_MASKED": ("Extra personal details were masked", "No action needed. They aren't needed for review."),
}

STATUS_TEXT = {"MET": "Met", "UNMET": "Not met", "MISSING": "Information missing", "NEEDS_REVIEW": "Couldn't check evidence"}


def show(value, spec: dict) -> str:
    """Turn a stored value into something a nurse can read."""
    if value is None:
        return "-"
    if isinstance(value, bool):
        return "Yes" if value else "No"
    if isinstance(value, float):
        text = str(int(value)) if value.is_integer() else str(value)
        return f"{text} {spec['unit']}" if spec.get("unit") else text
    if spec.get("type") == "enum":
        return str(value).replace("_", " ").capitalize()
    return str(value)


def check_rule(rule: dict, facts: dict, specs: dict, cites: dict, received: date):
    """Evaluate one policy rule. Returns (status, missing_fact_keys, checks shown to the nurse)."""
    for combo in ("all", "any"):
        if combo in rule:
            results = [check_rule(r, facts, specs, cites, received) for r in rule[combo]]
            statuses = [s for s, _, _ in results]
            missing = [k for _, ks, _ in results for k in ks]
            checks = [c for _, _, cs in results for c in cs]
            if combo == "any" and set(statuses) != {"UNMET"}:
                # an "either/or" rule: an option that fails is not a problem unless every option fails
                checks = [{**c, "status": "NOT_APPLICABLE", "result": c["result"].replace(", which does not meet this", "") + " (this option doesn't apply)"}
                          if c["status"] == "UNMET" else c for c in checks]
            if combo == "any" and "MET" in statuses:
                return "MET", [], checks
            if combo == "all" and "UNMET" in statuses:
                return "UNMET", [], checks
            for s in ("NEEDS_REVIEW", "MISSING"):
                if s in statuses:
                    return s, missing, checks
            return ("MET" if combo == "all" else "UNMET"), [], checks

    key, spec = rule["fact"], specs[rule["fact"]]
    fact = facts.get(key, {"status": "not_found"})
    check = {"need": rule["need"], "fact": key, "label": spec["label"], "cite": cites.get(key)}
    if fact["status"] == "not_found":
        return "MISSING", [key], [{**check, "status": "MISSING", "result": "Not found in the documents"}]
    found = show(fact["value"], spec)
    if fact["status"] != "found":
        return "NEEDS_REVIEW", [], [{**check, "status": "NEEDS_REVIEW", "result": f"Found {found}, but {fact.get('problem')}"}]
    v, target, op = fact["value"], rule["value"], rule["op"]
    ok = {"==": lambda: v == target, ">=": lambda: v >= target, "<": lambda: v < target,
          "in": lambda: v in target, "startswith": lambda: any(str(v).startswith(t) for t in target),
          "within_days": lambda: (received - date.fromisoformat(v)).days <= target}[op]()
    status = "MET" if ok else "UNMET"
    result = f"Found: {found}" if ok else f"Found: {found}, which does not meet this"
    return status, [], [{**check, "status": status, "result": result}]


def policy_agent(state: dict) -> dict:
    manifest, policy, member, provider = state["manifest"], state["policy"], state["member"], state["provider"]
    documents = state["documents"]
    docs_by_id = {d["doc_id"]: d for d in documents}
    facts = dict(state.get("facts", {}))
    flags = list(state["flags"])
    specs = {s["key"]: s for s in fact_specs(policy)} if policy else {}
    criteria, conflicts, missing, citations = [], [], [], []

    if state["intake_ok"] and policy:
        # Trusted plan data, not from the submitted documents
        specs["prescriber_specialty"] = {"key": "prescriber_specialty", "label": "Prescriber specialty", "type": "string"}
        facts["prescriber_specialty"] = {"status": "found", "value": provider.get("specialty"),
                                         "quote": f"{provider.get('name')} is listed as {provider.get('specialty')}",
                                         "doc_id": "REGISTRY", "page": None}

        # ---- number every citation so the nurse can click [1], [2] ...
        cites = {}
        for key, fact in facts.items():
            if fact.get("quote") and fact["status"] in ("found", "unverified"):
                doc = docs_by_id.get(fact.get("doc_id"))
                cites[key] = len(citations) + 1
                citations.append({
                    "n": cites[key], "fact": key, "label": specs[key]["label"], "value": show(fact["value"], specs[key]),
                    "quote": fact["quote"], "doc_id": fact.get("doc_id"), "page": fact.get("page"),
                    "source": f"{doc['type_label']} ({doc['file']}), page {fact.get('page')}" if doc else "Provider directory",
                    "checked": fact["status"] == "found", "problem": fact.get("problem")})

        # ---- policy checklist
        received = date.fromisoformat(manifest["received_at"][:10])
        for c in policy["criteria"]:
            status, missing_keys, checks = check_rule(c["rule"], facts, specs, cites, received)
            criteria.append({"id": c["id"], "title": c["title"], "status": status, "status_text": STATUS_TEXT[status],
                             "logic": "any" if "any" in c["rule"] else "all", "checks": checks})
            for key in missing_keys:
                spec = specs[key]
                if any(m["fact"] == key for m in missing):
                    continue
                looked = [d for d in usable_documents(documents) if d["type"] in spec.get("sources", [])]
                where = ("Looked in: " + ", ".join(f"{d['type_label']} ({d['file']})" for d in looked)) if looked else \
                    "No " + " or ".join(state_label(t) for t in spec.get("sources", [])).lower() + " was submitted"
                missing.append({"fact": key, "item": spec["ask"], "needed_for": f"{c['id']} {c['title']}", "where": where})

        # ---- conflicts between documents
        for rule in policy.get("must_match", []):
            a, b = rule["facts"]
            fa, fb = facts.get(a, {}), facts.get(b, {})
            if fa.get("status") == fb.get("status") == "found" and fa["value"] != fb["value"]:
                conflicts.append({"code": rule["code"], "title": rule["title"], "action": rule["action"],
                                  "detail": f"{specs[a]['label']}: {show(fa['value'], specs[a])}. "
                                            f"{specs[b]['label']}: {show(fb['value'], specs[b])}.",
                                  "cites": [cites.get(a), cites.get(b)]})
        code_fact = facts.get("requested_code", {})
        if code_fact.get("status") == "found" and code_fact["value"] != manifest["code"]:
            conflicts.append({"code": "CODE_MISMATCH", "title": "Requested code doesn't match",
                              "detail": f"Form says {code_fact['value']}, portal says {manifest['code']}.",
                              "action": "Confirm the correct service with the provider.", "cites": [cites.get("requested_code")]})

    route, reasons = safety.decide_route(state["intake_ok"], flags, criteria, conflicts, missing)

    # ---- provider letter for missing items
    letter = ""
    if missing:
        others = [d["other_patient"] for d in documents if d.get("other_patient")]
        letter = (f"Re: Prior authorization {manifest['case_id']}, additional information needed\n"
                  f"Patient: {member.get('name')}    Member ID: {safety.mask_id(manifest['member_id'])}\n"
                  f"Service: {manifest['code']} {policy.get('title', '')}\n\n"
                  f"To finish our review under policy {policy.get('policy_id')} (version {policy.get('version')}), please send:\n"
                  + "\n".join(f"  {i}. {m['item']}" for i, m in enumerate(missing, 1))
                  + "\n\nYou can upload these through the provider portal.\nUtilization Management")
        leaks = safety.letter_privacy_check(letter, others)
        if leaks:
            flags.append(make_flag("LETTER_BLOCKED", "high", f"Letter blocked: {', '.join(leaks)}", AGENT))
            letter = ""

    # ---- what's wrong, in plain words
    problems = [{"severity": "high", "code": c["code"], "title": c["title"], "detail": c["detail"],
                 "action": c["action"], "cites": [n for n in c["cites"] if n], "doc_id": None, "page": None}
                for c in conflicts]
    for f in flags:
        title, action = PROBLEM_TEXT.get(f["code"], (f["code"].replace("_", " ").capitalize(), ""))
        doc = docs_by_id.get(f.get("doc_id"))
        where = f"{doc['type_label']} ({doc['file']})" + (f", page {f['page']}" if f.get("page") else "") if doc else ""
        problems.append({"severity": f["severity"], "code": f["code"], "title": title, "detail": f["message"],
                         "action": action, "where": where, "doc_id": f.get("doc_id"), "page": f.get("page"), "cites": []})
    order = {"high": 0, "medium": 1, "info": 2}
    problems.sort(key=lambda p: order[p["severity"]])

    met = sum(c["status"] == "MET" for c in criteria)
    headline = {
        "FAST_TRACK": f"All {len(criteria)} policy rules are met, backed by {sum(c['checked'] for c in citations)} checked citations.",
        "PEND_FOR_INFO": f"{len(missing)} item(s) must come from the provider before a decision.",
        "NURSE_REVIEW": "Something in the documents needs a nurse's judgment.",
        "MD_REVIEW": f"{len(criteria) - met} policy rule(s) are not met.",
        "SECURITY_REVIEW": "The documents contain text trying to instruct the AI.",
        "INTAKE_EXCEPTION": "A submitted file could not be opened.",
    }[route]

    case = {
        "case_id": manifest["case_id"], "test_scenario": manifest["description"],
        "route": route, "route_label": safety.ROUTES[route]["label"], "headline": headline,
        "next_step": safety.ROUTES[route]["next_step"], "reasons": reasons,
        "service": {"code": manifest["code"], "name": policy.get("title", "Unknown service")},
        "policy": {"id": policy.get("policy_id"), "version": policy.get("version")},
        "member": {"name": member.get("name"), "dob": member.get("dob"), "plan": member.get("plan"),
                   "member_id": safety.mask_id(manifest["member_id"])},
        "provider": provider, "channel": manifest["channel"], "received_at": manifest["received_at"],
        "deadline": state["deadline"],
        "counts": {"problems": sum(p["severity"] != "info" for p in problems), "missing": len(missing),
                   "rules_met": met, "rules_total": len(criteria)},
        "problems": problems, "missing": missing, "criteria": criteria, "citations": citations,
        "documents": documents, "provider_letter": letter, "extraction_mode": state.get("extraction_mode", "skipped"),
    }
    safety.audit(manifest["case_id"], "ROUTED", AGENT, {
        "route": route, "policy": f"{policy.get('policy_id')} v{policy.get('version')}",
        "rules": {c["id"]: c["status"] for c in criteria}, "flags": [f["code"] for f in flags]})
    return {"flags": flags, "route": route, "case": case}


def state_label(doc_type: str) -> str:
    from .settings import coverage_rules
    return coverage_rules()["document_types"].get(doc_type, doc_type)

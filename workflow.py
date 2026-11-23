r"""LangGraph workflow: connects the three agents.

    START -> Agent 1 (Intake & Safety) --file ok--> Agent 2 (Clinical Evidence) -> Agent 3 (Policy & Compliance) -> END
                                       \--file broken------------------------------> Agent 3
"""
import time
from pathlib import Path
from typing import TypedDict

from langgraph.graph import END, START, StateGraph

from .agent1_intake_safety import intake_agent
from .agent2_clinical_evidence import clinical_agent
from .agent3_policy_compliance import policy_agent
from .settings import CASES_DIR, RESULTS_DIR, read_json, write_json


class CaseState(TypedDict, total=False):
    case_dir: str
    case_id: str
    manifest: dict
    member: dict
    provider: dict
    policy: dict
    documents: list
    flags: list
    intake_ok: bool
    deadline: dict
    facts: dict
    extraction_mode: str
    route: str
    case: dict


def build_workflow():
    graph = StateGraph(CaseState)
    graph.add_node("intake_safety", intake_agent)
    graph.add_node("clinical_evidence", clinical_agent)
    graph.add_node("policy_compliance", policy_agent)
    graph.add_edge(START, "intake_safety")
    graph.add_conditional_edges("intake_safety", lambda s: "ok" if s["intake_ok"] else "broken",
                                {"ok": "clinical_evidence", "broken": "policy_compliance"})
    graph.add_edge("clinical_evidence", "policy_compliance")
    graph.add_edge("policy_compliance", END)
    return graph.compile()


WORKFLOW = build_workflow()


def process_case(case_dir: Path) -> dict:
    started = time.time()
    case = WORKFLOW.invoke({"case_dir": str(case_dir)})["case"]
    case["processing_seconds"] = round(time.time() - started, 2)
    write_json(RESULTS_DIR / f"{case['case_id']}.json", case)
    return case


def process_all_cases() -> list:
    return [process_case(d) for d in sorted(CASES_DIR.iterdir()) if d.is_dir()]


def load_results() -> list:
    return [read_json(p) for p in sorted(RESULTS_DIR.glob("*.json"))] if RESULTS_DIR.exists() else []

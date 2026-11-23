import { useState } from "react";
import { ROUTE_ORDER, ROUTE_STYLE, hoursText } from "../api.js";

const FILTER_LABELS = {
  FAST_TRACK: "Ready to approve",
  PEND_FOR_INFO: "Missing information",
  NURSE_REVIEW: "Needs nurse review",
  MD_REVIEW: "Physician review",
  SECURITY_REVIEW: "Security hold",
  INTAKE_EXCEPTION: "File can't be processed",
};

export default function WorkQueue({ cases, onOpen, onRun, running }) {
  const [filter, setFilter] = useState("ALL");

  if (!cases.length) {
    return (
      <section className="empty">
        <h2>No cases in the queue yet</h2>
        <p>Run the AI on the 11 sample requests to see how each one is checked, cited and routed.</p>
        <button className="btn primary" onClick={onRun} disabled={running}>
          {running ? "Running the 3 agents…" : "Run AI on all cases"}
        </button>
      </section>
    );
  }

  const sorted = [...cases].sort((a, b) =>
    ROUTE_ORDER.indexOf(a.route) - ROUTE_ORDER.indexOf(b.route) || a.deadline.hours_left - b.deadline.hours_left);
  const shown = filter === "ALL" ? sorted : sorted.filter((c) => c.route === filter);
  const counts = Object.fromEntries(ROUTE_ORDER.map((r) => [r, cases.filter((c) => c.route === r).length]));

  return (
    <section>
      <div className="queue-head">
        <div>
          <h2>Work queue</h2>
          <p className="muted">Most urgent problems first, then by decision deadline. Click a case to review it.</p>
        </div>
      </div>

      <div className="filters" role="group" aria-label="Filter by status">
        <button className={`filter ${filter === "ALL" ? "on" : ""}`} onClick={() => setFilter("ALL")}>
          All <b>{cases.length}</b>
        </button>
        {ROUTE_ORDER.filter((r) => counts[r]).map((r) => (
          <button key={r} className={`filter ${filter === r ? "on" : ""}`} onClick={() => setFilter(r)}>
            <span className={`dot ${ROUTE_STYLE[r]}`} aria-hidden="true" />
            {FILTER_LABELS[r]} <b>{counts[r]}</b>
          </button>
        ))}
      </div>

      <div className="table-wrap">
        <table className="queue">
          <thead>
            <tr>
              <th>Status</th><th>Case</th><th>Service</th><th>Patient</th>
              <th>Policy rules</th><th>Problems</th><th>Missing</th><th>Deadline</th><th>Decision</th>
            </tr>
          </thead>
          <tbody>
            {shown.map((c) => (
              <tr key={c.case_id} onClick={() => onOpen(c.case_id)} tabIndex={0}
                onKeyDown={(e) => e.key === "Enter" && onOpen(c.case_id)}>
                <td><span className={`badge ${ROUTE_STYLE[c.route]}`}>{c.route_label}</span></td>
                <td className="strong">{c.case_id}</td>
                <td>{c.service.name}</td>
                <td>{c.member.name}</td>
                <td>{c.counts.rules_total ? `${c.counts.rules_met} of ${c.counts.rules_total} met` : "Not checked"}</td>
                <td>{c.counts.problems ? <span className="count wrong">{c.counts.problems}</span> : <span className="muted">None</span>}</td>
                <td>{c.counts.missing ? <span className="count missing">{c.counts.missing}</span> : <span className="muted">None</span>}</td>
                <td className={c.deadline.status === "on track" ? "" : "warn-text"}>
                  {hoursText(c.deadline)}{c.deadline.urgency === "expedited" && <span className="tag">Expedited</span>}
                </td>
                <td>{c.decision ? <span className="decided">{c.decision.decision}</span> : <span className="muted">Waiting</span>}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

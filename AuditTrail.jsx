import { useEffect, useState } from "react";
import { api } from "../api.js";

const EVENT_TEXT = {
  CASE_RECEIVED: "Case received",
  INJECTION_REMOVED: "Injected text removed",
  DOCUMENT_EXCLUDED: "Document left out",
  INTAKE_DONE: "Intake checks finished",
  SELF_CORRECTION: "AI asked to fix a quote",
  FACTS_EXTRACTED: "Facts extracted",
  ROUTED: "Route decided",
  HUMAN_DECISION: "Reviewer decision",
};

export default function AuditTrail({ cases }) {
  const [caseId, setCaseId] = useState("");
  const [data, setData] = useState(null);

  useEffect(() => { api.audit(caseId).then(setData); }, [caseId]);

  return (
    <section>
      <h2>Audit trail</h2>
      <p className="muted">Every step by the agents and every human decision, in order. No clinical text or patient identifiers are stored here.</p>
      <div className="audit-bar">
        <label>Case
          <select value={caseId} onChange={(e) => setCaseId(e.target.value)}>
            <option value="">All cases</option>
            {cases.map((c) => <option key={c.case_id} value={c.case_id}>{c.case_id}</option>)}
          </select>
        </label>
        {data && (
          <span className={`badge ${data.intact ? "ready" : "danger"}`}>
            {data.intact ? "Log intact: no entries changed" : "Log broken: an entry was changed"}
          </span>
        )}
      </div>
      {data && data.events.length === 0 && <p className="muted">No events yet. Run the AI on the sample cases first.</p>}
      {data && data.events.length > 0 && (
        <div className="table-wrap">
          <table className="audit">
            <thead><tr><th>Time (UTC)</th><th>Case</th><th>What happened</th><th>By</th><th>Details</th><th>Fingerprint</th></tr></thead>
            <tbody>
              {data.events.map((e) => (
                <tr key={e.hash}>
                  <td>{e.time.replace("T", " ").slice(0, 19)}</td>
                  <td className="strong">{e.case_id}</td>
                  <td>{EVENT_TEXT[e.event] || e.event}</td>
                  <td>{e.actor}</td>
                  <td className="details">{Object.entries(e.details).map(([k, v]) =>
                    <span key={k}><b>{k}:</b> {typeof v === "object" ? JSON.stringify(v) : String(v)} </span>)}</td>
                  <td className="hash" title={e.hash}>{e.hash.slice(0, 10)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}

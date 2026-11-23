import { useState } from "react";
import { api } from "../api.js";

export default function DecisionForm({ c, onSaved }) {
  const [role, setRole] = useState("nurse");
  const [reviewerId, setReviewerId] = useState("RN-0142");
  const [decision, setDecision] = useState("");
  const [denyBasis, setDenyBasis] = useState([]);
  const [securityCleared, setSecurityCleared] = useState(false);
  const [aiAccurate, setAiAccurate] = useState("Yes");
  const [rationale, setRationale] = useState("");
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);

  const options = [
    { id: "approve", label: "Approve" },
    { id: "pend", label: "Pend and send letter to provider" },
    { id: "escalate", label: "Send to physician reviewer" },
    ...(role === "physician" ? [{ id: "deny", label: "Deny" }] : []),
  ];
  const notMet = c.criteria.filter((cr) => cr.status !== "MET");

  function changeRole(r) {
    setRole(r);
    setReviewerId(r === "nurse" ? "RN-0142" : "MD-0007");
    if (decision === "deny") setDecision("");
  }

  async function submit(e) {
    e.preventDefault();
    setError("");
    setSaving(true);
    try {
      await api.decide(c.case_id, { role, reviewer_id: reviewerId, decision, deny_basis: denyBasis,
        security_cleared: securityCleared, ai_accurate: aiAccurate, rationale });
      onSaved();
    } catch (err) {
      setError(err.message);
    } finally {
      setSaving(false);
    }
  }

  if (c.decision) {
    return (
      <section className="block decision-done">
        <h3 className="block-title">Decision recorded</h3>
        <p><b>{c.decision.decision}</b> by {c.decision.reviewer}</p>
        <p className="muted">{c.decision.rationale}</p>
        {c.decision.deny_basis?.length > 0 && <p>Denial based on: {c.decision.deny_basis.join(", ")}</p>}
      </section>
    );
  }

  return (
    <form className="block decision" onSubmit={submit}>
      <h3 className="block-title">Your decision</h3>
      <p className="muted">The AI only recommends. A licensed reviewer makes the decision, and only a physician can deny.</p>

      <div className="form-row">
        <label>Reviewing as
          <select value={role} onChange={(e) => changeRole(e.target.value)}>
            <option value="nurse">Nurse reviewer</option>
            <option value="physician">Physician reviewer</option>
          </select>
        </label>
        <label>Reviewer ID
          <input value={reviewerId} onChange={(e) => setReviewerId(e.target.value)} />
        </label>
      </div>

      <fieldset className="choices">
        <legend>Decision</legend>
        {options.map((o) => (
          <label key={o.id} className={`choice ${decision === o.id ? "on" : ""}`}>
            <input type="radio" name="decision" value={o.id} checked={decision === o.id} onChange={() => setDecision(o.id)} />
            {o.label}
          </label>
        ))}
      </fieldset>

      {decision === "deny" && (
        <fieldset className="choices">
          <legend>Which policy rules are not met? (required)</legend>
          {notMet.length === 0 && <p className="warn-text">Every rule is met, so there is nothing to base a denial on.</p>}
          {notMet.map((cr) => (
            <label key={cr.id} className="choice">
              <input type="checkbox" checked={denyBasis.includes(cr.id)}
                onChange={(e) => setDenyBasis(e.target.checked ? [...denyBasis, cr.id] : denyBasis.filter((x) => x !== cr.id))} />
              {cr.id} {cr.title}
            </label>
          ))}
        </fieldset>
      )}

      {c.route === "SECURITY_REVIEW" && (
        <label className="choice">
          <input type="checkbox" checked={securityCleared} onChange={(e) => setSecurityCleared(e.target.checked)} />
          Security has reviewed the removed text
        </label>
      )}

      <fieldset className="choices inline">
        <legend>Was the AI summary accurate?</legend>
        {["Yes", "Partly", "No"].map((v) => (
          <label key={v} className={`choice ${aiAccurate === v ? "on" : ""}`}>
            <input type="radio" name="accurate" checked={aiAccurate === v} onChange={() => setAiAccurate(v)} />{v}
          </label>
        ))}
      </fieldset>

      <label className="full">Rationale
        <textarea rows={3} value={rationale} onChange={(e) => setRationale(e.target.value)}
          placeholder="Why you made this decision. This is saved to the audit trail." />
      </label>

      {error && <div className="alert danger" role="alert">{error}</div>}
      <button className="btn primary" type="submit" disabled={!decision || saving}>
        {saving ? "Recording…" : "Record decision"}
      </button>
    </form>
  );
}

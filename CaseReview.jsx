import { useEffect, useState } from "react";
import { api, ROUTE_STYLE, hoursText } from "../api.js";
import CitationTag from "./CitationTag.jsx";
import DocumentViewer from "./DocumentViewer.jsx";
import DecisionForm from "./DecisionForm.jsx";

const STATUS_ICON = { MET: "✓", UNMET: "✕", MISSING: "?", NEEDS_REVIEW: "!" };
const STATUS_STYLE = { MET: "ready", UNMET: "danger", MISSING: "missing", NEEDS_REVIEW: "review", NOT_APPLICABLE: "na" };

export default function CaseReview({ caseId, onBack, onDecided }) {
  const [c, setCase] = useState(null);
  const [error, setError] = useState("");
  const [focus, setFocus] = useState(null); // {doc_id, page, n}

  async function load() {
    try {
      setCase(await api.caseDetail(caseId));
    } catch (e) {
      setError(e.message);
    }
  }
  useEffect(() => { load(); }, [caseId]);

  if (error) return <div className="alert danger">{error}</div>;
  if (!c) return <p className="muted">Loading case…</p>;

  const cites = Object.fromEntries(c.citations.map((x) => [x.n, x]));
  const openCite = (n) => {
    const x = cites[n];
    if (x && x.doc_id !== "REGISTRY") setFocus({ doc_id: x.doc_id, page: x.page, n });
  };
  const problems = c.problems.filter((p) => p.severity !== "info");
  const notes = c.problems.filter((p) => p.severity === "info");

  return (
    <div className="review">
      <div className="review-head">
        <button className="btn ghost" onClick={onBack}>Back to queue</button>
        <div>
          <h2>{c.case_id}: {c.service.name}</h2>
          <p className="muted">Test scenario: {c.test_scenario}</p>
        </div>
      </div>

      <div className="review-grid">
        <div className="review-main">
          {/* ---- Verdict */}
          <section className={`verdict ${ROUTE_STYLE[c.route]}`}>
            <p className="verdict-label">AI recommendation</p>
            <h3>{c.route_label}</h3>
            <p className="verdict-headline">{c.headline}</p>
            <p className="verdict-next"><b>Next step:</b> {c.next_step}</p>
          </section>

          <dl className="facts-row">
            <div><dt>Patient</dt><dd>{c.member.name}<span>DOB {c.member.dob}, ID {c.member.member_id}</span></dd></div>
            <div><dt>Plan</dt><dd>{c.member.plan}</dd></div>
            <div><dt>Ordering provider</dt><dd>{c.provider.name}<span>{c.provider.specialty}, {c.provider.network === "in" ? "in network" : "out of network"}</span></dd></div>
            <div><dt>Policy</dt><dd>{c.policy.id || "None"}<span>{c.policy.version ? `Version ${c.policy.version}` : ""}</span></dd></div>
            <div><dt>Decision due</dt><dd className={c.deadline.status === "on track" ? "" : "warn-text"}>{hoursText(c.deadline)}<span>{c.deadline.urgency} request, received by {c.channel}</span></dd></div>
          </dl>

          {/* ---- What's wrong */}
          <section className="block">
            <h3 className="block-title"><span className="count wrong">{problems.length}</span> What's wrong</h3>
            {problems.length === 0 ? <p className="ok-line">No problems found in the documents.</p> : (
              <ul className="issue-list">
                {problems.map((p, i) => (
                  <li key={i} className={`issue ${p.severity}`}>
                    <p className="issue-title">{p.title}</p>
                    <p>{p.detail} {p.cites.map((n) => <CitationTag key={n} cite={cites[n]} onOpen={openCite} />)}</p>
                    {p.where && (
                      <button className="link" onClick={() => p.doc_id && setFocus({ doc_id: p.doc_id, page: p.page || 1 })}>
                        Where: {p.where}
                      </button>
                    )}
                    {p.action && <p className="issue-action"><b>What to do:</b> {p.action}</p>}
                  </li>
                ))}
              </ul>
            )}
          </section>

          {/* ---- What's missing */}
          <section className="block">
            <h3 className="block-title"><span className="count missing">{c.missing.length}</span> What's missing</h3>
            {c.missing.length === 0 ? <p className="ok-line">Nothing is missing. Every fact the policy needs was found.</p> : (
              <ul className="issue-list">
                {c.missing.map((m) => (
                  <li key={m.fact} className="issue missing">
                    <p className="issue-title">{m.item}</p>
                    <p>Needed for rule {m.needed_for}.</p>
                    <p className="muted">{m.where}, but this was not documented.</p>
                  </li>
                ))}
              </ul>
            )}
          </section>

          {/* ---- Policy checklist */}
          <section className="block">
            <h3 className="block-title">
              Policy checklist
              {c.counts.rules_total > 0 && <span className="muted small"> {c.counts.rules_met} of {c.counts.rules_total} rules met</span>}
            </h3>
            {c.criteria.length === 0 && <p className="muted">The policy could not be checked because a file was unreadable.</p>}
            <ol className="checklist">
              {c.criteria.map((cr) => (
                <li key={cr.id} className="rule">
                  <div className="rule-head">
                    <span className={`status-icon ${STATUS_STYLE[cr.status]}`} aria-hidden="true">{STATUS_ICON[cr.status]}</span>
                    <p><b>{cr.id}</b> {cr.title}</p>
                    <span className={`badge ${STATUS_STYLE[cr.status]}`}>{cr.status_text}</span>
                  </div>
                  {cr.checks.length > 1 && (
                    <p className="rule-logic">{cr.logic === "any" ? "Either one is enough:" : "All of these are needed:"}</p>
                  )}
                  <ul className="checks">
                    {cr.checks.map((ch, i) => (
                      <li key={i} className={`check ${STATUS_STYLE[ch.status]}`}>
                        <span className="check-need">{ch.need}</span>
                        <span className="check-result">
                          {ch.result} {ch.cite && <CitationTag cite={cites[ch.cite]} onOpen={openCite} />}
                        </span>
                      </li>
                    ))}
                  </ul>
                </li>
              ))}
            </ol>
          </section>

          {notes.length > 0 && (
            <section className="block quiet">
              <h3 className="block-title">Privacy notes</h3>
              {notes.map((n, i) => <p key={i} className="muted">{n.detail} ({n.where})</p>)}
            </section>
          )}

          {c.provider_letter && (
            <section className="block">
              <h3 className="block-title">Draft letter to the provider</h3>
              <p className="muted">Written automatically from the missing items. Edit before sending.</p>
              <textarea className="letter" defaultValue={c.provider_letter} rows={11} />
            </section>
          )}

          <DecisionForm c={c} onSaved={() => { load(); onDecided(); }} />
        </div>

        <aside className="review-side">
          <DocumentViewer documents={c.documents} citations={c.citations} focus={focus} onFocus={setFocus} />
        </aside>
      </div>
    </div>
  );
}

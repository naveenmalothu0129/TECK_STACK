import { useEffect, useRef, useState } from "react";

const REMOVED = "[REMOVED BY SAFETY FILTER: suspected instruction to the AI]";
const STATUS_TEXT = { used: "Used as evidence", excluded: "Not used", unreadable: "Can't open" };

function escapeRegex(s) {
  return s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

// Split page text into plain text, highlighted quotes and removed (injected) lines.
function segments(text, cites) {
  const ranges = [];
  for (const c of cites) {
    const pattern = new RegExp(escapeRegex(c.quote.trim()).replace(/\s+/g, "\\s+"), "i");
    const m = pattern.exec(text);
    if (m) ranges.push({ start: m.index, end: m.index + m[0].length, cite: c });
  }
  let idx = text.indexOf(REMOVED);
  while (idx !== -1) {
    ranges.push({ start: idx, end: idx + REMOVED.length, removed: true });
    idx = text.indexOf(REMOVED, idx + 1);
  }
  ranges.sort((a, b) => a.start - b.start);
  const out = [];
  let pos = 0;
  for (const r of ranges) {
    if (r.start < pos) continue; // skip overlaps
    if (r.start > pos) out.push({ text: text.slice(pos, r.start) });
    out.push({ ...r, text: text.slice(r.start, r.end) });
    pos = r.end;
  }
  if (pos < text.length) out.push({ text: text.slice(pos) });
  return out;
}

export default function DocumentViewer({ documents, citations, focus, onFocus }) {
  const [docId, setDocId] = useState(documents[0]?.doc_id);
  const paperRef = useRef(null);
  const doc = documents.find((d) => d.doc_id === docId) || documents[0];

  useEffect(() => {
    if (!focus) return;
    setDocId(focus.doc_id);
    // wait for render, then scroll to the highlighted quote and pulse it
    requestAnimationFrame(() => {
      const root = paperRef.current;
      if (!root) return;
      const target = focus.n ? root.querySelector(`[data-cite="${focus.n}"]`) : root.querySelector(`[data-page="${focus.page}"]`);
      if (target) {
        target.scrollIntoView({ behavior: "smooth", block: "center" });
        target.classList.remove("pulse");
        void target.offsetWidth;
        target.classList.add("pulse");
      }
    });
  }, [focus]);

  if (!doc) return null;
  const docCites = citations.filter((c) => c.doc_id === doc.doc_id);

  return (
    <section className="viewer" aria-label="Submitted documents">
      <h3 className="block-title">Submitted documents</h3>
      <div className="doc-tabs" role="tablist">
        {documents.map((d) => (
          <button key={d.doc_id} role="tab" aria-selected={d.doc_id === doc.doc_id}
            className={`doc-tab ${d.doc_id === doc.doc_id ? "on" : ""} ${d.status}`}
            onClick={() => { setDocId(d.doc_id); onFocus(null); }}>
            <span className="doc-tab-name">{d.doc_id} {d.type_label}</span>
            <span className="doc-tab-status">{STATUS_TEXT[d.status]}</span>
          </button>
        ))}
      </div>

      {doc.status !== "used" && (
        <div className="alert danger">
          <b>{STATUS_TEXT[doc.status]}:</b> {doc.status_reason}.
          {doc.status === "excluded" && " Nothing from this document counts as evidence."}
        </div>
      )}

      {docCites.length > 0 && (
        <ul className="cite-index">
          {docCites.map((c) => (
            <li key={c.n}>
              <button className={`cite ${c.checked ? "" : "unchecked"}`} onClick={() => onFocus({ doc_id: c.doc_id, page: c.page, n: c.n })}>{c.n}</button>
              <span>{c.label}: <b>{c.value}</b>{!c.checked && <em className="warn-text"> (not verified: {c.problem})</em>}</span>
            </li>
          ))}
        </ul>
      )}

      <div className="paper-stack" ref={paperRef}>
        {doc.pages.length === 0 && <p className="muted">No readable text in this file.</p>}
        {doc.pages.map((p) => (
          <article key={p.page} className="paper" data-page={p.page}>
            <p className="paper-meta">{doc.file}, page {p.page}</p>
            <div className="paper-text">
              {segments(p.text, docCites.filter((c) => c.page === p.page)).map((s, i) =>
                s.cite ? (
                  <mark key={i} data-cite={s.cite.n} className={s.cite.checked ? "" : "unchecked"}>
                    {s.text}<sup>{s.cite.n}</sup>
                  </mark>
                ) : s.removed ? (
                  <span key={i} className="removed">{s.text}</span>
                ) : (
                  <span key={i}>{s.text}</span>
                ))}
            </div>
          </article>
        ))}
      </div>
      <p className="muted small">Names, dates of birth and IDs are masked. Yellow marks are quotes the AI cited, numbered to match the checklist.</p>
    </section>
  );
}

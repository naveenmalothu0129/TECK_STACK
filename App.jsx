import { useEffect, useState } from "react";
import { api } from "./api.js";
import WorkQueue from "./components/WorkQueue.jsx";
import CaseReview from "./components/CaseReview.jsx";
import AuditTrail from "./components/AuditTrail.jsx";
import ImpactModel from "./components/ImpactModel.jsx";

const TABS = [
  { id: "queue", label: "Work queue" },
  { id: "audit", label: "Audit trail" },
  { id: "impact", label: "Business impact" },
];

export default function App() {
  const [tab, setTab] = useState("queue");
  const [status, setStatus] = useState(null);
  const [cases, setCases] = useState([]);
  const [openCase, setOpenCase] = useState(null);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState("");

  async function refresh() {
    try {
      const [s, c] = await Promise.all([api.status(), api.cases()]);
      setStatus(s);
      setCases(c);
    } catch (e) {
      setError(e.message);
    }
  }

  useEffect(() => { refresh(); }, []);

  async function runPipeline() {
    setRunning(true);
    setError("");
    try {
      await api.runPipeline();
      setOpenCase(null);
      await refresh();
    } catch (e) {
      setError(e.message);
    } finally {
      setRunning(false);
    }
  }

  return (
    <div className="app">
      <header className="topbar">
        <div className="brand">
          <span className="brand-mark" aria-hidden="true">PA</span>
          <div>
            <h1>PA Review Copilot</h1>
            <p>AI reads and cites. Nurses and physicians decide.</p>
          </div>
        </div>
        <div className="topbar-actions">
          {status && (
            <span className={`mode-pill ${status.mode === "Claude" ? "on" : "off"}`}>
              AI: {status.mode === "Claude" ? `Claude (${status.model})` : "offline rules"}
            </span>
          )}
          <button className="btn primary" onClick={runPipeline} disabled={running}>
            {running ? "Running the 3 agents…" : "Run AI on all cases"}
          </button>
        </div>
      </header>

      <nav className="tabs" aria-label="Sections">
        {TABS.map((t) => (
          <button key={t.id} className={`tab ${tab === t.id && !openCase ? "active" : ""}`}
            onClick={() => { setTab(t.id); setOpenCase(null); }}>
            {t.label}
          </button>
        ))}
        {openCase && <span className="tab active">Case {openCase}</span>}
      </nav>

      {error && <div className="alert danger" role="alert">{error}</div>}

      <main className="content">
        {openCase ? (
          <CaseReview caseId={openCase} onBack={() => setOpenCase(null)} onDecided={refresh} />
        ) : tab === "queue" ? (
          <WorkQueue cases={cases} onOpen={setOpenCase} onRun={runPipeline} running={running} />
        ) : tab === "audit" ? (
          <AuditTrail cases={cases} />
        ) : (
          <ImpactModel />
        )}
      </main>
    </div>
  );
}

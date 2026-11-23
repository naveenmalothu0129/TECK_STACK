import { useState } from "react";

// Simple scenario model. Every assumption is a slider so it can be challenged and replaced with pilot data.
const INPUTS = [
  { key: "volume", label: "Requests per month", min: 5000, max: 30000, step: 500, fmt: (v) => v.toLocaleString() },
  { key: "tat", label: "Turnaround today (days)", min: 1, max: 8, step: 0.1, fmt: (v) => v.toFixed(1) },
  { key: "rework", label: "Requests sent back for missing info today", min: 0, max: 0.5, step: 0.01, fmt: (v) => `${Math.round(v * 100)}%` },
  { key: "reworkDays", label: "Days added each time a request is sent back", min: 1, max: 6, step: 0.5, fmt: (v) => v.toFixed(1) },
  { key: "fast", label: "Clean cases a nurse can confirm same day", min: 0, max: 0.6, step: 0.01, fmt: (v) => `${Math.round(v * 100)}%` },
  { key: "reworkCut", label: "Send-backs avoided by checking at intake", min: 0, max: 0.9, step: 0.05, fmt: (v) => `${Math.round(v * 100)}%` },
  { key: "reviewCut", label: "Review time saved by the cited summary", min: 0, max: 0.6, step: 0.05, fmt: (v) => `${Math.round(v * 100)}%` },
  { key: "minutes", label: "Nurse minutes per case today", min: 10, max: 60, step: 5, fmt: (v) => `${v} min` },
];

export default function ImpactModel() {
  const [v, setV] = useState({ volume: 15000, tat: 4.2, rework: 0.22, reworkDays: 3, fast: 0.25, reworkCut: 0.5, reviewCut: 0.3, minutes: 30 });

  const core = v.tat - v.rework * v.reworkDays;
  const newTat = v.fast * 0.5 + (1 - v.fast) * core * (1 - v.reviewCut) + v.rework * (1 - v.reworkCut) * v.reworkDays;
  const change = (newTat - v.tat) / v.tat;
  const hours = (v.volume * v.minutes * (v.fast * 0.8 + (1 - v.fast) * v.reviewCut)) / 60;

  return (
    <section>
      <h2>Business impact</h2>
      <p className="muted">A scenario model, not a measured result. Move the sliders to test the assumptions; a pilot replaces them with real numbers.</p>
      <div className="impact">
        <div className="impact-inputs">
          {INPUTS.map((i) => (
            <label key={i.key} className="slider">
              <span>{i.label}<b>{i.fmt(v[i.key])}</b></span>
              <input type="range" min={i.min} max={i.max} step={i.step} value={v[i.key]}
                onChange={(e) => setV({ ...v, [i.key]: Number(e.target.value) })} />
            </label>
          ))}
        </div>
        <div className="impact-results">
          <div className="bars" aria-label="Turnaround today versus with AI">
            <div className="bar-row"><span>Today</span><div className="bar today" style={{ width: `${(v.tat / 8) * 100}%` }}>{v.tat.toFixed(1)} days</div></div>
            <div className="bar-row"><span>With AI</span><div className="bar ai" style={{ width: `${(newTat / 8) * 100}%` }}>{newTat.toFixed(1)} days</div></div>
          </div>
          <p className={`impact-change ${change <= -0.4 ? "good" : ""}`}>
            {Math.round(Math.abs(change) * 100)}% faster {change <= -0.4 ? "(meets the 40% goal)" : "(below the 40% goal)"}
          </p>
          <ul className="impact-list">
            <li><b>{Math.round(v.rework * (1 - v.reworkCut) * 100)}%</b> of requests sent back, down from {Math.round(v.rework * 100)}%</li>
            <li><b>{Math.round(hours).toLocaleString()}</b> nurse hours freed each month, about {(hours / 140).toFixed(0)} full-time nurses</li>
          </ul>
        </div>
      </div>
    </section>
  );
}

// Talks to the Python server (backend/api_server.py).
async function request(path, options = {}) {
  const res = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  const data = await res.json();
  if (!res.ok) throw new Error(data.error || `Request failed (${res.status})`);
  return data;
}

export const api = {
  status: () => request("/api/status"),
  cases: () => request("/api/cases"),
  caseDetail: (id) => request(`/api/cases/${id}`),
  runPipeline: () => request("/api/run", { method: "POST" }),
  decide: (id, body) => request(`/api/cases/${id}/decision`, { method: "POST", body: JSON.stringify(body) }),
  audit: (caseId) => request(`/api/audit${caseId ? `?case=${caseId}` : ""}`),
};

// Shared display helpers
export const ROUTE_STYLE = {
  FAST_TRACK: "ready",
  PEND_FOR_INFO: "missing",
  NURSE_REVIEW: "review",
  MD_REVIEW: "physician",
  SECURITY_REVIEW: "danger",
  INTAKE_EXCEPTION: "danger",
};

export const ROUTE_ORDER = ["SECURITY_REVIEW", "INTAKE_EXCEPTION", "MD_REVIEW", "NURSE_REVIEW", "PEND_FOR_INFO", "FAST_TRACK"];

export function hoursText(deadline) {
  const h = deadline.hours_left;
  if (h <= 0) return "Overdue";
  if (h < 48) return `${Math.round(h)} h left`;
  return `${Math.floor(h / 24)} d ${Math.round(h % 24)} h left`;
}

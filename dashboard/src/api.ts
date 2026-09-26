import type { DashboardData, Filters, LogEntry } from "./types";

const BASE = import.meta.env.VITE_API_BASE ?? "http://localhost:8000";

function filtersToParams(f: Filters): URLSearchParams {
  const p = new URLSearchParams();
  p.set("time_range", f.time_range);
  if (f.custom_from) p.set("custom_from", f.custom_from);
  if (f.custom_to) p.set("custom_to", f.custom_to);
  if (f.services.length) p.set("services", f.services.join(","));
  p.set("severities", f.severities.join(","));
  if (f.incident_types.length)
    p.set("incident_types", f.incident_types.join(","));
  return p;
}

export async function fetchDashboard(f: Filters): Promise<DashboardData> {
  const p = filtersToParams(f);
  const r = await fetch(`${BASE}/api/dashboard?${p}`);
  if (!r.ok) throw new Error(`Dashboard API error ${r.status}`);
  return r.json();
}

export async function fetchLogs(
  f: Filters,
  service?: string,
  from_ts?: string,
  to_ts?: string
): Promise<LogEntry[]> {
  const p = filtersToParams(f);
  if (service) p.set("service", service);
  if (from_ts) p.set("from_ts", from_ts);
  if (to_ts) p.set("to_ts", to_ts);
  const r = await fetch(`${BASE}/api/logs?${p}`);
  if (!r.ok) throw new Error(`Logs API error ${r.status}`);
  return r.json();
}

export async function exportLogs(
  f: Filters,
  format: "json" | "csv"
): Promise<Blob> {
  const p = filtersToParams(f);
  p.set("format", format);
  const r = await fetch(`${BASE}/api/export?${p}`);
  if (!r.ok) throw new Error(`Export API error ${r.status}`);
  return r.blob();
}

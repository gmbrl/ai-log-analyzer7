import { useEffect, useRef, useState, useCallback } from "react";
import { useStore } from "../store";
import { fetchDashboard, fetchLogs, exportLogs } from "../api";
import type { DashboardData, IncidentBar, LogEntry } from "../types";
import SeverityCard from "../components/SeverityCard";
import ServiceHealthCard from "../components/ServiceHealthCard";
import IncidentTimelineCard from "../components/IncidentTimelineCard";
import BubbleChartCard from "../components/BubbleChartCard";
import LatencyTrendCard from "../components/LatencyTrendCard";
import LogSourceCard from "../components/LogSourceCard";
import FilterPanel from "../components/FilterPanel";
import LogDrawer from "../components/LogDrawer";

const REFRESH_INTERVAL = 30_000;

export default function DashboardPage() {
  const { filters, setActiveService } = useStore();
  const [data, setData] = useState<DashboardData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [lastUpdated, setLastUpdated] = useState<string>("");

  // Drawer state
  const [drawerLogs, setDrawerLogs] = useState<LogEntry[]>([]);
  const [drawerTitle, setDrawerTitle] = useState("");
  const [drawerOpen, setDrawerOpen] = useState(false);

  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const load = useCallback(async () => {
    try {
      const d = await fetchDashboard(filters);
      setData(d);
      setLastUpdated(new Date().toLocaleTimeString());
      setError(null);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  }, [filters]);

  useEffect(() => {
    setLoading(true);
    load();
  }, [load]);

  useEffect(() => {
    if (timerRef.current) clearInterval(timerRef.current);
    if (filters.auto_refresh) {
      timerRef.current = setInterval(load, REFRESH_INTERVAL);
    }
    return () => {
      if (timerRef.current) clearInterval(timerRef.current);
    };
  }, [filters.auto_refresh, load]);

  async function openServiceLogs(service: string) {
    setActiveService(service);
    try {
      const logs = await fetchLogs(filters, service);
      setDrawerLogs(logs);
      setDrawerTitle(`Logs — ${service}`);
      setDrawerOpen(true);
    } catch {
      // silently ignore — drawer stays closed
    }
  }

  async function openIncidentLogs(bar: IncidentBar) {
    try {
      const logs = await fetchLogs(
        filters,
        bar.service,
        String(bar.timestamp_unix - 180),
        String(bar.timestamp_unix + 180)
      );
      setDrawerLogs(logs);
      setDrawerTitle(`Incident @ ${bar.time} — ${bar.service}`);
      setDrawerOpen(true);
    } catch {
      // silently ignore
    }
  }

  async function handleExport(format: "json" | "csv") {
    try {
      const blob = await exportLogs(filters, format);
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `logs_export.${format}`;
      a.click();
      URL.revokeObjectURL(url);
    } catch {
      // silently ignore
    }
  }

  const services = data
    ? Array.from(
        new Set(data.service_health.instances.map((i) => i.name))
      )
    : [];

  return (
    <div className="dashboard-layout">
      <FilterPanel availableServices={services} />

      <main className="dashboard-main">
        {/* Toolbar */}
        <div className="toolbar">
          <div className="toolbar-left">
            {loading && <span className="loading-badge">⟳ Loading…</span>}
            {error && <span className="error-badge">⚠ {error}</span>}
            {!loading && !error && (
              <span className="updated-badge">Updated {lastUpdated}</span>
            )}
          </div>
          <div className="toolbar-right">
            <button className="export-btn" onClick={() => handleExport("csv")}>
              ↓ CSV
            </button>
            <button className="export-btn" onClick={() => handleExport("json")}>
              ↓ JSON
            </button>
            <button
              className="refresh-btn"
              onClick={load}
              title="Refresh now"
            >
              ⟳
            </button>
          </div>
        </div>

        {data && (
          <div className="grid">
            {/* Row 1 */}
            <SeverityCard data={data.severity} />
            <ServiceHealthCard
              data={data.service_health}
              onServiceClick={openServiceLogs}
            />
            <IncidentTimelineCard
              data={data.incidents}
              onIncidentClick={openIncidentLogs}
            />

            {/* Row 2 */}
            <BubbleChartCard
              data={data.bubbles}
              onBubbleClick={openServiceLogs}
            />
            <LatencyTrendCard data={data.latency} />
            <LogSourceCard data={data.log_sources} />
          </div>
        )}

        {!data && !loading && (
          <div className="empty-state full">No data available</div>
        )}
      </main>

      {drawerOpen && (
        <LogDrawer
          logs={drawerLogs}
          title={drawerTitle}
          onClose={() => setDrawerOpen(false)}
        />
      )}
    </div>
  );
}

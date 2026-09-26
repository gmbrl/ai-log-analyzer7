import { useStore } from "../store";
import type { Filters, Severity } from "../types";

const ALL_SEVERITIES: Severity[] = ["FATAL", "ERROR", "WARN", "INFO", "DEBUG"];
const ALL_INCIDENT_TYPES = [
  "Exceptions",
  "Timeouts",
  "Failed Auth",
  "OOM",
  "Connection Refused",
];

interface Props {
  availableServices: string[];
}

export default function FilterPanel({ availableServices }: Props) {
  const { filters, setFilters } = useStore();

  function toggleSeverity(s: Severity) {
    const next = filters.severities.includes(s)
      ? filters.severities.filter((x) => x !== s)
      : [...filters.severities, s];
    setFilters({ severities: next });
  }

  function toggleService(s: string) {
    const next = filters.services.includes(s)
      ? filters.services.filter((x) => x !== s)
      : [...filters.services, s];
    setFilters({ services: next });
  }

  function toggleIncidentType(t: string) {
    const next = filters.incident_types.includes(t)
      ? filters.incident_types.filter((x) => x !== t)
      : [...filters.incident_types, t];
    setFilters({ incident_types: next });
  }

  return (
    <aside className="filter-panel">
      <div className="filter-section">
        <div className="filter-label">TIME RANGE</div>
        <div className="filter-btns">
          {(["1h", "6h", "24h"] as Filters["time_range"][]).map((r) => (
            <button
              key={r}
              className={`filter-btn ${filters.time_range === r ? "active" : ""}`}
              onClick={() => setFilters({ time_range: r })}
            >
              {r}
            </button>
          ))}
          <button
            className={`filter-btn ${filters.time_range === "custom" ? "active" : ""}`}
            onClick={() => setFilters({ time_range: "custom" })}
          >
            Custom
          </button>
        </div>
        {filters.time_range === "custom" && (
          <div className="custom-range">
            <input
              type="datetime-local"
              className="range-input"
              value={filters.custom_from ?? ""}
              onChange={(e) => setFilters({ custom_from: e.target.value })}
            />
            <span style={{ color: "#aaa" }}>→</span>
            <input
              type="datetime-local"
              className="range-input"
              value={filters.custom_to ?? ""}
              onChange={(e) => setFilters({ custom_to: e.target.value })}
            />
          </div>
        )}
      </div>

      <div className="filter-section">
        <div className="filter-label">SEVERITY</div>
        {ALL_SEVERITIES.map((s) => (
          <label key={s} className="filter-check">
            <input
              type="checkbox"
              checked={filters.severities.includes(s)}
              onChange={() => toggleSeverity(s)}
            />
            <span>{s}</span>
          </label>
        ))}
      </div>

      {availableServices.length > 0 && (
        <div className="filter-section">
          <div className="filter-label">SERVICES</div>
          <label className="filter-check">
            <input
              type="checkbox"
              checked={filters.services.length === 0}
              onChange={() => setFilters({ services: [] })}
            />
            <span>All</span>
          </label>
          {availableServices.map((s) => (
            <label key={s} className="filter-check">
              <input
                type="checkbox"
                checked={filters.services.includes(s)}
                onChange={() => toggleService(s)}
              />
              <span>{s}</span>
            </label>
          ))}
        </div>
      )}

      <div className="filter-section">
        <div className="filter-label">INCIDENT TYPE</div>
        {ALL_INCIDENT_TYPES.map((t) => (
          <label key={t} className="filter-check">
            <input
              type="checkbox"
              checked={filters.incident_types.includes(t)}
              onChange={() => toggleIncidentType(t)}
            />
            <span>{t}</span>
          </label>
        ))}
      </div>

      <div className="filter-section">
        <label className="filter-check">
          <input
            type="checkbox"
            checked={filters.auto_refresh}
            onChange={(e) => setFilters({ auto_refresh: e.target.checked })}
          />
          <span>Auto-refresh (30s)</span>
        </label>
      </div>
    </aside>
  );
}

import { useState } from "react";
import type { LogEntry } from "../types";

interface Props {
  logs: LogEntry[];
  title: string;
  onClose: () => void;
}

const LEVEL_COLOR: Record<string, string> = {
  FATAL: "#FF0000",
  ERROR: "#FF4444",
  WARN: "#FF9500",
  INFO: "#aaa",
  DEBUG: "#666",
};

export default function LogDrawer({ logs, title, onClose }: Props) {
  const [search, setSearch] = useState("");
  const filtered = search
    ? logs.filter(
        (l) =>
          l.message.toLowerCase().includes(search.toLowerCase()) ||
          l.source.toLowerCase().includes(search.toLowerCase())
      )
    : logs;

  return (
    <div className="drawer-overlay" onClick={onClose}>
      <div className="drawer" onClick={(e) => e.stopPropagation()}>
        <div className="drawer-header">
          <span className="drawer-title">{title}</span>
          <input
            className="drawer-search"
            placeholder="Filter logs…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
          <button className="drawer-close" onClick={onClose}>
            ✕
          </button>
        </div>
        <div className="drawer-body">
          {filtered.length === 0 && (
            <div className="empty-state">No logs found</div>
          )}
          {filtered.map((l, i) => (
            <div key={i} className="log-row">
              <span className="log-ts">{l.timestamp}</span>
              <span
                className="log-level"
                style={{ color: LEVEL_COLOR[l.level] ?? "#aaa" }}
              >
                {l.level}
              </span>
              <span className="log-source">{l.source}</span>
              <span className="log-msg">{l.message}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

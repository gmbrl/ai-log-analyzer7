import { useState } from "react";
import type { IncidentBar } from "../types";
import Card from "./Card";

const SEV_COLOR: Record<string, string> = {
  FATAL: "#FF0000",
  ERROR: "#FF4444",
  WARN: "#FF9500",
  INFO: "#7FFF00",
  DEBUG: "#999999",
};

interface TooltipState {
  bar: IncidentBar;
  x: number;
  y: number;
}

interface Props {
  data: IncidentBar[];
  onIncidentClick?: (bar: IncidentBar) => void;
}

export default function IncidentTimelineCard({ data, onIncidentClick }: Props) {
  const [tip, setTip] = useState<TooltipState | null>(null);

  if (!data.length) {
    return (
      <Card title="INCIDENT TIMELINE" className="card-tall">
        <div className="empty-state">No incidents in range</div>
      </Card>
    );
  }

  const maxCount = Math.max(...data.map((d) => d.log_count), 1);

  return (
    <Card title="INCIDENT TIMELINE" className="card-tall">
      <div className="timeline-container">
        {data.map((bar, i) => {
          const widthPct = (bar.log_count / maxCount) * 100;
          return (
            <div key={i} className="timeline-row">
              <span className="timeline-time">{bar.time}</span>
              <div className="timeline-bar-wrap">
                <button
                  className="timeline-bar"
                  style={{
                    width: `${widthPct}%`,
                    background: SEV_COLOR[bar.severity] ?? "#555",
                    minWidth: 4,
                  }}
                  onClick={() => onIncidentClick?.(bar)}
                  onMouseEnter={(e) => {
                    const rect = (
                      e.currentTarget as HTMLElement
                    ).getBoundingClientRect();
                    setTip({ bar, x: rect.right, y: rect.top });
                  }}
                  onMouseLeave={() => setTip(null)}
                >
                  <span className="timeline-bar-label">
                    {bar.service} · {bar.log_count} logs ·{" "}
                    {bar.affected_instances} inst
                  </span>
                </button>
              </div>
            </div>
          );
        })}
      </div>
      {tip && (
        <div
          className="tooltip"
          style={{ left: tip.x + 8, top: tip.y }}
        >
          <div className="tooltip-title">
            [{tip.bar.severity}] {tip.bar.service}
          </div>
          <div>Time: {tip.bar.time}</div>
          <div>Logs: {tip.bar.log_count}</div>
          <div>Instances affected: {tip.bar.affected_instances}</div>
          <div className="tooltip-msg">{tip.bar.sample_message}</div>
        </div>
      )}
    </Card>
  );
}

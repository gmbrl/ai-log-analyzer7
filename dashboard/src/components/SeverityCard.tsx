import type { SeverityCount } from "../types";
import Card from "./Card";

function MiniSparkline({ data, color }: { data: number[]; color: string }) {
  if (!data.length) return null;
  const max = Math.max(...data, 1);
  const min = Math.min(...data, 0);
  const range = max - min || 1;
  const w = 60,
    h = 20;
  const pts = data
    .map((v, i) => {
      const x = (i / (data.length - 1)) * w;
      const y = h - ((v - min) / range) * h;
      return `${x},${y}`;
    })
    .join(" ");
  return (
    <svg width={w} height={h} style={{ overflow: "visible" }}>
      <polyline
        points={pts}
        fill="none"
        stroke={color}
        strokeWidth={1}
        strokeLinejoin="round"
      />
    </svg>
  );
}

const SEV_CONFIG: Record<
  string,
  { color: string; bg: string; label: string }
> = {
  ERROR: { color: "#FF4444", bg: "rgba(255,68,68,0.12)", label: "ERROR" },
  WARN: { color: "#FF9500", bg: "rgba(255,149,0,0.12)", label: "WARN" },
  INFO: { color: "#999999", bg: "rgba(153,153,153,0.12)", label: "INFO" },
  FATAL: {
    color: "#FF0000",
    bg: "rgba(255,0,0,0.18)",
    label: "FATAL",
  },
};

interface Props {
  data: SeverityCount[];
}

export default function SeverityCard({ data }: Props) {
  const order = ["ERROR", "WARN", "INFO", "FATAL"];
  const displayed = order
    .map((lv) => data.find((d) => d.level === lv))
    .filter(Boolean) as SeverityCount[];

  return (
    <Card title="LOG SEVERITY">
      <div className="sev-grid">
        {displayed.map((d) => {
          const cfg = SEV_CONFIG[d.level] ?? {
            color: "#999",
            bg: "rgba(153,153,153,0.12)",
            label: d.level,
          };
          const up = d.delta_pct >= 0;
          return (
            <div
              key={d.level}
              className="sev-cell"
              style={{ background: cfg.bg }}
            >
              <div className="sev-label" style={{ color: cfg.color }}>
                {cfg.label}
              </div>
              <div className="sev-count">{d.count.toLocaleString()}</div>
              <div className="sev-footer">
                <span
                  className="sev-delta"
                  style={{ color: up ? "#FF4444" : "#7FFF00" }}
                >
                  {up ? "▲" : "▼"} {Math.abs(d.delta_pct).toFixed(1)}%
                </span>
                {d.sparkline?.length > 1 && (
                  <MiniSparkline data={d.sparkline} color={cfg.color} />
                )}
              </div>
            </div>
          );
        })}
      </div>
    </Card>
  );
}

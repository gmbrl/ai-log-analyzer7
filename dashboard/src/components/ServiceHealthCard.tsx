import type { ServiceHealth } from "../types";
import Card from "./Card";

const STATUS_COLOR: Record<string, string> = {
  healthy: "#7FFF00",
  degraded: "#FF9500",
  failed: "#FF4444",
};

interface Props {
  data: ServiceHealth;
  onServiceClick?: (name: string) => void;
}

export default function ServiceHealthCard({ data, onServiceClick }: Props) {
  return (
    <Card title="SERVICES">
      <div className="service-summary">
        <span style={{ color: "#7FFF00" }}>{data.healthy} healthy</span>
        <span className="sep">·</span>
        <span style={{ color: "#FF9500" }}>{data.degraded} degraded</span>
        <span className="sep">·</span>
        <span style={{ color: "#FF4444" }}>{data.failed} failed</span>
        <span className="sep">·</span>
        <span style={{ color: "#aaa" }}>{data.total} total</span>
      </div>
      <div className="dot-matrix">
        {data.instances.map((inst) => (
          <button
            key={inst.id}
            className="dot-btn"
            title={`${inst.name}\nStatus: ${inst.status}\nResponse: ${inst.response_time_ms}ms`}
            style={{ background: STATUS_COLOR[inst.status] ?? "#555" }}
            onClick={() => onServiceClick?.(inst.name)}
          />
        ))}
      </div>
      <div className="service-legend">
        {(["healthy", "degraded", "failed"] as const).map((s) => (
          <span key={s} className="legend-item">
            <span
              className="legend-dot"
              style={{ background: STATUS_COLOR[s] }}
            />
            {s}
          </span>
        ))}
      </div>
    </Card>
  );
}

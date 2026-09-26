import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
  ReferenceLine,
} from "recharts";
import type { LatencyPoint } from "../types";
import Card from "./Card";

interface Props {
  data: LatencyPoint[];
}

const LINES = [
  { key: "api_avg", name: "API avg", color: "#7FFF00", dash: "" },
  { key: "api_p95", name: "API p95", color: "#7FFF00", dash: "4 2" },
  { key: "api_p99", name: "API p99", color: "#7FFF00", dash: "2 2" },
  { key: "worker_avg", name: "Worker avg", color: "#FF9500", dash: "" },
  { key: "worker_p95", name: "Worker p95", color: "#FF9500", dash: "4 2" },
  { key: "db_avg", name: "DB avg", color: "#FF4444", dash: "" },
  { key: "db_p95", name: "DB p95", color: "#FF4444", dash: "4 2" },
] as const;

interface CustomTooltipProps {
  active?: boolean;
  label?: string;
  payload?: Array<{ name: string; value: number; color: string }>;
}

function CustomTooltip({ active, label, payload }: CustomTooltipProps) {
  if (!active || !payload?.length) return null;
  return (
    <div className="tooltip">
      <div className="tooltip-title">{label}</div>
      {payload.map((p) => (
        <div key={p.name} style={{ color: p.color }}>
          {p.name}: {p.value}ms
        </div>
      ))}
    </div>
  );
}

export default function LatencyTrendCard({ data }: Props) {
  return (
    <Card title="RESPONSE TIME TREND">
      <ResponsiveContainer width="100%" height={240}>
        <LineChart data={data} margin={{ top: 10, right: 20, bottom: 20, left: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#333" />
          <XAxis
            dataKey="time"
            tick={{ fill: "#aaa", fontSize: 11, fontFamily: "monospace" }}
            tickLine={false}
            axisLine={{ stroke: "#444" }}
          />
          <YAxis
            tick={{ fill: "#aaa", fontSize: 11 }}
            tickLine={false}
            axisLine={{ stroke: "#444" }}
            tickFormatter={(v) => `${v}ms`}
          />
          <Tooltip content={<CustomTooltip />} />
          <Legend
            wrapperStyle={{ color: "#aaa", fontSize: 11 }}
          />
          <ReferenceLine y={500} stroke="#FF4444" strokeDasharray="6 3" label={{ value: "SLO", fill: "#FF4444", fontSize: 10 }} />
          {LINES.map((l) => (
            <Line
              key={l.key}
              type="monotone"
              dataKey={l.key}
              name={l.name}
              stroke={l.color}
              strokeWidth={1}
              strokeDasharray={l.dash || undefined}
              dot={false}
              activeDot={{ r: 3 }}
            />
          ))}
        </LineChart>
      </ResponsiveContainer>
    </Card>
  );
}

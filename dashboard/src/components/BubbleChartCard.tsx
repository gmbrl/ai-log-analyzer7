import {
  ScatterChart,
  Scatter,
  XAxis,
  YAxis,
  ZAxis,
  Tooltip,
  ResponsiveContainer,
} from "recharts";
import type { BubblePoint } from "../types";
import Card from "./Card";

const STATUS_COLOR: Record<string, string> = {
  critical: "#FF4444",
  warning: "#FF9500",
  healthy: "#555555",
};

interface CustomDotProps {
  cx?: number;
  cy?: number;
  r?: number;
  payload?: BubblePoint;
  onClick?: (p: BubblePoint) => void;
}

function CustomDot({ cx = 0, cy = 0, r = 10, payload, onClick }: CustomDotProps) {
  if (!payload) return null;
  const color = STATUS_COLOR[payload.status] ?? "#555";
  return (
    <g
      style={{ cursor: "pointer" }}
      onClick={() => onClick?.(payload)}
    >
      <circle cx={cx} cy={cy} r={r} fill={color} fillOpacity={0.75} stroke={color} strokeWidth={1} />
      <text x={cx} y={cy + 4} textAnchor="middle" fill="#fff" fontSize={10} fontFamily="monospace">
        {payload.error_count}
      </text>
    </g>
  );
}

interface TooltipProps {
  active?: boolean;
  payload?: Array<{ payload: BubblePoint }>;
}

function BubbleTooltip({ active, payload }: TooltipProps) {
  if (!active || !payload?.length) return null;
  const d = payload[0].payload;
  return (
    <div className="tooltip">
      <div className="tooltip-title">{d.service}</div>
      <div>Error rate: {d.error_rate.toFixed(2)}%</div>
      <div>Log volume: {d.log_volume.toLocaleString()}</div>
      <div>Errors: {d.error_count}</div>
      {d.sample_stack && (
        <pre className="tooltip-stack">{d.sample_stack}</pre>
      )}
    </div>
  );
}

interface Props {
  data: BubblePoint[];
  onBubbleClick?: (service: string) => void;
}

export default function BubbleChartCard({ data, onBubbleClick }: Props) {
  return (
    <Card title="ERROR DISTRIBUTION">
      <ResponsiveContainer width="100%" height={240}>
        <ScatterChart margin={{ top: 10, right: 20, bottom: 20, left: 0 }}>
          <XAxis
            dataKey="service"
            type="category"
            name="Service"
            tick={{ fill: "#aaa", fontSize: 11, fontFamily: "monospace" }}
            tickLine={false}
            axisLine={{ stroke: "#444" }}
          />
          <YAxis
            dataKey="error_rate"
            name="Error Rate %"
            tick={{ fill: "#aaa", fontSize: 11 }}
            tickLine={false}
            axisLine={{ stroke: "#444" }}
            tickFormatter={(v) => `${v}%`}
          />
          <ZAxis dataKey="log_volume" range={[200, 1400]} name="Log Volume" />
          <Tooltip content={<BubbleTooltip />} />
          <Scatter data={data} shape={(p: CustomDotProps) => (
            <CustomDot
              {...p}
              onClick={(bp) => onBubbleClick?.(bp.service)}
            />
          )} />
        </ScatterChart>
      </ResponsiveContainer>
    </Card>
  );
}

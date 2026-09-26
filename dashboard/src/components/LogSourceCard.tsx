import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from "recharts";
import type { LogSourceBucket } from "../types";
import Card from "./Card";

interface Props {
  data: LogSourceBucket[];
}

export default function LogSourceCard({ data }: Props) {
  return (
    <Card title="LOG SOURCE BREAKDOWN">
      <ResponsiveContainer width="100%" height={200}>
        <BarChart
          layout="vertical"
          data={data}
          margin={{ top: 5, right: 20, bottom: 5, left: 10 }}
        >
          <CartesianGrid strokeDasharray="3 3" stroke="#333" horizontal={false} />
          <XAxis
            type="number"
            tick={{ fill: "#aaa", fontSize: 11 }}
            tickLine={false}
            axisLine={{ stroke: "#444" }}
          />
          <YAxis
            dataKey="source"
            type="category"
            tick={{ fill: "#aaa", fontSize: 11, fontFamily: "monospace" }}
            tickLine={false}
            axisLine={{ stroke: "#444" }}
            width={90}
          />
          <Tooltip
            contentStyle={{ background: "#1e1e1e", border: "1px solid #444", color: "#eee", fontSize: 12 }}
          />
          <Legend wrapperStyle={{ color: "#aaa", fontSize: 11 }} />
          <Bar dataKey="info" name="INFO" stackId="a" fill="#555555" />
          <Bar dataKey="warn" name="WARN" stackId="a" fill="#FF9500" />
          <Bar dataKey="error" name="ERROR" stackId="a" fill="#FF4444" />
          <Bar dataKey="fatal" name="FATAL" stackId="a" fill="#FF0000" />
        </BarChart>
      </ResponsiveContainer>
    </Card>
  );
}

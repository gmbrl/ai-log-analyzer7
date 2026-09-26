export type Severity = "FATAL" | "ERROR" | "WARN" | "INFO" | "DEBUG";

export interface SeverityCount {
  level: Severity;
  count: number;
  delta_pct: number; // % change from previous window
  sparkline: number[]; // last N buckets
}

export interface ServiceInstance {
  id: string;
  name: string;
  status: "healthy" | "degraded" | "failed";
  response_time_ms: number;
}

export interface ServiceHealth {
  instances: ServiceInstance[];
  healthy: number;
  degraded: number;
  failed: number;
  total: number;
}

export interface IncidentBar {
  time: string; // "HH:MM"
  timestamp_unix: number;
  service: string;
  severity: Severity;
  log_count: number;
  affected_instances: number;
  sample_message: string;
}

export interface BubblePoint {
  service: string;
  error_rate: number; // 0-100
  log_volume: number;
  error_count: number;
  status: "critical" | "warning" | "healthy";
  sample_stack?: string;
}

export interface LatencyPoint {
  time: string;
  api_avg: number;
  api_p95: number;
  api_p99: number;
  worker_avg: number;
  worker_p95: number;
  worker_p99: number;
  db_avg: number;
  db_p95: number;
  db_p99: number;
}

export interface LogSourceBucket {
  source: string;
  info: number;
  warn: number;
  error: number;
  fatal: number;
}

export interface DashboardData {
  severity: SeverityCount[];
  service_health: ServiceHealth;
  incidents: IncidentBar[];
  bubbles: BubblePoint[];
  latency: LatencyPoint[];
  log_sources: LogSourceBucket[];
  last_updated: string; // ISO
}

export interface Filters {
  time_range: "1h" | "6h" | "24h" | "custom";
  custom_from?: string;
  custom_to?: string;
  services: string[]; // empty = all
  severities: Severity[];
  incident_types: string[];
  auto_refresh: boolean;
}

export interface LogEntry {
  timestamp: string;
  level: Severity;
  source: string;
  message: string;
  raw: string;
}

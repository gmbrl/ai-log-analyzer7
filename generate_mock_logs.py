"""
generate_mock_logs.py — Realistic mock log generator for testing.

Generates a mixed log file containing multiple realistic failure scenarios:
  1. Database connection pool exhaustion → cascading 500 errors
  2. Auth brute-force attack (burst of 401 responses)
  3. Memory pressure + GC pause → latency spikes
  4. Downstream microservice timeout (circuit breaker trip)
  5. Disk I/O error on log rotation
  6. Recovery / healthy period

The generated file includes realistic PII (emails, IPs, tokens) so the
PII redaction pipeline can be exercised.

Usage:
    python generate_mock_logs.py                        # writes sample_logs/mock_app.log
    python generate_mock_logs.py --lines 2000 --out my.log
"""

import argparse
import random
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

# ---------------------------------------------------------------------------
# Seed for reproducibility (override via --seed)
# ---------------------------------------------------------------------------
SEED = 42

# ---------------------------------------------------------------------------
# Realistic data pools
# ---------------------------------------------------------------------------

HOSTS = ["web-01", "web-02", "api-gw", "worker-01", "worker-02", "cron-01"]
SERVICES = [
    "com.acme.PaymentService",
    "com.acme.UserService",
    "com.acme.OrderService",
    "com.acme.NotificationService",
    "com.acme.ReportingService",
    "com.acme.AuthService",
    "nginx",
    "postgres-pool",
    "redis-cache",
]
THREADS = [f"http-nio-8080-exec-{i}" for i in range(1, 9)] + ["scheduled-task-1", "worker-pool-3"]
USERS = ["alice@example.com", "bob@company.org", "charlie@test.io", "dave@corp.net"]
IPS = [
    "10.0.1.15", "10.0.1.22", "192.168.100.5",
    # Attacker IPs (will appear in brute-force scenario)
    "185.220.101.47", "104.21.56.88", "45.142.212.100", "91.108.4.0",
]
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "python-httpx/0.27.0",
    "curl/8.4.0",
    "Go-http-client/1.1",
]
BEARER_TOKENS = [
    "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJ1c2VyXzEyMyJ9.SIGNATURE",
    "sk-prod-ABCDEFGHIJKLMNOP1234567890",
]
API_KEYS = ["api_key=xK9mN2pQ8rS5tV3wY7zA1bC4dE6fG0hI", "X-API-Key: PROD-SECRET-KEY-48291XYZ"]

# ---------------------------------------------------------------------------
# Helper: Spring Boot log-line builder
# ---------------------------------------------------------------------------

def _spring_line(ts: datetime, level: str, service: str, msg: str, thread: str | None = None) -> str:
    pid = 12345
    t = thread or random.choice(THREADS)
    ts_str = ts.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    return f"{ts_str}  {level:<5} {pid} --- [{t:<28}] {service:<40} : {msg}"


def _nginx_line(ts: datetime, ip: str, path: str, status: int, size: int = 512) -> str:
    ts_str = ts.strftime("%d/%b/%Y:%H:%M:%S +0000")
    ua = random.choice(USER_AGENTS)
    return f'{ip} - - [{ts_str}] "GET {path} HTTP/1.1" {status} {size} "-" "{ua}"'


def _syslog_line(ts: datetime, host: str, proc: str, msg: str) -> str:
    ts_str = ts.strftime("%b %d %H:%M:%S")
    return f"{ts_str} {host} {proc}: {msg}"


# ---------------------------------------------------------------------------
# Scenario generators
# ---------------------------------------------------------------------------

def _healthy_period(start: datetime, n: int) -> list[str]:
    """Normal healthy traffic."""
    lines = []
    t = start
    paths = ["/api/v1/orders", "/api/v1/users/me", "/health", "/metrics", "/api/v1/products"]
    for _ in range(n):
        t += timedelta(seconds=random.uniform(0.1, 2.0))
        ip = random.choice(IPS[:3])
        path = random.choice(paths)
        service = random.choice(SERVICES[:5])

        if random.random() < 0.7:
            lines.append(_nginx_line(t, ip, path, 200, random.randint(200, 5000)))
        if random.random() < 0.5:
            lines.append(_spring_line(t, "INFO", service, f"Request processed in {random.randint(15, 120)}ms"))
        if random.random() < 0.1:
            lines.append(_spring_line(t, "DEBUG", service, f"Cache hit for key=user:{random.randint(1000,9999)}"))
    return lines


def _db_pool_exhaustion(start: datetime, n: int) -> list[str]:
    """Simulates HikariCP connection pool exhaustion cascade."""
    lines = []
    t = start
    service = "com.acme.PaymentService"
    pool_svc = "postgres-pool"

    lines.append(_spring_line(t, "WARN", pool_svc,
        "HikariPool-1 - Connection is not available, request timed out after 30000ms"))
    t += timedelta(seconds=0.5)

    for i in range(n):
        t += timedelta(seconds=random.uniform(0.05, 0.3))
        if i < 3:
            lines.append(_spring_line(t, "WARN", pool_svc,
                f"HikariPool-1 - Pool stats (total=10, active=10, idle=0, waiting={i+1})"))
        lines.append(_spring_line(t, "ERROR", service,
            "org.postgresql.util.PSQLException: FATAL: remaining connection slots are reserved"))
        lines.append(_spring_line(t, "ERROR", service,
            "Failed to process payment for order_id=ORD-{:06d}: DB unavailable".format(random.randint(1000, 9999))))
        # Cascading 500s
        ip = random.choice(IPS[:3])
        lines.append(_nginx_line(t, ip, "/api/v1/payments", 500))

    t += timedelta(seconds=5)
    lines.append(_spring_line(t, "ERROR", service,
        f"java.sql.SQLException: Timeout waiting for connection from pool after 30000ms "
        f"[user: admin@payments-db.internal, password: Sup3rS3cretDB!]"))
    t += timedelta(seconds=2)
    lines.append(_spring_line(t, "INFO", pool_svc,
        "HikariPool-1 - Connection pool size increased to 20"))
    t += timedelta(seconds=10)
    lines.append(_spring_line(t, "INFO", service, "Connection pool recovered. Resuming normal operations."))
    return lines


def _auth_brute_force(start: datetime, n: int) -> list[str]:
    """Simulates a burst of failed authentication attempts from rogue IPs."""
    lines = []
    t = start
    attacker_ips = IPS[3:]   # last 4 are "attacker" IPs
    service = "com.acme.AuthService"

    lines.append(_spring_line(t, "WARN", service,
        "Unusual authentication failure rate detected: 15 failures in last 30s"))
    t += timedelta(seconds=0.2)

    for i in range(n):
        t += timedelta(seconds=random.uniform(0.05, 0.5))
        ip = random.choice(attacker_ips)
        user = random.choice(["admin", "root", "administrator", "superuser"])
        bearer = random.choice(BEARER_TOKENS)
        lines.append(_nginx_line(t, ip, f"/api/v1/auth/login", 401))
        lines.append(_spring_line(t, "WARN", service,
            f"Authentication failed for user='{user}' from IP={ip}. "
            f"Attempt {random.randint(2,20)}/20. Token: {bearer}"))
        if i == n // 2:
            lines.append(_spring_line(t, "ERROR", service,
                f"SECURITY ALERT: Possible brute-force attack from {ip}. "
                f"Blocking IP. Contact: security@example.com"))

    t += timedelta(seconds=2)
    lines.append(_spring_line(t, "WARN", service,
        f"Rate limiting activated for IPs: {', '.join(attacker_ips)}"))
    return lines


def _memory_pressure(start: datetime, n: int) -> list[str]:
    """Simulates memory pressure, GC pauses, and latency spikes."""
    lines = []
    t = start
    service = "com.acme.OrderService"

    lines.append(_syslog_line(t, "worker-01", "java",
        "GC overhead limit exceeded: pause 4823ms, heap=95% of 4096MB"))
    t += timedelta(seconds=1)

    for i in range(n):
        t += timedelta(seconds=random.uniform(0.2, 1.0))
        used_mb = random.randint(3500, 4090)
        lines.append(_spring_line(t, "WARN", service,
            f"Slow response detected: {random.randint(3000, 12000)}ms (threshold=500ms)"))
        if random.random() < 0.4:
            lines.append(_spring_line(t, "ERROR", service,
                f"java.lang.OutOfMemoryError: Java heap space (used={used_mb}MB/4096MB)"))
        lines.append(_syslog_line(t, "worker-01", "kernel",
            f"[OOM] process 'java' ({random.randint(10000,19999)}) oom_score={random.randint(800,999)}"))

    t += timedelta(seconds=30)
    lines.append(_spring_line(t, "INFO", service, "JVM restarted. Heap usage reset to 512MB/4096MB"))
    return lines


def _circuit_breaker(start: datetime, n: int) -> list[str]:
    """Simulates downstream service timeout and circuit breaker opening."""
    lines = []
    t = start
    service = "com.acme.NotificationService"

    for i in range(n):
        t += timedelta(seconds=random.uniform(0.3, 1.5))
        lines.append(_spring_line(t, "WARN", service,
            f"Downstream call to sms-gateway timed out after 5000ms (attempt {i+1}/{n})"))

    t += timedelta(seconds=1)
    lines.append(_spring_line(t, "ERROR", service,
        "CircuitBreaker 'sms-gateway' is OPEN. Calls will be rejected for next 60s."))
    lines.append(_spring_line(t, "ERROR", service,
        f"io.github.resilience4j.circuitbreaker.CallNotPermittedException: "
        f"CircuitBreaker 'sms-gateway' is OPEN and does not permit further calls"))

    t += timedelta(seconds=60)
    lines.append(_spring_line(t, "INFO", service,
        "CircuitBreaker 'sms-gateway' changed state from OPEN to HALF_OPEN"))
    t += timedelta(seconds=10)
    lines.append(_spring_line(t, "INFO", service,
        "CircuitBreaker 'sms-gateway' changed state from HALF_OPEN to CLOSED. Service recovered."))
    return lines


def _disk_io_error(start: datetime) -> list[str]:
    """Simulates disk I/O error during log rotation."""
    lines = []
    t = start
    host = "cron-01"

    lines.append(_syslog_line(t, host, "logrotate",
        "error: error running shared postrotate script for /var/log/app/*.log"))
    t += timedelta(seconds=1)
    lines.append(_syslog_line(t, host, "kernel",
        "EXT4-fs error (device sda1): ext4_journal_check_start: Detected aborted journal"))
    t += timedelta(seconds=2)
    lines.append(_syslog_line(t, host, "systemd",
        "app-logger.service: Failed with result 'exit-code'. Restarting in 5s."))
    t += timedelta(seconds=5)
    lines.append(_syslog_line(t, host, "systemd",
        "app-logger.service: Started successfully after disk recovered."))
    return lines


def _pii_sample(start: datetime) -> list[str]:
    """A few lines containing PII to exercise the redaction pipeline."""
    t = start
    lines = [
        _spring_line(t, "ERROR", "com.acme.UserService",
            f"Failed to send verification email to alice@example.com from noreply@company.com"),
        _spring_line(t + timedelta(seconds=1), "WARN", "com.acme.PaymentService",
            f"Payment declined for card 4532015112830366 (exp 12/26). User: bob@company.org"),
        _spring_line(t + timedelta(seconds=2), "DEBUG", "com.acme.AuthService",
            f"Refreshing token for user. Authorization: Bearer eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJ1c2VyXzEyMyJ9.SIGNATURE"),
        _spring_line(t + timedelta(seconds=3), "ERROR", "com.acme.ReportingService",
            f"DB connect error: postgresql://admin:Sup3rS3cret@db.internal:5432/prod"),
        _spring_line(t + timedelta(seconds=4), "INFO", "com.acme.UserService",
            f"SSN validation failed for user 123-45-6789 — rejecting registration"),
    ]
    return lines


# ---------------------------------------------------------------------------
# Main assembler
# ---------------------------------------------------------------------------

def generate(total_target_lines: int = 1000, seed: int = SEED) -> list[str]:
    """
    Assemble a realistic mixed log stream.

    Args:
        total_target_lines: Approximate total line count.
        seed:               Random seed for reproducibility.

    Returns:
        List of log line strings (unsorted within scenarios, ordered by scenario time).
    """
    random.seed(seed)
    all_lines: list[str] = []

    base_time = datetime(2024, 6, 15, 10, 0, 0, tzinfo=timezone.utc)
    t = base_time

    # 1. Healthy warm-up (~20% of budget)
    warm_lines = max(50, int(total_target_lines * 0.20))
    all_lines.extend(_healthy_period(t, warm_lines))
    t += timedelta(minutes=15)

    # 2. DB pool exhaustion (~20%)
    db_lines = max(20, int(total_target_lines * 0.20))
    all_lines.extend(_db_pool_exhaustion(t, db_lines))
    t += timedelta(minutes=5)

    # 3. PII sample lines
    all_lines.extend(_pii_sample(t))
    t += timedelta(minutes=1)

    # 4. Auth brute-force (~15%)
    auth_lines = max(15, int(total_target_lines * 0.15))
    all_lines.extend(_auth_brute_force(t, auth_lines))
    t += timedelta(minutes=3)

    # 5. Healthy middle period (~10%)
    mid_lines = max(30, int(total_target_lines * 0.10))
    all_lines.extend(_healthy_period(t, mid_lines))
    t += timedelta(minutes=8)

    # 6. Memory pressure (~15%)
    mem_lines = max(15, int(total_target_lines * 0.15))
    all_lines.extend(_memory_pressure(t, mem_lines))
    t += timedelta(minutes=10)

    # 7. Circuit breaker (~10%)
    cb_lines = max(10, int(total_target_lines * 0.10))
    all_lines.extend(_circuit_breaker(t, cb_lines))
    t += timedelta(minutes=2)

    # 8. Disk I/O error
    all_lines.extend(_disk_io_error(t))
    t += timedelta(minutes=5)

    # 9. Recovery / healthy tail (~10%)
    tail_lines = max(30, int(total_target_lines * 0.10))
    all_lines.extend(_healthy_period(t, tail_lines))

    return all_lines


# ---------------------------------------------------------------------------
# CLI entry-point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Generate realistic mock logs for AI Log Analyzer testing."
    )
    parser.add_argument(
        "--lines",
        type=int,
        default=1000,
        help="Approximate total line count (default: 1000)",
    )
    parser.add_argument(
        "--out",
        type=str,
        default="sample_logs/mock_app.log",
        help="Output file path (default: sample_logs/mock_app.log)",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=SEED,
        help=f"Random seed for reproducibility (default: {SEED})",
    )
    args = parser.parse_args()

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    print(f"Generating ~{args.lines} log lines (seed={args.seed})…")
    lines = generate(total_target_lines=args.lines, seed=args.seed)

    with open(out_path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")

    print(f"[OK] Written {len(lines)} lines to {out_path}")
    print(
        "\nScenarios included:\n"
        "  - Healthy traffic (warm-up, middle, tail)\n"
        "  - Database connection pool exhaustion -> 500 errors\n"
        "  - Auth brute-force attack (401 burst)\n"
        "  - Memory pressure + OOM / GC pauses\n"
        "  - Downstream service timeout + circuit breaker\n"
        "  - Disk I/O error during log rotation\n"
        "  - PII data (emails, CC numbers, tokens, passwords, SSN)\n"
    )

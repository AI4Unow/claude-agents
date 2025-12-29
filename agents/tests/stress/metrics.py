"""Custom metrics collection for stress tests."""

import time
import statistics
from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional
from collections import defaultdict


@dataclass
class MetricsCollector:
    """Collects and aggregates test metrics."""

    latencies: List[float] = field(default_factory=list)
    errors: Dict[str, int] = field(default_factory=lambda: defaultdict(int))
    status_codes: Dict[int, int] = field(default_factory=lambda: defaultdict(int))
    circuit_trips: Dict[str, int] = field(default_factory=lambda: defaultdict(int))
    start_time: float = field(default_factory=time.time)
    _max_latencies: int = 100_000  # Cap to prevent memory issues

    def record_request(
        self,
        latency_ms: float,
        success: bool,
        status_code: int = 200,
        error_type: str = None,
    ):
        """Record a single request result."""
        # Cap latencies to prevent memory growth
        if len(self.latencies) < self._max_latencies:
            self.latencies.append(latency_ms)

        self.status_codes[status_code] += 1

        if not success and error_type:
            self.errors[error_type] += 1

    def record_circuit_trip(self, circuit_name: str):
        """Record a circuit breaker trip."""
        self.circuit_trips[circuit_name] += 1

    def percentile(self, p: int) -> float:
        """Get latency percentile (p50, p95, p99)."""
        if not self.latencies:
            return 0.0
        sorted_latencies = sorted(self.latencies)
        idx = int(len(sorted_latencies) * p / 100)
        return sorted_latencies[min(idx, len(sorted_latencies) - 1)]

    @property
    def p50(self) -> float:
        """50th percentile latency."""
        return self.percentile(50)

    @property
    def p95(self) -> float:
        """95th percentile latency."""
        return self.percentile(95)

    @property
    def p99(self) -> float:
        """99th percentile latency."""
        return self.percentile(99)

    @property
    def min_latency(self) -> float:
        """Minimum latency."""
        return min(self.latencies) if self.latencies else 0.0

    @property
    def max_latency(self) -> float:
        """Maximum latency."""
        return max(self.latencies) if self.latencies else 0.0

    @property
    def mean_latency(self) -> float:
        """Mean latency."""
        return statistics.mean(self.latencies) if self.latencies else 0.0

    @property
    def total_requests(self) -> int:
        """Total number of requests recorded."""
        return sum(self.status_codes.values())

    @property
    def total_errors(self) -> int:
        """Total number of errors."""
        return sum(self.errors.values())

    @property
    def error_rate(self) -> float:
        """Error rate as fraction (0.0 - 1.0)."""
        total = self.total_requests
        return self.total_errors / total if total > 0 else 0.0

    @property
    def duration_seconds(self) -> float:
        """Test duration in seconds."""
        return time.time() - self.start_time

    @property
    def throughput(self) -> float:
        """Requests per second."""
        duration = self.duration_seconds
        return self.total_requests / duration if duration > 0 else 0.0

    def reset(self):
        """Reset all metrics."""
        self.latencies.clear()
        self.errors.clear()
        self.status_codes.clear()
        self.circuit_trips.clear()
        self.start_time = time.time()

    def to_report(self) -> Dict[str, Any]:
        """Generate report dictionary."""
        return {
            "summary": {
                "total_requests": self.total_requests,
                "total_errors": self.total_errors,
                "duration_seconds": round(self.duration_seconds, 2),
                "throughput_rps": round(self.throughput, 2),
                "error_rate_percent": round(self.error_rate * 100, 2),
            },
            "latency_ms": {
                "min": round(self.min_latency, 2),
                "mean": round(self.mean_latency, 2),
                "p50": round(self.p50, 2),
                "p95": round(self.p95, 2),
                "p99": round(self.p99, 2),
                "max": round(self.max_latency, 2),
            },
            "status_codes": dict(self.status_codes),
            "errors": dict(self.errors),
            "circuit_trips": dict(self.circuit_trips),
        }

    def print_summary(self):
        """Print human-readable summary."""
        report = self.to_report()
        print("\n" + "=" * 50)
        print("STRESS TEST RESULTS")
        print("=" * 50)

        print(f"\nRequests: {report['summary']['total_requests']}")
        print(f"Duration: {report['summary']['duration_seconds']}s")
        print(f"Throughput: {report['summary']['throughput_rps']} req/s")
        print(f"Error Rate: {report['summary']['error_rate_percent']}%")

        print(f"\nLatency (ms):")
        lat = report['latency_ms']
        print(f"  Min: {lat['min']}, Mean: {lat['mean']}, Max: {lat['max']}")
        print(f"  p50: {lat['p50']}, p95: {lat['p95']}, p99: {lat['p99']}")

        if report['status_codes']:
            print(f"\nStatus Codes: {dict(report['status_codes'])}")

        if report['errors']:
            print(f"\nErrors: {dict(report['errors'])}")

        if report['circuit_trips']:
            print(f"\nCircuit Trips: {dict(report['circuit_trips'])}")

        print("=" * 50 + "\n")


# Global collector instance
collector = MetricsCollector()


def check_thresholds(report: Dict[str, Any], config) -> List[str]:
    """Check if metrics meet configured thresholds. Returns list of violations."""
    violations = []

    lat = report['latency_ms']
    if lat['p50'] > config.p50_target_ms:
        violations.append(f"p50 latency {lat['p50']}ms > target {config.p50_target_ms}ms")
    if lat['p95'] > config.p95_target_ms:
        violations.append(f"p95 latency {lat['p95']}ms > target {config.p95_target_ms}ms")
    if lat['p99'] > config.p99_target_ms:
        violations.append(f"p99 latency {lat['p99']}ms > target {config.p99_target_ms}ms")

    error_rate = report['summary']['error_rate_percent'] / 100
    if error_rate > config.error_rate_threshold:
        violations.append(
            f"Error rate {error_rate*100:.1f}% > threshold {config.error_rate_threshold*100:.1f}%"
        )

    throughput = report['summary']['throughput_rps']
    if throughput < config.min_throughput_rps:
        violations.append(
            f"Throughput {throughput:.1f} rps < minimum {config.min_throughput_rps} rps"
        )

    return violations

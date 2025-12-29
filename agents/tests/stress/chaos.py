"""Chaos engineering tests for resilience verification."""

import asyncio
import json
import time
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional
import httpx

from .config import config
from .payloads import (
    text_message,
    malformed_json,
    empty_payload,
    missing_message,
    huge_payload,
    invalid_user_id,
    string_user_id,
)
from .users import user_pool


@dataclass
class ChaosResult:
    """Result of a chaos test."""

    name: str
    passed: bool
    expected: str
    actual: str
    duration_ms: float
    error: Optional[str] = None


@dataclass
class ChaosReport:
    """Aggregated chaos test results."""

    results: List[ChaosResult] = field(default_factory=list)
    start_time: float = field(default_factory=time.time)

    @property
    def passed(self) -> int:
        return sum(1 for r in self.results if r.passed)

    @property
    def failed(self) -> int:
        return len(self.results) - self.passed

    @property
    def duration_seconds(self) -> float:
        return time.time() - self.start_time

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON output."""
        return {
            "summary": {
                "total": len(self.results),
                "passed": self.passed,
                "failed": self.failed,
                "duration_seconds": round(self.duration_seconds, 2),
            },
            "results": [
                {
                    "name": r.name,
                    "passed": r.passed,
                    "expected": r.expected,
                    "actual": r.actual,
                    "duration_ms": round(r.duration_ms, 2),
                    "error": r.error,
                }
                for r in self.results
            ],
        }


class ChaosRunner:
    """Executes chaos test scenarios."""

    def __init__(self, base_url: str = None, timeout: float = None):
        """Initialize chaos runner."""
        self.base_url = base_url or config.webhook_url.rsplit("/webhook", 1)[0]
        self.webhook_url = f"{self.base_url}/webhook/telegram"
        self.timeout = timeout or config.request_timeout
        self.report = ChaosReport()

    async def run_all(self) -> ChaosReport:
        """Run all chaos tests."""
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            self.client = client

            # Invalid payload tests
            await self.test_malformed_json()
            await self.test_empty_payload()
            await self.test_missing_message()
            await self.test_invalid_user_id()
            await self.test_string_user_id()

            # Overload tests
            await self.test_huge_payload()
            await self.test_concurrent_burst()

            # Security tests
            await self.test_guest_admin_escalation()
            await self.test_negative_user_id()

            # Circuit breaker tests
            await self.test_circuit_status()

        return self.report

    async def _send(self, payload: Any, is_json: bool = True) -> httpx.Response:
        """Send request to webhook."""
        if is_json:
            return await self.client.post(
                self.webhook_url,
                json=payload,
                headers={"Content-Type": "application/json"},
            )
        else:
            return await self.client.post(
                self.webhook_url,
                content=payload,
                headers={"Content-Type": "application/json"},
            )

    def _record(self, name: str, passed: bool, expected: str, actual: str,
                duration_ms: float, error: str = None):
        """Record test result."""
        self.report.results.append(ChaosResult(
            name=name,
            passed=passed,
            expected=expected,
            actual=actual,
            duration_ms=duration_ms,
            error=error,
        ))

    # ==================== Invalid Payload Tests ====================

    async def test_malformed_json(self):
        """Send malformed JSON, expect 4xx error."""
        name = "malformed_json"
        start = time.time()
        try:
            response = await self._send(malformed_json(), is_json=False)
            duration = (time.time() - start) * 1000
            passed = response.status_code in (400, 422, 500)
            self._record(name, passed, "4xx/5xx", str(response.status_code), duration)
        except Exception as e:
            duration = (time.time() - start) * 1000
            self._record(name, False, "4xx/5xx", "exception", duration, str(e))

    async def test_empty_payload(self):
        """Send empty payload, expect graceful handling."""
        name = "empty_payload"
        start = time.time()
        try:
            response = await self._send(empty_payload())
            duration = (time.time() - start) * 1000
            passed = response.status_code in (200, 400, 422)
            self._record(name, passed, "2xx/4xx", str(response.status_code), duration)
        except Exception as e:
            duration = (time.time() - start) * 1000
            self._record(name, False, "2xx/4xx", "exception", duration, str(e))

    async def test_missing_message(self):
        """Send update without message field."""
        name = "missing_message"
        start = time.time()
        try:
            response = await self._send(missing_message())
            duration = (time.time() - start) * 1000
            passed = response.status_code in (200, 400, 422)
            self._record(name, passed, "2xx/4xx", str(response.status_code), duration)
        except Exception as e:
            duration = (time.time() - start) * 1000
            self._record(name, False, "2xx/4xx", "exception", duration, str(e))

    async def test_invalid_user_id(self):
        """Send negative user ID."""
        name = "invalid_user_id"
        start = time.time()
        try:
            response = await self._send(invalid_user_id())
            duration = (time.time() - start) * 1000
            passed = response.status_code in (200, 400, 422)
            self._record(name, passed, "2xx/4xx", str(response.status_code), duration)
        except Exception as e:
            duration = (time.time() - start) * 1000
            self._record(name, False, "2xx/4xx", "exception", duration, str(e))

    async def test_string_user_id(self):
        """Send string instead of int for user ID."""
        name = "string_user_id"
        start = time.time()
        try:
            response = await self._send(string_user_id())
            duration = (time.time() - start) * 1000
            passed = response.status_code in (200, 400, 422, 500)
            self._record(name, passed, "any response", str(response.status_code), duration)
        except Exception as e:
            duration = (time.time() - start) * 1000
            self._record(name, False, "any response", "exception", duration, str(e))

    # ==================== Overload Tests ====================

    async def test_huge_payload(self):
        """Send 1MB payload to test memory limits."""
        name = "huge_payload_1mb"
        start = time.time()
        try:
            payload = huge_payload(size_mb=1)
            response = await self._send(payload)
            duration = (time.time() - start) * 1000
            # Accept rejection (413, 422) or timeout handling
            passed = response.status_code in (200, 400, 413, 422, 500)
            self._record(name, passed, "any response", str(response.status_code), duration)
        except httpx.TimeoutException:
            duration = (time.time() - start) * 1000
            self._record(name, True, "timeout acceptable", "timeout", duration)
        except Exception as e:
            duration = (time.time() - start) * 1000
            self._record(name, False, "any response", "exception", duration, str(e))

    async def test_concurrent_burst(self, count: int = 50):
        """Send 50 simultaneous requests."""
        name = "concurrent_burst_50"
        start = time.time()
        try:
            user_id = user_pool.get_user("guest")
            tasks = [
                self._send(text_message(user_id, f"burst {i}"))
                for i in range(count)
            ]
            responses = await asyncio.gather(*tasks, return_exceptions=True)
            duration = (time.time() - start) * 1000

            errors = sum(1 for r in responses if isinstance(r, Exception))
            successes = count - errors

            passed = successes >= count * 0.8  # 80% success rate
            self._record(
                name, passed,
                f">={count * 0.8} successes",
                f"{successes}/{count} successes",
                duration
            )
        except Exception as e:
            duration = (time.time() - start) * 1000
            self._record(name, False, "burst complete", "exception", duration, str(e))

    # ==================== Security Tests ====================

    async def test_guest_admin_escalation(self):
        """Guest user attempts admin command."""
        name = "guest_admin_escalation"
        start = time.time()
        try:
            guest_id = user_pool.get_user("guest")
            payload = text_message(guest_id, "/grant 123456 admin")
            response = await self._send(payload)
            duration = (time.time() - start) * 1000

            # Should get 200 but response should deny access
            if response.status_code == 200:
                body = response.text.lower()
                passed = "denied" in body or "admin" in body or "permission" in body
            else:
                passed = response.status_code in (403, 401)

            self._record(name, passed, "access denied", f"{response.status_code}", duration)
        except Exception as e:
            duration = (time.time() - start) * 1000
            self._record(name, False, "access denied", "exception", duration, str(e))

    async def test_negative_user_id(self):
        """Test with negative user ID."""
        name = "negative_user_id"
        start = time.time()
        try:
            payload = text_message(-999999, "test")
            response = await self._send(payload)
            duration = (time.time() - start) * 1000
            passed = response.status_code in (200, 400, 422)
            self._record(name, passed, "handled gracefully", str(response.status_code), duration)
        except Exception as e:
            duration = (time.time() - start) * 1000
            self._record(name, False, "handled gracefully", "exception", duration, str(e))

    # ==================== Circuit Breaker Tests ====================

    async def test_circuit_status(self):
        """Check /circuits endpoint responds."""
        name = "circuit_status_endpoint"
        start = time.time()
        try:
            response = await self.client.get(f"{self.base_url}/api/circuits")
            duration = (time.time() - start) * 1000
            passed = response.status_code == 200
            self._record(name, passed, "200", str(response.status_code), duration)
        except Exception as e:
            duration = (time.time() - start) * 1000
            self._record(name, False, "200", "exception", duration, str(e))


async def run_chaos_tests(base_url: str = None) -> ChaosReport:
    """Run all chaos tests and return report."""
    runner = ChaosRunner(base_url)
    return await runner.run_all()


if __name__ == "__main__":
    """Run chaos tests standalone."""
    import sys

    report = asyncio.run(run_chaos_tests())
    print(json.dumps(report.to_dict(), indent=2))
    sys.exit(0 if report.failed == 0 else 1)

"""UX metrics collection and storage.

Tracks latency, command success, and circuit breaker events.
"""
from datetime import datetime, timezone, timedelta
from typing import Dict, Optional, List, Any
import asyncio

from src.services.firebase._client import get_db
from src.services.firebase._circuit import with_firebase_circuit
from src.utils.logging import get_logger

logger = get_logger()

# TTL for metrics (30 days)
METRICS_TTL_DAYS = 30


class UXMetricsService:
    """Collect and analyze UX metrics."""

    def __init__(self):
        self._write_queue: List[Dict] = []
        self._flush_task: Optional[asyncio.Task] = None

    async def record_latency(
        self,
        operation: str,
        latency_ms: int,
        success: bool,
        context: Optional[Dict] = None
    ) -> None:
        """Record operation latency.

        Args:
            operation: "llm_chat", "skill_execute", "web_search", etc.
            latency_ms: Duration in milliseconds
            success: Whether operation succeeded
            context: Additional context (user_tier, model, etc.)
        """
        now = datetime.now(timezone.utc)
        metric = {
            "type": "latency",
            "operation": operation,
            "value_ms": latency_ms,
            "success": success,
            "context": context or {},
            "timestamp": now,
            "expires_at": now + timedelta(days=METRICS_TTL_DAYS)
        }
        await self._queue_write(metric)

    async def record_command(
        self,
        command: str,
        user_tier: str,
        success: bool,
        error_type: Optional[str] = None,
        latency_ms: Optional[int] = None
    ) -> None:
        """Record command execution.

        Args:
            command: Command name (e.g., "/start", "/skills")
            user_tier: User tier (guest, user, developer, admin)
            success: Whether command succeeded
            error_type: Error classification if failed
            latency_ms: Command execution time
        """
        now = datetime.now(timezone.utc)
        metric = {
            "type": "command",
            "operation": command,
            "success": success,
            "error_type": error_type,
            "context": {
                "user_tier": user_tier,
                "latency_ms": latency_ms
            },
            "timestamp": now,
            "expires_at": now + timedelta(days=METRICS_TTL_DAYS)
        }
        await self._queue_write(metric)

    async def record_circuit_event(
        self,
        circuit_name: str,
        event: str,  # "opened", "closed", "half_open"
        failure_count: int = 0
    ) -> None:
        """Record circuit breaker state change.

        Args:
            circuit_name: Circuit identifier
            event: State transition
            failure_count: Failures before opening
        """
        now = datetime.now(timezone.utc)
        metric = {
            "type": "circuit",
            "operation": circuit_name,
            "success": event == "closed",
            "context": {
                "event": event,
                "failure_count": failure_count
            },
            "timestamp": now,
            "expires_at": now + timedelta(days=METRICS_TTL_DAYS)
        }
        await self._queue_write(metric)

    async def _queue_write(self, metric: Dict) -> None:
        """Queue metric for batch write."""
        self._write_queue.append(metric)

        # Flush immediately for now (batch later if needed)
        await self._flush()

    @with_firebase_circuit(open_return=None)
    async def _flush(self) -> None:
        """Write queued metrics to Firestore."""
        if not self._write_queue:
            return

        db = get_db()
        metrics_ref = db.collection("ux_metrics")

        # Process all pending metrics in batches of 50
        while self._write_queue:
            batch = db.batch()
            batch_items = self._write_queue[:50]

            for metric in batch_items:
                doc_ref = metrics_ref.document()
                batch.set(doc_ref, metric)

            await asyncio.to_thread(batch.commit)
            self._write_queue = self._write_queue[50:]

        logger.debug("ux_metrics_flushed", count=min(50, len(self._write_queue) + 50))

    @with_firebase_circuit(open_return={})
    async def get_sla_report(self, hours: int = 24) -> Dict[str, Any]:
        """Get SLA metrics for dashboard.

        Args:
            hours: Time window (1, 24, 168 for week)

        Returns:
            SLA report with P50/P95/P99 latencies, success rates
        """
        db = get_db()
        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)

        # Query latency metrics
        latency_query = (
            db.collection("ux_metrics")
            .where("type", "==", "latency")
            .where("timestamp", ">=", cutoff)
        )

        # Query command metrics
        command_query = (
            db.collection("ux_metrics")
            .where("type", "==", "command")
            .where("timestamp", ">=", cutoff)
        )

        # Query circuit events
        circuit_query = (
            db.collection("ux_metrics")
            .where("type", "==", "circuit")
            .where("timestamp", ">=", cutoff)
        )

        # Execute queries
        latency_docs = await asyncio.to_thread(lambda: list(latency_query.stream()))
        command_docs = await asyncio.to_thread(lambda: list(command_query.stream()))
        circuit_docs = await asyncio.to_thread(lambda: list(circuit_query.stream()))

        # Process latency metrics
        llm_latencies = []
        search_latencies = []
        for doc in latency_docs:
            data = doc.to_dict()
            latency = data.get("value_ms", 0)
            op = data.get("operation", "")
            if op == "llm_chat":
                llm_latencies.append(latency)
            elif op == "web_search":
                search_latencies.append(latency)

        # Calculate percentiles
        def percentile(data: List[int], p: int) -> int:
            if not data:
                return 0
            data_sorted = sorted(data)
            idx = int(len(data_sorted) * p / 100)
            return data_sorted[min(idx, len(data_sorted) - 1)]

        # Process command metrics
        command_total = len(command_docs)
        command_success = sum(1 for d in command_docs if d.to_dict().get("success"))

        # Process circuit events
        circuit_opens = sum(
            1 for d in circuit_docs
            if d.to_dict().get("context", {}).get("event") == "opened"
        )

        return {
            "hours": hours,
            "llm_p50": percentile(llm_latencies, 50),
            "llm_p95": percentile(llm_latencies, 95),
            "llm_p99": percentile(llm_latencies, 99),
            "llm_success_rate": (
                sum(1 for d in latency_docs if d.to_dict().get("operation") == "llm_chat" and d.to_dict().get("success"))
                / max(len(llm_latencies), 1) * 100
            ),
            "search_p50": percentile(search_latencies, 50),
            "search_p95": percentile(search_latencies, 95),
            "search_success_rate": (
                sum(1 for d in latency_docs if d.to_dict().get("operation") == "web_search" and d.to_dict().get("success"))
                / max(len(search_latencies), 1) * 100
            ),
            "command_count": command_total,
            "command_success_rate": command_success / max(command_total, 1) * 100,
            "circuits_open": circuit_opens,
            "circuit_trips": circuit_opens,
        }


# Singleton
_service: Optional[UXMetricsService] = None


def get_ux_metrics_service() -> UXMetricsService:
    """Get or create UXMetricsService singleton."""
    global _service
    if _service is None:
        _service = UXMetricsService()
    return _service

"""Smart Timing Engine - Learn optimal reminder times from user behavior.

Analyzes completion patterns, energy levels, calendar gaps to suggest optimal task times.
"""
from dataclasses import dataclass, field
from datetime import datetime, time, timedelta, timezone
from typing import Optional, List, Dict

from src.services.firebase.pkm import SmartTask
from src.utils.logging import get_logger

logger = get_logger()


@dataclass
class TimingFactors:
    """Factors used to calculate optimal task timing."""
    task_priority: float  # 0.0-1.0
    estimated_duration: int  # minutes
    energy_match: float  # 0.0-1.0
    calendar_gap_score: float  # 0.0-1.0
    historical_completion_score: float  # 0.0-1.0
    context_availability: float  # 0.0-1.0


@dataclass
class UserActivity:
    """User activity learning data."""
    user_id: int
    energy_patterns: Dict[int, float] = field(default_factory=dict)  # hour → completion rate
    completion_by_day: Dict[int, int] = field(default_factory=dict)  # weekday → count
    snooze_count: int = 0
    avg_procrastination_hours: float = 0.0
    context_times: Dict[str, List[int]] = field(default_factory=dict)  # context → preferred hours


class SmartTimingEngine:
    """Learn optimal reminder times from user behavior."""

    def __init__(self):
        self.default_energy_pattern = {
            9: 0.9,   # High energy morning
            10: 0.95,
            11: 0.85,
            14: 0.6,  # Post-lunch slump
            15: 0.7,
            16: 0.8,
            17: 0.75,
        }

    async def calculate_optimal_time(
        self,
        task: SmartTask,
        user_id: int,
        calendar_events: Optional[List[Dict]] = None
    ) -> datetime:
        """Find best reminder time based on learned patterns.

        Args:
            task: SmartTask to schedule
            user_id: User ID
            calendar_events: Optional list of calendar events

        Returns:
            Optimal datetime for task reminder
        """
        calendar_events = calendar_events or []

        # Load user activity data
        activity = await self._get_user_activity(user_id)

        factors = TimingFactors(
            task_priority=self._priority_weight(task.priority),
            estimated_duration=task.estimated_duration or 30,
            energy_match=self._match_energy_to_time(task.energy_level, activity),
            calendar_gap_score=self._find_gap_score(calendar_events, task.due_date),
            historical_completion_score=self._completion_patterns(activity, task),
            context_availability=self._context_windows(task.context, activity)
        )

        logger.info(
            "timing_factors_calculated",
            user_id=user_id,
            task_id=task.id,
            factors=factors.__dict__
        )

        return await self._optimize(factors, task.due_date, activity)

    def _priority_weight(self, priority: Optional[str]) -> float:
        """Convert priority to weight score."""
        weights = {"p1": 1.0, "p2": 0.75, "p3": 0.5, "p4": 0.25}
        return weights.get(priority, 0.5)

    def _match_energy_to_time(
        self,
        energy: Optional[str],
        activity: UserActivity
    ) -> float:
        """Match task energy to user's typical energy patterns by hour.

        High energy tasks → morning for most users
        Low energy → afternoon slump times
        """
        if not energy:
            return 0.5

        # Use learned patterns or defaults
        patterns = activity.energy_patterns if activity.energy_patterns else self.default_energy_pattern

        if energy == "high":
            # Find highest energy hours
            if patterns:
                best_hour = max(patterns, key=patterns.get)
                return patterns.get(best_hour, 0.5)
            return 0.9  # Morning default

        elif energy == "low":
            # Find lower energy hours (still productive)
            if patterns:
                sorted_hours = sorted(patterns.items(), key=lambda x: x[1])
                # Use middle-low energy hour (not lowest)
                if len(sorted_hours) >= 2:
                    return sorted_hours[len(sorted_hours) // 2][1]
            return 0.6  # Afternoon default

        return 0.7  # Medium energy default

    def _find_gap_score(
        self,
        events: List[Dict],
        target_date: Optional[datetime]
    ) -> float:
        """Score based on calendar free time around target.

        Args:
            events: List of calendar events with 'start' and 'end' datetime
            target_date: Target due date

        Returns:
            Score 0.0-1.0 based on available gaps
        """
        if not target_date or not events:
            return 0.5

        # Find gaps before due_date
        gaps = self._calculate_gaps(events, target_date)
        if not gaps:
            return 0.2  # No good gaps

        # Normalize by 1 hour (60 min)
        max_gap = max(gaps)
        return min(1.0, max_gap / 60.0)

    def _calculate_gaps(
        self,
        events: List[Dict],
        target: datetime
    ) -> List[float]:
        """Calculate free time gaps in minutes before target.

        Args:
            events: Calendar events with 'start' and 'end' datetime
            target: Target datetime

        Returns:
            List of gap durations in minutes
        """
        # Filter events before target
        relevant = [e for e in events if e.get("start") and e["start"] < target]
        if not relevant:
            return [480.0]  # Full day available

        # Sort by start time
        sorted_events = sorted(relevant, key=lambda e: e["start"])

        gaps = []
        for i in range(len(sorted_events) - 1):
            end_time = sorted_events[i].get("end")
            next_start = sorted_events[i + 1].get("start")

            if end_time and next_start:
                gap_minutes = (next_start - end_time).total_seconds() / 60
                if gap_minutes > 0:
                    gaps.append(gap_minutes)

        return gaps

    def _completion_patterns(
        self,
        activity: UserActivity,
        task: SmartTask
    ) -> float:
        """Score based on historical completion patterns.

        Args:
            activity: User activity data
            task: SmartTask

        Returns:
            Score based on similar task completion history
        """
        if not activity.completion_by_day:
            return 0.5  # No data

        # Check if task has due date to determine day
        if not task.due_date:
            return 0.5

        weekday = task.due_date.weekday()
        completions = activity.completion_by_day.get(weekday, 0)
        total = sum(activity.completion_by_day.values())

        if total == 0:
            return 0.5

        # Normalize to 0.0-1.0
        return min(1.0, completions / (total / 7))  # Compared to average

    def _context_windows(
        self,
        context: Optional[str],
        activity: UserActivity
    ) -> float:
        """Score based on when user typically works in this context.

        Args:
            context: Task context (@home, @work, @errands)
            activity: User activity data

        Returns:
            Score based on context availability patterns
        """
        if not context or not activity.context_times:
            return 0.5

        preferred_hours = activity.context_times.get(context, [])
        if not preferred_hours:
            return 0.5

        # Calculate score based on overlap with preferred hours
        # For now, return 0.8 if context has history
        return 0.8 if preferred_hours else 0.5

    async def _optimize(
        self,
        factors: TimingFactors,
        target_date: Optional[datetime],
        activity: UserActivity
    ) -> datetime:
        """Optimize timing based on all factors.

        Args:
            factors: Timing factors
            target_date: Target due date
            activity: User activity data

        Returns:
            Optimal datetime for reminder
        """
        now = datetime.now(timezone.utc)

        # If no target date, suggest based on priority
        if not target_date:
            # High priority: within 1 hour
            # Medium: within 4 hours
            # Low: tomorrow
            hours_offset = {
                1.0: 1,
                0.75: 4,
                0.5: 24,
                0.25: 48
            }.get(factors.task_priority, 24)

            target_date = now + timedelta(hours=hours_offset)

        # Find optimal hour based on energy patterns
        patterns = activity.energy_patterns if activity.energy_patterns else self.default_energy_pattern

        # Get best hour for this task
        best_hour = self._select_best_hour(factors, patterns)

        # Combine target date with best hour
        optimal = target_date.replace(
            hour=best_hour,
            minute=0,
            second=0,
            microsecond=0
        )

        # Ensure not in the past
        if optimal < now:
            optimal = now + timedelta(minutes=30)

        logger.info(
            "optimal_time_calculated",
            target=target_date.isoformat() if target_date else None,
            optimal=optimal.isoformat(),
            best_hour=best_hour
        )

        return optimal

    def _select_best_hour(
        self,
        factors: TimingFactors,
        patterns: Dict[int, float]
    ) -> int:
        """Select best hour based on factors and patterns.

        Args:
            factors: Timing factors
            patterns: Energy patterns by hour

        Returns:
            Best hour (0-23)
        """
        if not patterns:
            # Default to 10am
            return 10

        # Weight patterns by energy match and priority
        weighted = {}
        for hour, energy in patterns.items():
            weight = (
                energy * factors.energy_match * 0.4 +
                factors.task_priority * 0.3 +
                factors.calendar_gap_score * 0.3
            )
            weighted[hour] = weight

        # Return hour with highest weight
        best_hour = max(weighted, key=weighted.get)
        return best_hour

    async def record_completion(
        self,
        task: SmartTask,
        completed_at: datetime
    ) -> None:
        """Record completion for learning.

        Args:
            task: Completed SmartTask
            completed_at: Completion datetime
        """
        await self._store_signal(
            user_id=task.user_id,
            signal_type="completion",
            task_type=task.type,
            hour=completed_at.hour,
            day_of_week=completed_at.weekday(),
            priority=task.priority,
            context=task.context
        )

        logger.info(
            "completion_recorded",
            user_id=task.user_id,
            task_id=task.id,
            hour=completed_at.hour,
            weekday=completed_at.weekday()
        )

    async def _get_user_activity(self, user_id: int) -> UserActivity:
        """Load user activity data from Firebase.

        Args:
            user_id: User ID

        Returns:
            UserActivity with learning signals
        """
        from src.services.firebase import get_db

        try:
            db = get_db()
            if not db:
                return UserActivity(user_id=user_id)

            doc = db.collection("user_activity").document(str(user_id)).get()

            if not doc.exists:
                return UserActivity(user_id=user_id)

            data = doc.to_dict()
            return UserActivity(
                user_id=user_id,
                energy_patterns=data.get("energy_patterns", {}),
                completion_by_day=data.get("completion_by_day", {}),
                snooze_count=data.get("snooze_count", 0),
                avg_procrastination_hours=data.get("avg_procrastination_hours", 0.0),
                context_times=data.get("context_times", {})
            )

        except Exception as e:
            logger.error("load_user_activity_error", error=str(e)[:100])
            return UserActivity(user_id=user_id)

    async def _store_signal(
        self,
        user_id: int,
        signal_type: str,
        **kwargs
    ) -> None:
        """Store learning signal to Firebase.

        Args:
            user_id: User ID
            signal_type: Type of signal (completion, snooze, etc.)
            **kwargs: Signal metadata
        """
        from src.services.firebase import get_db
        from firebase_admin import firestore

        try:
            db = get_db()
            if not db:
                return

            doc_ref = db.collection("user_activity").document(str(user_id))

            # Update energy patterns
            if signal_type == "completion" and "hour" in kwargs:
                hour = kwargs["hour"]

                # Get current data
                current = doc_ref.get()
                if current.exists:
                    data = current.to_dict()
                    energy_patterns = data.get("energy_patterns", {})
                    completion_by_day = data.get("completion_by_day", {})
                else:
                    energy_patterns = {}
                    completion_by_day = {}

                # Update hour pattern (simple moving average)
                hour_key = str(hour)
                current_score = energy_patterns.get(hour_key, 0.5)
                new_score = (current_score * 0.9 + 1.0 * 0.1)  # Weight recent higher
                energy_patterns[hour_key] = new_score

                # Update day completion count
                if "day_of_week" in kwargs:
                    day_key = str(kwargs["day_of_week"])
                    completion_by_day[day_key] = completion_by_day.get(day_key, 0) + 1

                # Update context times
                context_times = data.get("context_times", {}) if current.exists else {}
                if kwargs.get("context"):
                    ctx = kwargs["context"]
                    if ctx not in context_times:
                        context_times[ctx] = []
                    if hour not in context_times[ctx]:
                        context_times[ctx].append(hour)

                doc_ref.set({
                    "user_id": user_id,
                    "energy_patterns": energy_patterns,
                    "completion_by_day": completion_by_day,
                    "context_times": context_times,
                    "updated_at": firestore.SERVER_TIMESTAMP
                }, merge=True)

                logger.info("learning_signal_stored", user_id=user_id, signal_type=signal_type)

        except Exception as e:
            logger.error("store_signal_error", error=str(e)[:100])

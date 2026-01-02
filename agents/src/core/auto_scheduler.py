"""Auto Scheduler - Detect calendar conflicts and auto-reschedule tasks.

Checks for time conflicts and suggests/applies optimal reschedule times.
"""
from dataclasses import dataclass
from datetime import datetime, timedelta, time, timezone
from typing import Optional, List, Dict, Literal

from src.services.firebase.pkm import SmartTask, update_smart_task
from src.utils.logging import get_logger

logger = get_logger()


@dataclass
class ConflictInfo:
    """Information about a scheduling conflict."""
    task_id: str
    conflict_type: Literal["overlap", "too_close", "no_time"]
    conflicting_event: Optional[Dict]
    suggested_times: List[datetime]


class AutoScheduler:
    """Detect calendar conflicts and suggest/apply reschedules."""

    MIN_GAP_MINUTES = 15  # Buffer between events
    LOOKAHEAD_DAYS = 7

    async def check_conflicts(
        self,
        task: SmartTask,
        calendar_events: List[Dict]
    ) -> Optional[ConflictInfo]:
        """Check if task time conflicts with calendar.

        Args:
            task: SmartTask to check
            calendar_events: List of calendar events with 'start' and 'end' datetime

        Returns:
            ConflictInfo if conflict found, None otherwise
        """
        if not task.due_date:
            return None

        # Build task time range
        task_start = self._get_task_start(task)
        if not task_start:
            return None

        task_end = task_start + timedelta(minutes=task.estimated_duration or 30)

        logger.debug(
            "checking_conflicts",
            task_id=task.id,
            task_start=task_start.isoformat(),
            task_end=task_end.isoformat(),
            events_count=len(calendar_events)
        )

        # Check each event for overlap
        for event in calendar_events:
            event_start = event.get("start")
            event_end = event.get("end")

            if not event_start or not event_end:
                continue

            # Check overlap
            if self._overlaps(task_start, task_end, event_start, event_end):
                suggestions = await self._find_alternatives(
                    task, calendar_events, task_start
                )

                logger.info(
                    "conflict_detected",
                    task_id=task.id,
                    event_title=event.get("summary", "Untitled"),
                    suggestions_count=len(suggestions)
                )

                return ConflictInfo(
                    task_id=task.id,
                    conflict_type="overlap",
                    conflicting_event=event,
                    suggested_times=suggestions[:3]
                )

        return None

    def _get_task_start(self, task: SmartTask) -> Optional[datetime]:
        """Get task start datetime.

        Args:
            task: SmartTask

        Returns:
            datetime if both due_date and due_time set, None otherwise
        """
        if not task.due_date:
            return None

        # If no time specified, use default 9am
        task_time = task.due_time if task.due_time else time(9, 0)

        # Combine date and time
        return datetime.combine(task.due_date, task_time)

    def _overlaps(
        self,
        start1: datetime, end1: datetime,
        start2: datetime, end2: datetime
    ) -> bool:
        """Check if two time ranges overlap with buffer.

        Args:
            start1: Start of first range
            end1: End of first range
            start2: Start of second range
            end2: End of second range

        Returns:
            True if ranges overlap (including buffer)
        """
        buffer = timedelta(minutes=self.MIN_GAP_MINUTES)
        return not (end1 + buffer <= start2 or end2 + buffer <= start1)

    async def _find_alternatives(
        self,
        task: SmartTask,
        calendar_events: List[Dict],
        original_time: datetime
    ) -> List[datetime]:
        """Find alternative time slots for task.

        Args:
            task: SmartTask to reschedule
            calendar_events: Calendar events
            original_time: Original scheduled time

        Returns:
            List of alternative datetime slots (up to 5)
        """
        alternatives = []
        duration = task.estimated_duration or 30

        # Search window: original day + next 7 days
        search_start = original_time.replace(hour=8, minute=0)
        search_end = search_start + timedelta(days=self.LOOKAHEAD_DAYS)

        logger.debug(
            "searching_alternatives",
            search_start=search_start.isoformat(),
            search_end=search_end.isoformat(),
            duration=duration
        )

        # Try slots in working hours (8am-6pm)
        current = search_start
        while current < search_end and len(alternatives) < 5:
            # Skip non-working hours
            if current.hour < 8 or current.hour >= 18:
                current += timedelta(days=1)
                current = current.replace(hour=8, minute=0)
                continue

            # Check if this slot is free
            slot_end = current + timedelta(minutes=duration)

            if self._is_slot_free(current, slot_end, calendar_events):
                alternatives.append(current)
                logger.debug("alternative_found", time=current.isoformat())

            # Move to next slot (30 min increments)
            current += timedelta(minutes=30)

        return alternatives

    def _is_slot_free(
        self,
        start: datetime,
        end: datetime,
        events: List[Dict]
    ) -> bool:
        """Check if time slot is free of conflicts.

        Args:
            start: Slot start
            end: Slot end
            events: Calendar events

        Returns:
            True if slot is free
        """
        for event in events:
            event_start = event.get("start")
            event_end = event.get("end")

            if not event_start or not event_end:
                continue

            if self._overlaps(start, end, event_start, event_end):
                return False

        return True

    async def auto_reschedule(
        self,
        task: SmartTask,
        conflict: ConflictInfo,
        trust_level: str = "ask"
    ) -> bool:
        """Reschedule task if allowed by trust level.

        Args:
            task: SmartTask to reschedule
            conflict: ConflictInfo with suggestions
            trust_level: Trust level ("auto", "notify", "ask")

        Returns:
            True if rescheduled, False if queued for confirmation
        """
        if not conflict.suggested_times:
            logger.warning("no_alternatives", task_id=task.id)
            return False

        new_time = conflict.suggested_times[0]

        # Auto-execute if trusted
        if trust_level == "auto":
            await self._apply_reschedule(task, new_time)

            # Notify user of change
            await self._notify_reschedule(
                task.user_id,
                task,
                new_time,
                conflict.conflicting_event
            )

            logger.info(
                "auto_rescheduled",
                task_id=task.id,
                old_time=self._get_task_start(task).isoformat() if self._get_task_start(task) else None,
                new_time=new_time.isoformat()
            )
            return True

        elif trust_level == "notify":
            # Apply but notify prominently
            await self._apply_reschedule(task, new_time)
            await self._notify_reschedule(
                task.user_id,
                task,
                new_time,
                conflict.conflicting_event,
                prominent=True
            )
            return True

        else:
            # Queue for user confirmation
            await self._queue_reschedule_confirmation(task, conflict.suggested_times)
            return False

    async def _apply_reschedule(
        self,
        task: SmartTask,
        new_time: datetime
    ) -> None:
        """Apply reschedule to task.

        Args:
            task: SmartTask to update
            new_time: New datetime
        """
        await update_smart_task(
            task.user_id,
            task.id,
            due_date=new_time.date() if new_time.date() else task.due_date,
            due_time=new_time.time() if new_time.time() else task.due_time
        )

        logger.info("reschedule_applied", task_id=task.id, new_time=new_time.isoformat())

    async def _notify_reschedule(
        self,
        user_id: int,
        task: SmartTask,
        new_time: datetime,
        conflicting_event: Optional[Dict],
        prominent: bool = False
    ) -> None:
        """Notify user of reschedule.

        Args:
            user_id: User ID
            task: SmartTask
            new_time: New scheduled time
            conflicting_event: Event that caused conflict
            prominent: If True, use prominent notification
        """
        # Build notification message
        event_title = conflicting_event.get("summary", "an event") if conflicting_event else "an event"

        message = f"⏰ Rescheduled: \"{task.content}\"\n"
        message += f"📅 New time: {new_time.strftime('%b %d, %I:%M %p')}\n"
        message += f"⚠️ Reason: Conflicts with {event_title}"

        logger.info("reschedule_notification", user_id=user_id, task_id=task.id)

        # TODO: Send notification via transport
        # For now, store in notifications collection
        from src.services.firebase import get_db
        from firebase_admin import firestore

        try:
            db = get_db()
            if db:
                db.collection("notifications").document(str(user_id)).collection("items").add({
                    "type": "task_rescheduled",
                    "task_id": task.id,
                    "message": message,
                    "prominent": prominent,
                    "created_at": firestore.SERVER_TIMESTAMP,
                    "read": False
                })
        except Exception as e:
            logger.error("notification_error", error=str(e)[:100])

    async def _queue_reschedule_confirmation(
        self,
        task: SmartTask,
        suggested_times: List[datetime]
    ) -> None:
        """Queue reschedule for user confirmation.

        Args:
            task: SmartTask
            suggested_times: List of suggested times
        """
        from src.services.firebase import get_db
        from firebase_admin import firestore

        try:
            db = get_db()
            if not db:
                return

            # Store confirmation request
            db.collection("reschedule_confirmations").document(task.id).set({
                "user_id": task.user_id,
                "task_id": task.id,
                "task_content": task.content,
                "original_time": self._get_task_start(task).isoformat() if self._get_task_start(task) else None,
                "suggested_times": [t.isoformat() for t in suggested_times],
                "status": "pending",
                "created_at": firestore.SERVER_TIMESTAMP
            })

            logger.info("reschedule_queued", task_id=task.id, suggestions=len(suggested_times))

        except Exception as e:
            logger.error("queue_confirmation_error", error=str(e)[:100])

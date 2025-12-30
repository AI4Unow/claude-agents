"""Firebase Firestore service for state management, task queues, and logging.

II Framework Temporal Schema:
- skills/{id}: Skill config, stats, memory backup
- entities/{id}: Facts with valid_from/valid_until (temporal)
- decisions/{id}: Learned rules with temporal validity
- logs/{id}: Execution logs with observation refs
- observations/{id}: Masked verbose outputs
- user_tiers/{telegram_id}: User access tiers for Telegram parity

This package re-exports all functions from domain-specific modules for backward compatibility.
"""

# Re-export client utilities
from ._client import get_db, Collections

# Re-export firestore for backward compatibility with tests
from firebase_admin import firestore

# Re-export type constants
from .tiers import TierType, TIER_HIERARCHY, TIER_RATE_LIMITS
from .faq import FAQEntry
from .local_tasks import LocalTask
from .pkm import PKMItem, ItemType, ItemStatus

# Users
from .users import (
    get_user,
    create_or_update_user,
    update_agent_status,
    get_agent,
)

# Tasks
from .tasks import (
    create_task,
    claim_task,
    complete_task,
    fail_task,
)

# Tiers
from .tiers import (
    get_user_tier,
    set_user_tier,
    remove_user_tier,
    has_permission,
    get_rate_limit,
)

# FAQ
from .faq import (
    get_faq_entries,
    create_faq_entry,
    update_faq_entry,
    delete_faq_entry,
)

# Reports
from .reports import (
    save_report,
    save_file,
    list_user_reports,
    get_report_url,
    get_report_content,
    cleanup_expired_content,
)

# Reminders
from .reminders import (
    create_reminder,
    get_due_reminders,
    mark_reminder_sent,
    get_user_reminders,
    delete_reminder,
)

# Local Tasks
from .local_tasks import (
    create_local_task,
    get_pending_local_tasks,
    claim_local_task,
    complete_local_task,
    increment_retry_count,
    get_task_result,
    cleanup_old_tasks,
)

# II Framework (entities, decisions, observations, skills)
from .ii_framework import (
    get_skill,
    update_skill_stats,
    backup_skill_memory,
    create_entity,
    get_entity,
    get_entities_by_type,
    create_decision,
    get_decisions,
    invalidate_decision,
    store_observation,
    get_observation,
    log_execution,
    log_activity,
    keyword_search,
)

# Tokens
from .tokens import (
    get_token,
    save_token,
)

# PKM
from .pkm import (
    create_item,
    get_item,
    update_item,
    delete_item,
    list_items,
    get_inbox,
    get_tasks,
)

# For compatibility with old imports
def get_storage_bucket():
    """Get Firebase Storage bucket (legacy function for compatibility)."""
    from ._client import get_bucket
    return get_bucket()

def init_firebase():
    """Initialize Firebase (legacy function for compatibility)."""
    from ._client import get_db
    get_db()  # Triggers initialization


__all__ = [
    # Client
    "get_db",
    "Collections",
    "get_storage_bucket",
    "init_firebase",

    # Types
    "TierType",
    "TIER_HIERARCHY",
    "TIER_RATE_LIMITS",
    "FAQEntry",
    "LocalTask",
    "PKMItem",
    "ItemType",
    "ItemStatus",

    # Users
    "get_user",
    "create_or_update_user",
    "update_agent_status",
    "get_agent",

    # Tasks
    "create_task",
    "claim_task",
    "complete_task",
    "fail_task",

    # Tiers
    "get_user_tier",
    "set_user_tier",
    "remove_user_tier",
    "has_permission",
    "get_rate_limit",

    # FAQ
    "get_faq_entries",
    "create_faq_entry",
    "update_faq_entry",
    "delete_faq_entry",

    # Reports
    "save_report",
    "save_file",
    "list_user_reports",
    "get_report_url",
    "get_report_content",
    "cleanup_expired_content",

    # Reminders
    "create_reminder",
    "get_due_reminders",
    "mark_reminder_sent",
    "get_user_reminders",
    "delete_reminder",

    # Local Tasks
    "create_local_task",
    "get_pending_local_tasks",
    "claim_local_task",
    "complete_local_task",
    "increment_retry_count",
    "get_task_result",
    "cleanup_old_tasks",

    # II Framework
    "get_skill",
    "update_skill_stats",
    "backup_skill_memory",
    "create_entity",
    "get_entity",
    "get_entities_by_type",
    "create_decision",
    "get_decisions",
    "invalidate_decision",
    "store_observation",
    "get_observation",
    "log_execution",
    "log_activity",
    "keyword_search",

    # Tokens
    "get_token",
    "save_token",

    # PKM
    "create_item",
    "get_item",
    "update_item",
    "delete_item",
    "list_items",
    "get_inbox",
    "get_tasks",
]

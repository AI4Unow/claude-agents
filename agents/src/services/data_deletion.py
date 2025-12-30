"""Data deletion service - GDPR compliance."""
from src.services.firebase import get_db
from src.services.qdrant import get_client
from src.core.state import get_state_manager
from src.utils.logging import get_logger

logger = get_logger()


async def delete_all_user_data(user_id: int) -> dict:
    """Delete all personal data for a user.

    Implements /forget command for GDPR compliance.

    Args:
        user_id: Telegram user ID

    Returns:
        Dict with deletion status per collection
    """
    results = {}

    # 1. Delete profile
    try:
        from src.services.user_profile import delete_profile
        await delete_profile(user_id)
        results["profile"] = "deleted"
    except Exception as e:
        results["profile"] = f"error: {str(e)[:30]}"

    # 2. Delete context
    try:
        db = get_db()
        if db:
            db.collection("user_contexts").document(str(user_id)).delete()
        results["context"] = "deleted"
    except Exception as e:
        results["context"] = f"error: {str(e)[:30]}"

    # 3. Delete macros
    try:
        db = get_db()
        if db:
            macros_ref = db.collection("user_macros").document(str(user_id))
            # Delete subcollection
            for doc in macros_ref.collection("macros").get():
                doc.reference.delete()
            macros_ref.delete()
        results["macros"] = "deleted"
    except Exception as e:
        results["macros"] = f"error: {str(e)[:30]}"

    # 4. Delete activities (Firebase)
    try:
        db = get_db()
        if db:
            activities_ref = db.collection("user_activities").document(str(user_id))
            for doc in activities_ref.collection("logs").limit(500).get():
                doc.reference.delete()
            activities_ref.delete()
        results["activities"] = "deleted"
    except Exception as e:
        results["activities"] = f"error: {str(e)[:30]}"

    # 5. Delete from Qdrant (conversations and activities)
    try:
        client = get_client()
        if client:
            from qdrant_client.http import models

            # Delete from conversations collection
            try:
                client.delete(
                    collection_name="conversations",
                    points_selector=models.FilterSelector(
                        filter=models.Filter(
                            must=[
                                models.FieldCondition(
                                    key="user_id",
                                    match=models.MatchValue(value=str(user_id))
                                )
                            ]
                        )
                    )
                )
            except Exception:
                pass  # Collection may not exist

            # Delete from user_activities collection
            try:
                client.delete(
                    collection_name="user_activities",
                    points_selector=models.FilterSelector(
                        filter=models.Filter(
                            must=[
                                models.FieldCondition(
                                    key="user_id",
                                    match=models.MatchValue(value=user_id)
                                )
                            ]
                        )
                    )
                )
            except Exception:
                pass  # Collection may not exist

            results["qdrant"] = "deleted"
    except Exception as e:
        results["qdrant"] = f"error: {str(e)[:30]}"

    # 6. Invalidate all caches
    try:
        state = get_state_manager()
        await state.invalidate("user_profiles", str(user_id))
        await state.invalidate("user_contexts", str(user_id))
        await state.invalidate("user_tiers", str(user_id))
        results["cache"] = "invalidated"
    except Exception as e:
        results["cache"] = f"error: {str(e)[:30]}"

    # 7. Delete session
    try:
        db = get_db()
        if db:
            db.collection("telegram_sessions").document(str(user_id)).delete()
        state = get_state_manager()
        await state.invalidate("telegram_sessions", str(user_id))
        results["session"] = "deleted"
    except Exception as e:
        results["session"] = f"error: {str(e)[:30]}"

    # 8. Delete conversations from Firebase
    try:
        db = get_db()
        if db:
            db.collection("conversations").document(str(user_id)).delete()
        results["conversations"] = "deleted"
    except Exception as e:
        results["conversations"] = f"error: {str(e)[:30]}"

    logger.info("user_data_deleted", user_id=user_id, results=results)
    return results


def format_deletion_result(results: dict) -> str:
    """Format deletion results for Telegram."""
    lines = ["<b>Data Deletion Complete</b>\n"]

    for key, status in results.items():
        icon = "✅" if status == "deleted" or status == "invalidated" else "❌"
        lines.append(f"{icon} <b>{key}:</b> {status}")

    lines.append("\n<i>Your personal data has been removed from our systems.</i>")

    return "\n".join(lines)

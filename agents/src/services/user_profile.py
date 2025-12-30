"""User profile service - CRUD and onboarding."""
from datetime import datetime, timezone
from typing import Optional, Dict, Literal

from src.models.personalization import UserProfile, CommunicationPrefs, ToneType
from src.core.state import get_state_manager
from src.services.firebase import get_db, firestore
from src.utils.logging import get_logger

logger = get_logger()

# Language detection keywords
LANGUAGE_INDICATORS = {
    "vi": ["xin", "chào", "tôi", "bạn", "được", "không", "có", "này"],
    "zh": ["你好", "我", "是", "的", "了", "吗"],
    "ja": ["こんにちは", "私", "です", "ます", "ありがとう"],
    "ko": ["안녕", "저", "입니다", "감사"],
}


async def get_profile(user_id: int) -> Optional[UserProfile]:
    """Get user profile."""
    state = get_state_manager()
    data = await state.get_user_profile(user_id)
    if data:
        return UserProfile.from_dict(data)
    return None


async def create_profile(user_id: int, name: Optional[str] = None) -> UserProfile:
    """Create default profile for new user."""
    profile = UserProfile(
        user_id=user_id,
        name=name,
        onboarded=False,
        updated_at=datetime.now(timezone.utc)
    )

    state = get_state_manager()
    await state.set_user_profile(user_id, profile.to_dict())

    logger.info("profile_created", user_id=user_id)
    return profile


async def update_profile(user_id: int, updates: Dict) -> Optional[UserProfile]:
    """Update user profile fields."""
    profile = await get_profile(user_id)
    if not profile:
        profile = await create_profile(user_id)

    # Apply updates
    for key, value in updates.items():
        if hasattr(profile, key):
            setattr(profile, key, value)

    profile.updated_at = datetime.now(timezone.utc)

    state = get_state_manager()
    await state.set_user_profile(user_id, profile.to_dict())

    logger.info("profile_updated", user_id=user_id, fields=list(updates.keys()))
    return profile


async def mark_onboarded(user_id: int) -> None:
    """Mark user as onboarded."""
    await update_profile(user_id, {
        "onboarded": True,
        "onboarded_at": datetime.now(timezone.utc)
    })


async def set_tone(user_id: int, tone: ToneType) -> None:
    """Set user's preferred tone."""
    await update_profile(user_id, {"tone": tone})


async def set_response_length(user_id: int, length: Literal["short", "medium", "long"]) -> None:
    """Set preferred response length."""
    profile = await get_profile(user_id)
    if not profile:
        profile = await create_profile(user_id)

    profile.communication.response_length = length
    state = get_state_manager()
    await state.set_user_profile(user_id, profile.to_dict())


async def toggle_emoji(user_id: int, enabled: bool) -> None:
    """Toggle emoji usage in responses."""
    profile = await get_profile(user_id)
    if not profile:
        profile = await create_profile(user_id)

    profile.communication.use_emoji = enabled
    state = get_state_manager()
    await state.set_user_profile(user_id, profile.to_dict())


async def detect_language(text: str) -> str:
    """Detect language from text (simple heuristic)."""
    text_lower = text.lower()

    for lang, indicators in LANGUAGE_INDICATORS.items():
        if any(ind in text_lower for ind in indicators):
            return lang

    return "en"  # Default to English


async def auto_detect_preferences(user_id: int, first_message: str, user_info: Dict) -> UserProfile:
    """Auto-detect preferences from first message and user info.

    Args:
        user_id: Telegram user ID
        first_message: User's first message
        user_info: Telegram user object

    Returns:
        Created/updated profile with detected preferences
    """
    # Detect language
    language = await detect_language(first_message)

    # Extract name from Telegram user info
    name = user_info.get("first_name") or user_info.get("username")

    # Create profile with detected preferences
    profile = await create_profile(user_id, name=name)
    await update_profile(user_id, {
        "language": language,
        "name": name
    })

    logger.info("preferences_auto_detected", user_id=user_id, language=language)
    return profile


def format_profile_display(profile: UserProfile) -> str:
    """Format profile for Telegram display."""
    lines = ["<b>Your Profile</b>\n"]

    lines.append(f"👤 <b>Name:</b> {profile.name or 'Not set'}")
    lines.append(f"🌍 <b>Language:</b> {profile.language}")
    lines.append(f"🕐 <b>Timezone:</b> {profile.timezone}")
    lines.append(f"💬 <b>Tone:</b> {profile.tone}")
    lines.append(f"📏 <b>Response length:</b> {profile.communication.response_length}")
    lines.append(f"😀 <b>Emoji:</b> {'Enabled' if profile.communication.use_emoji else 'Disabled'}")

    if profile.domain:
        lines.append(f"🏢 <b>Domain:</b> {', '.join(profile.domain)}")
    if profile.tech_stack:
        lines.append(f"🛠 <b>Tech stack:</b> {', '.join(profile.tech_stack)}")

    lines.append(f"\n<i>Onboarded:</i> {'Yes' if profile.onboarded else 'No'}")

    return "\n".join(lines)


async def delete_profile(user_id: int) -> bool:
    """Delete user profile (for /forget command)."""
    try:
        db = get_db()
        db.collection("user_profiles").document(str(user_id)).delete()

        # Invalidate cache
        state = get_state_manager()
        await state.invalidate("user_profiles", str(user_id))

        logger.info("profile_deleted", user_id=user_id)
        return True
    except Exception as e:
        logger.error("profile_delete_error", user_id=user_id, error=str(e)[:50])
        return False

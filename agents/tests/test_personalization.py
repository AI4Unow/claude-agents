"""Functional tests for personalization system."""
import sys
sys.path.insert(0, '.')

import asyncio


def test_user_profile_model():
    """Test UserProfile model."""
    from src.models.personalization import UserProfile, CommunicationPrefs
    profile = UserProfile(
        user_id=12345,
        name="Test User",
        tone="concise",
        domain=["backend", "devops"],
        tech_stack=["python", "typescript"]
    )
    assert profile.user_id == 12345
    assert profile.tone == "concise"
    profile_dict = profile.to_dict()
    assert "user_id" in profile_dict
    profile2 = UserProfile.from_dict(profile_dict)
    assert profile2.name == "Test User"
    print("✓ UserProfile model works correctly")


def test_work_context_model():
    """Test WorkContext model."""
    from src.models.personalization import WorkContext
    context = WorkContext(
        user_id=12345,
        current_project="my-project",
        current_task="implementing auth"
    )
    assert context.current_project == "my-project"
    context_dict = context.to_dict()
    context2 = WorkContext.from_dict(context_dict)
    assert context2.current_task == "implementing auth"
    print("✓ WorkContext model works correctly")


def test_macro_model():
    """Test Macro model."""
    from src.models.personalization import Macro
    macro = Macro(
        macro_id="abc123",
        user_id=12345,
        trigger_phrases=["deploy", "ship it"],
        action_type="command",
        action="modal deploy main.py",
        use_count=5
    )
    assert macro.trigger_phrases[0] == "deploy"
    macro_dict = macro.to_dict()
    macro2 = Macro.from_dict(macro_dict)
    assert macro2.use_count == 5
    print("✓ Macro model works correctly")


def test_personal_context():
    """Test PersonalContext aggregation."""
    from src.models.personalization import PersonalContext, UserProfile, WorkContext
    profile = UserProfile(user_id=12345, name="Test")
    context = WorkContext(user_id=12345, current_project="test")

    ctx = PersonalContext(profile=profile, work_context=context)
    assert ctx.is_onboarded == False  # Not onboarded yet
    profile.onboarded = True
    ctx2 = PersonalContext(profile=profile)
    assert ctx2.is_onboarded == True
    print("✓ PersonalContext aggregation works correctly")


def test_formatting_functions():
    """Test formatting functions."""
    from src.models.personalization import UserProfile, WorkContext, Macro
    from src.services.user_profile import format_profile_display
    from src.services.user_context import format_context_display
    from src.services.user_macros import format_macro_display, format_macros_list

    profile = UserProfile(user_id=12345, name="Test User", tone="concise")
    context = WorkContext(user_id=12345, current_project="my-project")
    macro = Macro(
        macro_id="abc123", user_id=12345,
        trigger_phrases=["deploy"], action_type="command",
        action="git push", use_count=5
    )

    profile_html = format_profile_display(profile)
    assert "<b>Your Profile</b>" in profile_html
    assert "Test User" in profile_html

    context_html = format_context_display(context)
    assert "<b>Work Context</b>" in context_html
    assert "my-project" in context_html

    macro_html = format_macro_display(macro)
    assert "abc123" in macro_html
    assert "deploy" in macro_html

    macros_list = format_macros_list([macro])
    assert "Your Macros" in macros_list
    empty_list = format_macros_list([])
    assert "No macros" in empty_list
    print("✓ Formatting functions work correctly")


def test_cosine_similarity():
    """Test cosine similarity."""
    from src.services.user_macros import _cosine_similarity
    v1 = [1.0, 0.0, 0.0]
    v2 = [1.0, 0.0, 0.0]
    v3 = [0.0, 1.0, 0.0]
    assert _cosine_similarity(v1, v2) == 1.0
    assert _cosine_similarity(v1, v3) == 0.0
    print("✓ Cosine similarity works correctly")


def test_dangerous_command_detection():
    """Test dangerous command blocking."""
    from src.core.macro_executor import _execute_command
    from src.models.personalization import Macro

    # Safe command
    safe_macro = Macro(
        macro_id="safe", user_id=123,
        trigger_phrases=["test"], action_type="command",
        action="git status",
    )
    safe_result = asyncio.run(_execute_command(safe_macro, {}, 0))
    assert "🔧" in safe_result
    assert "blocked" not in safe_result.lower()

    # Dangerous command (sudo)
    dangerous_macro = Macro(
        macro_id="danger", user_id=123,
        trigger_phrases=["test"], action_type="command",
        action="sudo apt install",
    )
    danger_result = asyncio.run(_execute_command(dangerous_macro, {}, 0))
    assert "⚠️" in danger_result
    assert "blocked" in danger_result.lower()
    print("✓ Dangerous command detection works correctly")


def test_data_deletion_formatting():
    """Test data deletion formatting."""
    from src.services.data_deletion import format_deletion_result
    results = {
        "profile": "deleted",
        "context": "deleted",
        "cache": "invalidated",
        "error_test": "error: something"
    }
    deletion_html = format_deletion_result(results)
    assert "✅" in deletion_html
    assert "❌" in deletion_html  # For the error case
    assert "Data Deletion Complete" in deletion_html
    print("✓ Data deletion formatting works correctly")


def test_suggestions_formatting():
    """Test suggestions formatting."""
    from src.core.suggestions import format_suggestions_display
    suggestions = ["💡 Try skill X", "⏰ Reminder: check email"]
    formatted = format_suggestions_display(suggestions)
    assert "Suggestions" in formatted
    assert "Try skill X" in formatted

    empty_suggestions = format_suggestions_display([])
    assert "No suggestions" in empty_suggestions
    print("✓ Suggestions formatting works correctly")


def test_activity_formatting():
    """Test activity formatting."""
    from src.services.activity import format_activity_display, format_stats_display
    activities = [
        {"action_type": "chat", "summary": "Hello world"},
        {"action_type": "skill_invoke", "skill": "planning", "summary": "Create auth"},
    ]
    activity_html = format_activity_display(activities)
    assert "Recent Activity" in activity_html
    assert "💬" in activity_html
    assert "🔧" in activity_html

    stats = {"total": 100, "skill_invocations": 50, "top_skills": [("planning", 20)]}
    stats_html = format_stats_display(stats)
    assert "Activity Stats" in stats_html
    assert "100" in stats_html
    print("✓ Activity formatting works correctly")


if __name__ == "__main__":
    print("=== Personalization System Functional Tests ===\n")

    test_user_profile_model()
    test_work_context_model()
    test_macro_model()
    test_personal_context()
    test_formatting_functions()
    test_cosine_similarity()
    test_dangerous_command_detection()
    test_data_deletion_formatting()
    test_suggestions_formatting()
    test_activity_formatting()

    print("\n" + "=" * 50)
    print("All 10 functional tests passed! ✅")
    print("=" * 50)

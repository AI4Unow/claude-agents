"""Admin commands: user management, FAQ, and system control."""
from commands.router import command_router


@command_router.command(
    name="/grant",
    description="Grant tier to user",
    usage="/grant <user_id> <tier>",
    permission="admin",
    category="admin"
)
async def grant_command(args: str, user: dict, chat_id: int) -> str:
    """Grant tier to a user."""
    parts = args.split()
    if len(parts) != 2:
        return "Usage: /grant <user_id> <tier>\n\nTiers: user, developer"

    target_id_str, tier = parts
    try:
        target_id = int(target_id_str)
    except ValueError:
        return "❌ Invalid user ID. Must be a number."

    valid_tiers = ["user", "developer"]
    if tier not in valid_tiers:
        return f"❌ Invalid tier. Choose from: {', '.join(valid_tiers)}"

    from src.services.firebase import set_user_tier
    from src.core.state import get_state_manager

    success = await set_user_tier(target_id, tier, user.get("id"))

    if success:
        state = get_state_manager()
        await state.invalidate_user_tier(target_id)
        return f"✓ Granted <b>{tier}</b> tier to user {target_id}"

    return "❌ Failed to grant tier. Check logs."


@command_router.command(
    name="/revoke",
    description="Revoke user tier (reset to guest)",
    usage="/revoke <user_id>",
    permission="admin",
    category="admin"
)
async def revoke_command(args: str, user: dict, chat_id: int) -> str:
    """Revoke user's tier."""
    if not args:
        return "Usage: /revoke <user_id>"

    try:
        target_id = int(args.strip())
    except ValueError:
        return "❌ Invalid user ID. Must be a number."

    from src.services.firebase import remove_user_tier
    from src.core.state import get_state_manager

    success = await remove_user_tier(target_id)

    if success:
        state = get_state_manager()
        await state.invalidate_user_tier(target_id)
        return f"✓ Revoked access for user {target_id}. Now guest tier."

    return "❌ Failed to revoke tier."


@command_router.command(
    name="/faq",
    description="Manage FAQ entries (add, edit, delete, list)",
    usage="/faq <add|edit|delete|list|refresh>",
    permission="admin",
    category="admin"
)
async def faq_command(args: str, user: dict, chat_id: int) -> str:
    """Manage FAQ entries."""
    from src.services.firebase import (
        get_faq_entries, create_faq_entry, update_faq_entry,
        delete_faq_entry, FAQEntry
    )
    from src.services.qdrant import upsert_faq_embedding, delete_faq_embedding, get_text_embedding
    from src.core.faq import get_faq_matcher
    import re

    parts = args.split(maxsplit=1) if args else []
    subcmd = parts[0].lower() if parts else ""

    if not subcmd or subcmd == "help":
        return (
            "<b>FAQ Commands:</b>\n\n"
            "/faq list - List all FAQ entries\n"
            "/faq add <pattern> | <answer> - Add FAQ\n"
            "/faq edit <id> | <answer> - Update answer\n"
            "/faq delete <id> - Disable FAQ entry\n"
            "/faq refresh - Refresh FAQ cache"
        )

    elif subcmd == "list":
        entries = await get_faq_entries(enabled_only=False)
        if not entries:
            return "No FAQ entries found."

        lines = ["<b>FAQ Entries:</b>\n"]
        for e in entries[:20]:  # Limit to 20
            status = "✓" if e.enabled else "✗"
            pattern_preview = e.patterns[0][:25] if e.patterns else "?"
            lines.append(f"{status} <code>{e.id}</code>\n   {pattern_preview}...")

        if len(entries) > 20:
            lines.append(f"\n... and {len(entries) - 20} more")

        return "\n".join(lines)

    elif subcmd == "add":
        # Format: /faq add <pattern> | <answer>
        if len(parts) < 2 or "|" not in parts[1]:
            return "Usage: /faq add <pattern> | <answer>"

        content = parts[1]
        pipe_idx = content.index("|")
        pattern = content[:pipe_idx].strip()
        answer = content[pipe_idx + 1:].strip()

        if not pattern or not answer:
            return "❌ Both pattern and answer are required."

        # Generate ID from pattern
        faq_id = re.sub(r'[^a-z0-9]+', '-', pattern.lower())[:30]

        # Generate embedding
        embedding = await get_text_embedding(answer)

        entry = FAQEntry(
            id=faq_id,
            patterns=[pattern],
            answer=answer,
            category="custom",
            enabled=True,
            embedding=embedding
        )

        success = await create_faq_entry(entry)
        if success:
            # Sync to Qdrant if embedding exists
            if embedding:
                await upsert_faq_embedding(faq_id, embedding, answer)
            get_faq_matcher().invalidate_cache()
            return f"✓ Created FAQ: <code>{faq_id}</code>"
        else:
            return "❌ Failed to create FAQ entry."

    elif subcmd == "edit":
        # Format: /faq edit <id> | <answer>
        if len(parts) < 2 or "|" not in parts[1]:
            return "Usage: /faq edit <id> | <answer>"

        content = parts[1]
        pipe_idx = content.index("|")
        faq_id = content[:pipe_idx].strip()
        new_answer = content[pipe_idx + 1:].strip()

        if not faq_id or not new_answer:
            return "❌ Both ID and answer are required."

        # Generate new embedding
        embedding = await get_text_embedding(new_answer)

        updates = {"answer": new_answer}
        if embedding:
            updates["embedding"] = embedding

        success = await update_faq_entry(faq_id, updates)
        if success:
            # Update Qdrant
            if embedding:
                await upsert_faq_embedding(faq_id, embedding, new_answer)
            get_faq_matcher().invalidate_cache()
            return f"✓ Updated FAQ: <code>{faq_id}</code>"
        else:
            return f"❌ FAQ entry <code>{faq_id}</code> not found."

    elif subcmd == "delete":
        if len(parts) < 2:
            return "Usage: /faq delete <id>"

        faq_id = parts[1].strip()
        success = await delete_faq_entry(faq_id)

        if success:
            await delete_faq_embedding(faq_id)
            get_faq_matcher().invalidate_cache()
            return f"✓ Disabled FAQ: <code>{faq_id}</code>"
        else:
            return f"❌ FAQ entry <code>{faq_id}</code> not found."

    elif subcmd == "refresh":
        get_faq_matcher().invalidate_cache()
        return "✓ FAQ cache invalidated. Will refresh on next query."

    else:
        return f"❓ Unknown FAQ command: {subcmd}\nUse /faq for help."


@command_router.command(
    name="/admin",
    description="System control commands (reset circuits)",
    usage="/admin <reset> <circuit|all>",
    permission="admin",
    category="admin"
)
async def admin_command(args: str, user: dict, chat_id: int) -> str:
    """Admin system control commands."""
    from src.core.resilience import reset_circuit, reset_all_circuits

    if not args:
        return (
            "<b>Admin Commands:</b>\n\n"
            "/admin reset <circuit> - Reset specific circuit\n"
            "/admin reset all - Reset all circuits"
        )

    parts = args.split()
    subcmd = parts[0].lower() if parts else ""

    if subcmd == "reset":
        if len(parts) < 2:
            return "Usage: /admin reset <circuit_name|all>"

        target = parts[1].lower()
        if target == "all":
            reset_all_circuits()
            return "✓ All circuits have been reset."
        else:
            if reset_circuit(target):
                return f"✓ Circuit <b>{target}</b> has been reset."
            else:
                return (
                    f"❌ Circuit <b>{target}</b> not found.\n\n"
                    "Available: exa_api, tavily_api, firebase, qdrant, claude_api, telegram_api, gemini_api"
                )

    return "❓ Unknown admin command. Use /admin for help."

# Phase 4: Admin Commands

## Context
- Parent: [plan.md](./plan.md)
- Depends on: [Phase 1](./phase-01-faq-core.md)

## Overview
- **Date:** 2025-12-30
- **Description:** Add Telegram admin commands for FAQ management
- **Priority:** P2
- **Implementation Status:** pending
- **Review Status:** pending

## Key Insights
- Admin only (check ADMIN_TELEGRAM_ID)
- Use pipe separator for multi-part args
- Auto-generate embeddings on create

## Requirements
1. `/faq list` - List all entries
2. `/faq add <patterns> | <answer>` - Add new entry
3. `/faq edit <id> | <answer>` - Update answer
4. `/faq delete <id>` - Disable entry

## Related Code Files
- `main.py` - Add command handlers in handle_command()

## Implementation Steps

### 1. Add FAQ Commands (main.py)
```python
# In handle_command() function

elif cmd == "/faq":
    # Admin only
    admin_id = os.environ.get("ADMIN_TELEGRAM_ID")
    if str(user.get("id")) != str(admin_id):
        return "Admin only command."

    if not args:
        return """<b>FAQ Management</b>

/faq list - List all entries
/faq add <patterns> | <answer> - Add entry
/faq edit <id> | <answer> - Update answer
/faq delete <id> - Disable entry

<i>Patterns: comma-separated keywords</i>"""

    parts = args.split(maxsplit=1)
    subcmd = parts[0].lower()
    subargs = parts[1] if len(parts) > 1 else ""

    if subcmd == "list":
        return await _faq_list()
    elif subcmd == "add":
        return await _faq_add(subargs)
    elif subcmd == "edit":
        return await _faq_edit(subargs)
    elif subcmd == "delete":
        return await _faq_delete(subargs)
    else:
        return "Unknown subcommand. Use: list, add, edit, delete"
```

### 2. Implement Subcommands
```python
async def _faq_list() -> str:
    """List all FAQ entries."""
    from src.services.firebase import get_faq_entries

    entries = await get_faq_entries(enabled_only=False)
    if not entries:
        return "No FAQ entries found."

    lines = ["<b>FAQ Entries</b>\n"]
    for e in entries[:20]:  # Limit display
        status = "✅" if e.enabled else "❌"
        patterns = ", ".join(e.patterns[:3])
        lines.append(f"{status} <code>{e.id}</code>")
        lines.append(f"   {patterns}")
        lines.append(f"   → {e.answer[:50]}...")
        lines.append("")

    if len(entries) > 20:
        lines.append(f"<i>...and {len(entries) - 20} more</i>")

    return "\n".join(lines)


async def _faq_add(args: str) -> str:
    """Add new FAQ entry."""
    if "|" not in args:
        return "Usage: /faq add <patterns> | <answer>"

    patterns_str, answer = args.split("|", 1)
    patterns = [p.strip() for p in patterns_str.split(",")]
    answer = answer.strip()

    if not patterns or not answer:
        return "Both patterns and answer required."

    # Generate ID from first pattern
    faq_id = re.sub(r'[^\w]', '-', patterns[0].lower())[:30]

    from src.services.firebase import create_faq_entry, FAQEntry
    from src.services.qdrant import get_embedding

    # Generate embedding
    embedding = await get_embedding(answer)

    entry = FAQEntry(
        id=faq_id,
        patterns=patterns,
        answer=answer,
        category="custom",
        enabled=True,
        embedding=embedding
    )

    success = await create_faq_entry(entry)
    if success:
        # Invalidate cache
        from src.core.faq import get_faq_matcher
        get_faq_matcher()._cache_expiry = 0
        return f"✅ Added FAQ: <code>{faq_id}</code>"
    return "❌ Failed to add FAQ"


async def _faq_edit(args: str) -> str:
    """Edit FAQ answer."""
    if "|" not in args:
        return "Usage: /faq edit <id> | <new answer>"

    faq_id, answer = args.split("|", 1)
    faq_id = faq_id.strip()
    answer = answer.strip()

    from src.services.firebase import update_faq_entry
    from src.services.qdrant import get_embedding, upsert_faq_embedding

    # Update embedding
    embedding = await get_embedding(answer)

    success = await update_faq_entry(faq_id, {
        "answer": answer,
        "embedding": embedding
    })

    if success:
        await upsert_faq_embedding(faq_id, embedding, answer)
        from src.core.faq import get_faq_matcher
        get_faq_matcher()._cache_expiry = 0
        return f"✅ Updated FAQ: <code>{faq_id}</code>"
    return "❌ FAQ not found or update failed"


async def _faq_delete(args: str) -> str:
    """Disable FAQ entry."""
    faq_id = args.strip()
    if not faq_id:
        return "Usage: /faq delete <id>"

    from src.services.firebase import update_faq_entry

    success = await update_faq_entry(faq_id, {"enabled": False})
    if success:
        from src.core.faq import get_faq_matcher
        get_faq_matcher()._cache_expiry = 0
        return f"✅ Disabled FAQ: <code>{faq_id}</code>"
    return "❌ FAQ not found"
```

## Todo List
- [ ] Add /faq command handler
- [ ] Implement _faq_list()
- [ ] Implement _faq_add()
- [ ] Implement _faq_edit()
- [ ] Implement _faq_delete()
- [ ] Add cache invalidation after changes
- [ ] Test all subcommands

## Success Criteria
- Admin can list all FAQ entries
- Admin can add new FAQ with patterns
- Admin can edit existing FAQ answer
- Admin can disable FAQ entries
- Cache invalidates after changes

## Risk Assessment
- **Non-admin access:** Blocked by tier check
- **Invalid input:** Helpful error messages

## Security Considerations
- Admin-only access (ADMIN_TELEGRAM_ID check)
- Input sanitization for patterns/answers

## Next Steps
→ [Phase 5: Seed Data](./phase-05-seed-data.md)

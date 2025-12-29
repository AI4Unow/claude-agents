"""Telegram message formatting utilities.

Provides HTML conversion, message chunking, and skill result formatting
for Telegram Bot API 4096 character limit.
"""
import re
from typing import List

MAX_MESSAGE_LENGTH = 4096
CODE_BLOCK_PATTERN = r'```(\w+)?\n?([\s\S]*?)```'


def escape_html(text: str) -> str:
    """Escape HTML special characters."""
    return (text
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;"))


def format_code_blocks(text: str) -> str:
    """Convert markdown code blocks to HTML <pre><code>.

    Must run first to protect code content from other transformations.
    Returns text with placeholder markers for code blocks.
    """
    blocks = []

    def replace_block(match):
        lang = match.group(1) or ""
        code = escape_html(match.group(2).strip())
        idx = len(blocks)
        if lang:
            blocks.append(f'<pre><code class="language-{lang}">{code}</code></pre>')
        else:
            blocks.append(f'<pre>{code}</pre>')
        return f"__CODE_BLOCK_{idx}__"

    text = re.sub(CODE_BLOCK_PATTERN, replace_block, text)
    return text, blocks


def restore_code_blocks(text: str, blocks: list) -> str:
    """Restore code block placeholders with actual HTML."""
    for i, block in enumerate(blocks):
        text = text.replace(f"__CODE_BLOCK_{i}__", block)
    return text


def format_inline_code(text: str) -> str:
    """Convert `code` to <code>code</code>."""
    def replace_code(match):
        code = escape_html(match.group(1))
        return f'<code>{code}</code>'
    return re.sub(r'`([^`]+)`', replace_code, text)


def format_bold(text: str) -> str:
    """Convert **bold** and *bold* to <b>bold</b>."""
    # Double asterisks first (more specific)
    text = re.sub(r'\*\*([^*]+)\*\*', r'<b>\1</b>', text)
    # Single asterisks (but not in code blocks or already converted)
    text = re.sub(r'(?<![*<])\*([^*\n]+)\*(?![*>])', r'<b>\1</b>', text)
    return text


def format_italic(text: str) -> str:
    """Convert _italic_ to <i>italic</i>."""
    return re.sub(r'(?<!\w)_([^_]+)_(?!\w)', r'<i>\1</i>', text)


def format_strikethrough(text: str) -> str:
    """Convert ~~strikethrough~~ to <s>strikethrough</s>."""
    return re.sub(r'~~([^~]+)~~', r'<s>\1</s>', text)


def format_links(text: str) -> str:
    """Convert [text](url) to <a href="url">text</a>."""
    return re.sub(r'\[([^\]]+)\]\(([^)]+)\)', r'<a href="\2">\1</a>', text)


def format_headers(text: str) -> str:
    """Convert markdown headers to bold text.

    Telegram HTML doesn't support headers, so we convert to bold.
    """
    # H1-H6 to bold
    text = re.sub(r'^#{1,6}\s+(.+)$', r'<b>\1</b>', text, flags=re.MULTILINE)
    return text


def format_lists(text: str) -> str:
    """Convert markdown lists to plain text with bullets.

    Telegram doesn't render list HTML, so keep as formatted text.
    """
    # Unordered lists: - item or * item (at line start)
    text = re.sub(r'^[\-\*]\s+', '• ', text, flags=re.MULTILINE)
    # Numbered lists: 1. item
    # Keep as-is since they're already readable
    return text


def format_blockquotes(text: str) -> str:
    """Convert > quote to italic text."""
    # Simple blockquote: > text
    text = re.sub(r'^>\s*(.+)$', r'<i>\1</i>', text, flags=re.MULTILINE)
    return text


def markdown_to_html(text: str) -> str:
    """Convert markdown to Telegram HTML.

    Order matters:
    1. Code blocks first (protect from other transformations)
    2. Inline code
    3. Links (before bold/italic to avoid breaking URLs)
    4. Bold, italic, strikethrough
    5. Headers, lists, blockquotes
    6. Restore code blocks
    """
    # Step 1: Extract code blocks with placeholders
    text, code_blocks = format_code_blocks(text)

    # Step 2: Format inline elements (order matters)
    text = format_inline_code(text)
    text = format_links(text)
    text = format_bold(text)
    text = format_italic(text)
    text = format_strikethrough(text)

    # Step 3: Format block elements
    text = format_headers(text)
    text = format_lists(text)
    text = format_blockquotes(text)

    # Step 4: Restore code blocks
    text = restore_code_blocks(text, code_blocks)

    return text


def chunk_message(text: str, max_length: int = MAX_MESSAGE_LENGTH) -> List[str]:
    """Split long message into chunks respecting formatting.

    Tries to split at paragraph boundaries first, then sentences.
    """
    if len(text) <= max_length:
        return [text]

    chunks = []
    current = ""

    # Split by paragraphs first
    paragraphs = text.split("\n\n")

    for para in paragraphs:
        if len(current) + len(para) + 2 <= max_length:
            current += para + "\n\n"
        else:
            if current:
                chunks.append(current.strip())

            # Handle paragraph longer than max_length
            if len(para) > max_length:
                # Split by sentences
                sentences = re.split(r'(?<=[.!?])\s+', para)
                current = ""
                for sentence in sentences:
                    if len(current) + len(sentence) + 1 <= max_length:
                        current += sentence + " "
                    else:
                        if current:
                            chunks.append(current.strip())
                        # If single sentence too long, hard split
                        if len(sentence) > max_length:
                            for i in range(0, len(sentence), max_length - 10):
                                chunks.append(sentence[i:i + max_length - 10])
                            current = ""
                        else:
                            current = sentence + " "
            else:
                current = para + "\n\n"

    if current:
        chunks.append(current.strip())

    return chunks if chunks else [text[:max_length]]


def format_skill_result(skill_name: str, result: str, duration_ms: int) -> str:
    """Format skill execution result with header and footer."""
    header = f"<b>Skill:</b> {skill_name}\n\n"
    footer = f"\n\n<i>Duration: {duration_ms}ms</i>"

    # Calculate available space for result
    overhead = len(header) + len(footer) + 20
    available = MAX_MESSAGE_LENGTH - overhead

    # Escape HTML in result but preserve already-formatted content
    if len(result) > available:
        result = result[:available] + "..."

    return header + result + footer


def format_improvement_proposal(proposal: dict) -> str:
    """Format improvement proposal for Telegram HTML."""
    skill = escape_html(proposal.get("skill_name", "unknown"))
    error = escape_html(proposal.get("error_summary", "")[:300])
    memory = escape_html(proposal.get("proposed_memory_addition", "")[:500])
    error_entry = escape_html(proposal.get("proposed_error_entry", "")[:200])
    proposal_id = proposal.get("id", "?")[:8]

    return f"""🔧 <b>Improvement Proposal</b>

<b>Skill:</b> {skill}

<b>Error:</b>
<pre>{error}</pre>

<b>Proposed Memory Addition:</b>
<pre>{memory}</pre>

<b>Error History Entry:</b>
<pre>{error_entry}</pre>

<i>Proposal ID: {proposal_id}...</i>"""


def build_improvement_keyboard(proposal_id: str) -> list:
    """Build inline keyboard for approve/reject."""
    return [
        [
            {"text": "✅ Approve", "callback_data": f"improve_approve:{proposal_id}"},
            {"text": "❌ Reject", "callback_data": f"improve_reject:{proposal_id}"},
        ]
    ]


async def update_progress_message(
    chat_id: int,
    message_id: int,
    text: str,
    bot_token: str = None,
) -> bool:
    """Update existing message with progress (for streaming).

    Uses edit_message_text to update in-place.
    Rate limited by Telegram to ~30 edits/minute.

    Args:
        chat_id: Telegram chat ID
        message_id: Message ID to update
        text: New message text
        bot_token: Optional bot token override

    Returns:
        True if update successful
    """
    import httpx
    import os

    token = bot_token or os.environ.get("TELEGRAM_BOT_TOKEN")
    url = f"https://api.telegram.org/bot{token}/editMessageText"

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(url, json={
                "chat_id": chat_id,
                "message_id": message_id,
                "text": text,
                "parse_mode": "HTML",
            })
            return response.status_code == 200
    except Exception:
        return False


def format_traces_list(traces: list) -> str:
    """Format list of traces for Telegram.

    Args:
        traces: List of ExecutionTrace objects

    Returns:
        HTML-formatted string
    """
    if not traces:
        return "<i>No traces found.</i>"

    lines = ["<b>Recent Traces</b>\n"]

    for t in traces[:10]:  # Limit to 10
        status_emoji = {"success": "✅", "error": "❌", "timeout": "⏱", "running": "🔄"}.get(t.status, "❓")
        skill = t.skill or "chat"
        # Parse started_at ISO string for time display
        time_part = t.started_at[11:16] if len(t.started_at) > 16 else "?"

        lines.append(f"{status_emoji} <code>{t.trace_id}</code> {skill} ({time_part})")

    lines.append(f"\n<i>Use /trace &lt;id&gt; for details</i>")
    return "\n".join(lines)


def format_trace_detail(trace) -> str:
    """Format single trace detail for Telegram.

    Args:
        trace: ExecutionTrace object

    Returns:
        HTML-formatted string
    """
    if not trace:
        return "<i>Trace not found.</i>"

    status_emoji = {"success": "✅", "error": "❌", "timeout": "⏱", "running": "🔄"}.get(trace.status, "❓")

    lines = [
        f"<b>Trace: {trace.trace_id}</b> {status_emoji}",
        "",
        f"<b>Skill:</b> {trace.skill or 'chat'}",
        f"<b>Status:</b> {trace.status}",
        f"<b>Iterations:</b> {trace.iterations}",
        f"<b>Tools:</b> {len(trace.tool_traces)}",
        f"<b>Started:</b> {trace.started_at[:19].replace('T', ' ')}",
    ]

    if trace.ended_at:
        lines.append(f"<b>Ended:</b> {trace.ended_at[:19].replace('T', ' ')}")

    # Tool summary
    if trace.tool_traces:
        lines.append("\n<b>Tools Used:</b>")
        for tt in trace.tool_traces[:5]:  # Limit to 5
            err = "❌" if tt.is_error else "✓"
            lines.append(f"  {err} {tt.name} ({tt.duration_ms}ms)")
        if len(trace.tool_traces) > 5:
            lines.append(f"  <i>... and {len(trace.tool_traces) - 5} more</i>")

    # Error info
    if trace.metadata.get("error"):
        error_text = escape_html(trace.metadata["error"][:200])
        lines.append(f"\n<b>Error:</b>\n<pre>{error_text}</pre>")

    # Output preview
    if trace.final_output:
        output_preview = escape_html(trace.final_output[:200])
        lines.append(f"\n<b>Output:</b>\n<pre>{output_preview}...</pre>")

    return "\n".join(lines)


def format_circuits_status(circuits: dict) -> str:
    """Format circuit breaker status for Telegram.

    Args:
        circuits: Dict from get_circuit_stats()

    Returns:
        HTML-formatted string
    """
    if not circuits:
        return "<i>No circuits configured.</i>"

    state_emoji = {"closed": "🟢", "open": "🔴", "half_open": "🟡"}

    lines = ["<b>Circuit Breakers</b>\n"]

    for name, stats in circuits.items():
        emoji = state_emoji.get(stats["state"], "⚪")
        state = stats["state"].upper()
        failures = stats.get("failures", 0)
        threshold = stats.get("threshold", 0)

        line = f"{emoji} <b>{name}</b>: {state}"
        if stats["state"] == "open":
            remaining = stats.get("cooldown_remaining", 0)
            line += f" (reset in {remaining}s)"
        elif failures > 0:
            line += f" ({failures}/{threshold} failures)"

        lines.append(line)

    lines.append("\n<i>Use /admin reset &lt;circuit&gt; to reset</i>")
    return "\n".join(lines)


def format_task_status(task: dict) -> str:
    """Format local task status for Telegram.

    Args:
        task: Task dict from Firebase task_queue

    Returns:
        HTML-formatted string
    """
    if not task:
        return "<i>Task not found.</i>"

    status_emoji = {
        "pending": "⏳",
        "processing": "🔄",
        "completed": "✅",
        "failed": "❌"
    }.get(task.get("status", ""), "❓")

    lines = [
        f"<b>Task: {task.get('task_id', '?')[:8]}</b> {status_emoji}",
        "",
        f"<b>Skill:</b> {task.get('skill_name', 'unknown')}",
        f"<b>Status:</b> {task.get('status', 'unknown')}",
    ]

    if task.get("created_at"):
        lines.append(f"<b>Created:</b> {task['created_at'][:19].replace('T', ' ')}")

    if task.get("completed_at"):
        lines.append(f"<b>Completed:</b> {task['completed_at'][:19].replace('T', ' ')}")

    if task.get("status") == "completed" and task.get("result"):
        result_preview = escape_html(str(task["result"])[:300])
        lines.append(f"\n<b>Result:</b>\n<pre>{result_preview}</pre>")

    if task.get("status") == "failed" and task.get("error"):
        error_text = escape_html(task["error"][:200])
        lines.append(f"\n<b>Error:</b>\n<pre>{error_text}</pre>")

    return "\n".join(lines)


async def send_with_progress(
    chat_id: int,
    initial_text: str,
    bot_token: str = None,
) -> int:
    """Send initial message and return message_id for progress updates.

    Args:
        chat_id: Telegram chat ID
        initial_text: Initial message text
        bot_token: Optional bot token override

    Returns:
        message_id for subsequent updates, 0 if failed
    """
    import httpx
    import os

    token = bot_token or os.environ.get("TELEGRAM_BOT_TOKEN")
    url = f"https://api.telegram.org/bot{token}/sendMessage"

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(url, json={
                "chat_id": chat_id,
                "text": initial_text,
                "parse_mode": "HTML",
            })
            if response.status_code == 200:
                return response.json()["result"]["message_id"]
            return 0
    except Exception:
        return 0

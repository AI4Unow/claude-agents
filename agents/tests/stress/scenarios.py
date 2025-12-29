"""Message content generators for realistic stress test scenarios."""

import random
from typing import List

# Simple messages - greetings, quick questions
SIMPLE_MESSAGES = [
    "hi",
    "hello",
    "hey there",
    "thanks",
    "ok",
    "thank you!",
    "what is Python?",
    "who made this bot?",
    "how are you?",
    "help me",
    "what can you do?",
    "hello bot",
    "good morning",
    "quick question",
    "yes",
    "no",
]

# Complex messages - trigger orchestrator/multi-skill
COMPLEX_MESSAGES = [
    "build a login system with OAuth and JWT authentication",
    "analyze this codebase and suggest security improvements",
    "create a REST API for user management with CRUD operations",
    "review my code for security vulnerabilities and performance issues",
    "design a database schema for an e-commerce platform",
    "help me refactor this legacy code to use modern patterns",
    "write unit tests for the authentication module",
    "debug this error and explain the root cause",
    "plan the implementation of a real-time notification system",
    "optimize the database queries for better performance",
]

# Translate requests
TRANSLATE_TEXTS = [
    "Hello world, how are you today?",
    "The quick brown fox jumps over the lazy dog",
    "Machine learning is a subset of artificial intelligence",
    "Python is a versatile programming language",
    "Good morning, have a great day!",
]

# Summarize requests (longer texts)
SUMMARIZE_TEXTS = [
    "Artificial intelligence has revolutionized many industries. From healthcare to finance, "
    "AI is being used to automate tasks, make predictions, and improve decision-making. "
    "Machine learning, a subset of AI, allows computers to learn from data without being "
    "explicitly programmed. Deep learning, which uses neural networks, has enabled breakthroughs "
    "in image recognition, natural language processing, and autonomous vehicles.",

    "The history of computing spans several decades. Starting from mechanical calculators "
    "to modern quantum computers, the evolution has been remarkable. Key milestones include "
    "the development of transistors, integrated circuits, microprocessors, and the internet. "
    "Today, computing is ubiquitous and essential to daily life.",
]

# Rewrite requests
REWRITE_TEXTS = [
    "This code is bad and doesnt work good",
    "The meeting was long and boring nobody paid attention",
    "We need to do the thing before the deadline",
    "The system is broken and needs fixing asap",
]

# Reminder time formats
REMINDER_TIMES = ["30m", "1h", "2h", "1d", "3d", "1w"]
REMINDER_MESSAGES = [
    "Check emails",
    "Team meeting",
    "Review PR",
    "Deploy to production",
    "Follow up with client",
    "Update documentation",
]

# Skill names for /skill command
SKILL_NAMES = [
    "research",
    "planning",
    "debugging",
    "code-review",
    "backend-development",
    "frontend-development",
    "ui-ux-pro-max",
    "databases",
]


def get_simple_message() -> str:
    """Get random simple message."""
    return random.choice(SIMPLE_MESSAGES)


def get_complex_message() -> str:
    """Get random complex message."""
    return random.choice(COMPLEX_MESSAGES)


def get_translate_text() -> str:
    """Get text for translation."""
    return random.choice(TRANSLATE_TEXTS)


def get_summarize_text() -> str:
    """Get text for summarization."""
    return random.choice(SUMMARIZE_TEXTS)


def get_rewrite_text() -> str:
    """Get text for rewriting."""
    return random.choice(REWRITE_TEXTS)


def get_reminder() -> tuple:
    """Get reminder time and message."""
    return random.choice(REMINDER_TIMES), random.choice(REMINDER_MESSAGES)


def get_skill_name() -> str:
    """Get random skill name."""
    return random.choice(SKILL_NAMES)


def get_guest_command() -> str:
    """Get random guest-tier command."""
    commands = ["/start", "/help", "/status", "/skills", "/mode", "/cancel", "/clear"]
    return random.choice(commands)


def get_user_command() -> str:
    """Get random user-tier command with args."""
    options = [
        f"/translate {get_translate_text()}",
        f"/summarize {get_summarize_text()[:200]}",  # Truncate for command
        f"/rewrite {get_rewrite_text()}",
        f"/skill {get_skill_name()}",
        "/reminders",
    ]
    return random.choice(options)


def get_developer_command() -> str:
    """Get random developer-tier command."""
    commands = ["/traces", "/trace abc123", "/circuits", "/tier"]
    return random.choice(commands)


def get_admin_command(target_user_id: int = None) -> str:
    """Get random admin command."""
    target = target_user_id or random.randint(1_000_000, 1_000_100)
    options = [
        "/admin",
        f"/grant {target} user",
        f"/revoke {target}",
        "/admin reset claude_api",
    ]
    return random.choice(options)

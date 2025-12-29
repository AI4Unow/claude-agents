"""Locust load test definitions for Telegram bot stress testing."""

import json
import random
from locust import HttpUser, task, between, events
from locust.env import Environment

from .config import config
from .users import user_pool, get_commands_for_tier
from .payloads import (
    text_message,
    voice_message,
    image_message,
    document_message,
    callback_query,
)
from .scenarios import (
    get_simple_message,
    get_complex_message,
    get_guest_command,
    get_user_command,
    get_developer_command,
    get_admin_command,
    get_skill_name,
)


class TelegramBotUser(HttpUser):
    """Base class for Telegram bot users."""

    abstract = True
    wait_time = between(1, 5)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.user_id = None
        self.tier = None

    def send_webhook(self, payload: dict, name: str = None):
        """Send payload to webhook endpoint."""
        return self.client.post(
            "/webhook/telegram",
            json=payload,
            headers={"Content-Type": "application/json"},
            name=name or "webhook",
            timeout=config.request_timeout,
        )


class GuestUser(TelegramBotUser):
    """Simulates guest-tier user behavior (80% of traffic)."""

    weight = 80
    wait_time = between(1, 5)

    def on_start(self):
        """Initialize guest user."""
        self.user_id = user_pool.get_user("guest")
        self.tier = "guest"

    @task(10)
    def send_simple_message(self):
        """Most common: greetings, questions."""
        payload = text_message(self.user_id, get_simple_message())
        self.send_webhook(payload, "simple_message")

    @task(3)
    def use_help_command(self):
        """/help, /status, /skills commands."""
        cmd = random.choice(["/help", "/status", "/skills"])
        payload = text_message(self.user_id, cmd)
        self.send_webhook(payload, f"cmd_{cmd[1:]}")

    @task(2)
    def start_command(self):
        """/start for new session."""
        payload = text_message(self.user_id, "/start")
        self.send_webhook(payload, "cmd_start")

    @task(1)
    def mode_command(self):
        """/mode command."""
        mode = random.choice(["simple", "auto", "routed", ""])
        payload = text_message(self.user_id, f"/mode {mode}".strip())
        self.send_webhook(payload, "cmd_mode")


class PowerUser(TelegramBotUser):
    """Simulates user-tier behavior (15% of traffic)."""

    weight = 15
    wait_time = between(2, 8)

    def on_start(self):
        """Initialize power user."""
        self.user_id = user_pool.get_user("user")
        self.tier = "user"

    @task(5)
    def send_complex_task(self):
        """Orchestrated multi-skill tasks."""
        payload = text_message(self.user_id, get_complex_message())
        self.send_webhook(payload, "complex_task")

    @task(3)
    def use_skill_command(self):
        """/skill <name> command."""
        skill = get_skill_name()
        payload = text_message(self.user_id, f"/skill {skill}")
        self.send_webhook(payload, "cmd_skill")

    @task(2)
    def quick_commands(self):
        """/translate, /summarize, /rewrite."""
        cmd = get_user_command()
        payload = text_message(self.user_id, cmd)
        cmd_name = cmd.split()[0][1:]  # Extract command name
        self.send_webhook(payload, f"cmd_{cmd_name}")

    @task(2)
    def use_guest_commands(self):
        """Power users also use guest commands."""
        cmd = get_guest_command()
        payload = text_message(self.user_id, cmd)
        self.send_webhook(payload, f"cmd_{cmd[1:]}")

    @task(1)
    def send_voice(self):
        """Voice message (simulated)."""
        duration = random.randint(5, 30)
        payload = voice_message(self.user_id, duration)
        self.send_webhook(payload, "voice_message")

    @task(1)
    def send_image(self):
        """Image with caption."""
        caption = random.choice(["What's this?", "Analyze this image", "Describe this", None])
        payload = image_message(self.user_id, caption)
        self.send_webhook(payload, "image_message")


class DeveloperUser(TelegramBotUser):
    """Simulates developer-tier behavior (4% of traffic)."""

    weight = 4
    wait_time = between(5, 15)

    def on_start(self):
        """Initialize developer user."""
        self.user_id = user_pool.get_user("developer")
        self.tier = "developer"

    @task(3)
    def check_traces(self):
        """/traces, /trace <id> commands."""
        cmd = random.choice(["/traces", "/trace abc123"])
        payload = text_message(self.user_id, cmd)
        self.send_webhook(payload, "cmd_traces")

    @task(2)
    def check_circuits(self):
        """/circuits command."""
        payload = text_message(self.user_id, "/circuits")
        self.send_webhook(payload, "cmd_circuits")

    @task(2)
    def check_tier(self):
        """/tier command."""
        payload = text_message(self.user_id, "/tier")
        self.send_webhook(payload, "cmd_tier")

    @task(2)
    def use_power_features(self):
        """Developers also use power user features."""
        payload = text_message(self.user_id, get_complex_message())
        self.send_webhook(payload, "complex_task")

    @task(1)
    def send_document(self):
        """Document upload (simulated)."""
        docs = [
            ("report.pdf", "application/pdf"),
            ("data.csv", "text/csv"),
            ("readme.md", "text/markdown"),
        ]
        filename, mime = random.choice(docs)
        payload = document_message(self.user_id, filename, mime)
        self.send_webhook(payload, "document_message")


class AdminUser(TelegramBotUser):
    """Simulates admin behavior (1% of traffic)."""

    weight = 1
    wait_time = between(10, 30)

    def on_start(self):
        """Initialize admin user."""
        self.user_id = user_pool.get_user("admin")
        self.tier = "admin"

    @task(3)
    def admin_commands(self):
        """/admin command."""
        payload = text_message(self.user_id, "/admin")
        self.send_webhook(payload, "cmd_admin")

    @task(2)
    def check_circuits(self):
        """/circuits with potential reset."""
        cmds = ["/circuits", "/admin reset claude_api"]
        payload = text_message(self.user_id, random.choice(cmds))
        self.send_webhook(payload, "cmd_circuits")

    @task(1)
    def tier_management(self):
        """/grant, /revoke commands (with test user IDs)."""
        target = user_pool.get_user("guest")  # Only affect test users
        cmd = random.choice([
            f"/grant {target} user",
            f"/revoke {target}",
        ])
        payload = text_message(self.user_id, cmd)
        self.send_webhook(payload, "cmd_grant_revoke")

    @task(1)
    def developer_tasks(self):
        """Admin also does developer tasks."""
        payload = text_message(self.user_id, get_developer_command())
        self.send_webhook(payload, "dev_task")


class ChaosUser(TelegramBotUser):
    """Injects chaos for resilience testing (included in full mode)."""

    weight = 0  # Disabled by default, enable via CLI
    wait_time = between(10, 30)

    def on_start(self):
        """Initialize chaos user."""
        self.user_id = user_pool.get_user("guest")
        self.tier = "guest"

    @task
    def send_malformed(self):
        """Send malformed JSON."""
        self.client.post(
            "/webhook/telegram",
            data='{"broken": json',
            headers={"Content-Type": "application/json"},
            name="chaos_malformed",
            timeout=5,
        )

    @task
    def send_empty(self):
        """Send empty payload."""
        self.send_webhook({}, "chaos_empty")

    @task
    def burst_requests(self):
        """Send rapid burst of requests."""
        for _ in range(10):
            payload = text_message(self.user_id, "burst")
            self.send_webhook(payload, "chaos_burst")


# Event hooks for custom metrics
@events.request.add_listener
def on_request(request_type, name, response_time, response_length, response, exception, **kwargs):
    """Log request details for debugging."""
    if exception:
        print(f"Request failed: {name} - {exception}")

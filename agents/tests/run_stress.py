#!/usr/bin/env python3
"""CLI runner for Telegram bot stress tests."""

import argparse
import asyncio
import json
import subprocess
import sys
import os
from datetime import datetime
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def run_load_test(args) -> int:
    """Run Locust load test."""
    from tests.stress.config import StressConfig

    config = StressConfig()
    profile = config.get_profile(args.profile) if args.profile else {}

    # Build locust command
    cmd = [
        sys.executable, "-m", "locust",
        "-f", "tests/stress/locustfile.py",
        "--host", args.host,
        "--headless",
        "--users", str(profile.get("users", args.users)),
        "--spawn-rate", str(profile.get("spawn_rate", args.spawn_rate)),
        "--run-time", profile.get("run_time", args.duration),
    ]

    if args.report:
        cmd.extend(["--html", args.report])

    print(f"Running load test: {' '.join(cmd)}")
    print(f"Target: {args.host}")
    print(f"Users: {profile.get('users', args.users)}, Duration: {profile.get('run_time', args.duration)}")
    print("-" * 50)

    result = subprocess.run(cmd)
    return result.returncode


def run_chaos_test(args) -> int:
    """Run chaos engineering tests."""
    print("Running chaos tests...")
    print(f"Target: {args.host}")
    print("-" * 50)

    from tests.stress.chaos import run_chaos_tests

    # Extract base URL from webhook URL
    base_url = args.host.rsplit("/webhook", 1)[0] if "/webhook" in args.host else args.host

    report = asyncio.run(run_chaos_tests(base_url))

    # Print results
    print(json.dumps(report.to_dict(), indent=2))

    # Save report if requested
    if args.report:
        report_path = Path(args.report).with_suffix(".json")
        with open(report_path, "w") as f:
            json.dump(report.to_dict(), f, indent=2)
        print(f"\nReport saved to: {report_path}")

    # Return exit code
    if report.failed > 0:
        print(f"\n❌ {report.failed} chaos tests failed")
        return 1
    else:
        print(f"\n✅ All {report.passed} chaos tests passed")
        return 0


def run_quick_test(args) -> int:
    """Run quick validation test."""
    print("Running quick validation test...")
    print(f"Target: {args.host}")
    print("-" * 50)

    import httpx
    from tests.stress.payloads import text_message
    from tests.stress.users import user_pool

    # Send a few test requests
    user_id = user_pool.get_user("guest")
    tests = [
        ("/start", text_message(user_id, "/start")),
        ("/help", text_message(user_id, "/help")),
        ("simple_msg", text_message(user_id, "hello")),
    ]

    passed = 0
    failed = 0

    with httpx.Client(timeout=30) as client:
        for name, payload in tests:
            try:
                response = client.post(
                    f"{args.host}/webhook/telegram",
                    json=payload,
                    headers={"Content-Type": "application/json"},
                )
                if response.status_code == 200:
                    print(f"  ✅ {name}: {response.status_code}")
                    passed += 1
                else:
                    print(f"  ❌ {name}: {response.status_code}")
                    failed += 1
            except Exception as e:
                print(f"  ❌ {name}: {e}")
                failed += 1

    print("-" * 50)
    print(f"Results: {passed} passed, {failed} failed")

    return 0 if failed == 0 else 1


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Telegram Bot Stress Test Runner",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Quick validation test
  python tests/run_stress.py --mode quick

  # Load test with 100 users for 5 minutes
  python tests/run_stress.py --mode load --users 100 --duration 5m

  # Load test with predefined profile
  python tests/run_stress.py --mode load --profile sustained

  # Chaos engineering tests
  python tests/run_stress.py --mode chaos

  # Full test suite (load + chaos)
  python tests/run_stress.py --mode full --users 50 --duration 2m

Profiles:
  quick     - 50 users, 1 minute
  ramp_up   - 1000 users, 5 minutes (gradual increase)
  sustained - 1000 users, 10 minutes (constant load)
  spike     - 2000 users, 3 minutes (burst traffic)
  soak      - 200 users, 1 hour (long-running stability)
        """
    )

    parser.add_argument(
        "--mode",
        choices=["load", "chaos", "full", "quick"],
        default="quick",
        help="Test mode (default: quick)",
    )
    parser.add_argument(
        "--host",
        default="https://duc-a-nguyen--claude-agents-telegramchatagent-app.modal.run",
        help="Target host URL",
    )
    parser.add_argument(
        "--users",
        type=int,
        default=50,
        help="Number of concurrent users (default: 50)",
    )
    parser.add_argument(
        "--spawn-rate",
        type=int,
        default=10,
        help="Users spawned per second (default: 10)",
    )
    parser.add_argument(
        "--duration",
        default="1m",
        help="Test duration, e.g., 1m, 5m, 1h (default: 1m)",
    )
    parser.add_argument(
        "--profile",
        choices=["quick", "ramp_up", "sustained", "spike", "soak"],
        help="Use predefined test profile",
    )
    parser.add_argument(
        "--report",
        help="Output report file path (HTML for load, JSON for chaos)",
    )

    args = parser.parse_args()

    print("=" * 50)
    print("TELEGRAM BOT STRESS TEST")
    print(f"Mode: {args.mode}")
    print(f"Started: {datetime.now().isoformat()}")
    print("=" * 50 + "\n")

    exit_code = 0

    if args.mode == "quick":
        exit_code = run_quick_test(args)

    elif args.mode == "load":
        exit_code = run_load_test(args)

    elif args.mode == "chaos":
        exit_code = run_chaos_test(args)

    elif args.mode == "full":
        print("Phase 1: Load Test")
        load_result = run_load_test(args)

        print("\nPhase 2: Chaos Test")
        chaos_result = run_chaos_test(args)

        exit_code = max(load_result, chaos_result)

    print(f"\nCompleted: {datetime.now().isoformat()}")
    return exit_code


if __name__ == "__main__":
    sys.exit(main())

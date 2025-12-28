#!/usr/bin/env python3
"""
LinkedIn Lead Tracker: CLI tool to manage and track leads across the funnel.

Provides operations to view, update, and report on leads from Sales Navigator campaigns.

Usage:
    python3 linkedin-lead-tracker.py status           # Show funnel status
    python3 linkedin-lead-tracker.py list [tier]      # List leads by tier
    python3 linkedin-lead-tracker.py update URL STATUS # Update lead status
    python3 linkedin-lead-tracker.py queue-inmail URL  # Add lead to InMail queue
    python3 linkedin-lead-tracker.py report           # Generate weekly report
"""

import argparse
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path
from collections import Counter

from config import (
    LINKEDIN_LEADS_FILE,
    LINKEDIN_INMAIL_QUEUE_FILE,
    LINKEDIN_INMAIL_SENT_FILE,
    LINKEDIN_CONNECTIONS_FILE,
    LINKEDIN_WEEKLY_REPORTS_DIR,
    DATA_DIR,
)

# Valid lead statuses
VALID_STATUSES = [
    "cold",           # Just added, no engagement
    "engaged",        # Liked/commented on their content
    "connect_sent",   # Connection request sent
    "connected",      # Connection accepted
    "inmail_sent",    # InMail sent
    "responded",      # They replied
    "meeting",        # Meeting scheduled
    "qualified",      # Qualified as opportunity
    "disqualified",   # Not a fit
]


def load_leads() -> dict:
    """Load leads from JSON file."""
    if not LINKEDIN_LEADS_FILE.exists():
        return {"leads": {}, "stats": {}}
    try:
        with open(LINKEDIN_LEADS_FILE) as f:
            return json.load(f)
    except Exception:
        return {"leads": {}, "stats": {}}


def save_leads(data: dict):
    """Save leads to JSON file."""
    LINKEDIN_LEADS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(LINKEDIN_LEADS_FILE, 'w') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def load_connections() -> dict:
    """Load connections data."""
    if not LINKEDIN_CONNECTIONS_FILE.exists():
        return {"sent": [], "accepted": []}
    try:
        with open(LINKEDIN_CONNECTIONS_FILE) as f:
            return json.load(f)
    except Exception:
        return {"sent": [], "accepted": []}


def load_inmails() -> dict:
    """Load InMail sent data."""
    if not LINKEDIN_INMAIL_SENT_FILE.exists():
        return {"sent": [], "details": []}
    try:
        with open(LINKEDIN_INMAIL_SENT_FILE) as f:
            return json.load(f)
    except Exception:
        return {"sent": [], "details": []}


def cmd_status(args):
    """Show funnel status summary."""
    data = load_leads()
    leads = data.get("leads", {})
    connections = load_connections()
    inmails = load_inmails()

    # Count by status
    status_counts = Counter(lead.get("status", "unknown") for lead in leads.values())

    # Count by tier
    tier_counts = Counter(lead.get("tier", "unknown") for lead in leads.values())

    print("=" * 50)
    print("LINKEDIN SALES NAVIGATOR - LEAD TRACKER")
    print("=" * 50)
    print()

    print("📊 FUNNEL STATUS")
    print("-" * 30)
    for status in VALID_STATUSES:
        count = status_counts.get(status, 0)
        if count > 0:
            bar = "█" * min(count, 20)
            print(f"  {status:15} {count:4d} {bar}")
    print()

    print("🎯 BY TIER")
    print("-" * 30)
    for tier in ["tier1", "tier2", "tier3"]:
        count = tier_counts.get(tier, 0)
        print(f"  {tier:15} {count:4d}")
    print()

    print("📈 ACTIVITY SUMMARY")
    print("-" * 30)
    print(f"  Total leads:        {len(leads)}")
    print(f"  Connections sent:   {len(connections.get('sent', []))}")
    print(f"  Connections accepted: {len(connections.get('accepted', []))}")
    print(f"  InMails sent:       {len(inmails.get('sent', []))}")

    # Calculate rates
    sent = len(connections.get('sent', []))
    accepted = len(connections.get('accepted', []))
    if sent > 0:
        rate = (accepted / sent) * 100
        print(f"  Connection rate:    {rate:.1f}%")

    inmail_sent = len(inmails.get('sent', []))
    responded = status_counts.get("responded", 0)
    if inmail_sent > 0:
        rate = (responded / inmail_sent) * 100
        print(f"  InMail response:    {rate:.1f}%")

    print()


def cmd_list(args):
    """List leads, optionally filtered by tier."""
    data = load_leads()
    leads = data.get("leads", {})

    tier_filter = args.tier

    print(f"{'URL':<60} {'Tier':<8} {'Status':<15} {'Added':<12}")
    print("-" * 100)

    for url, lead in sorted(leads.items(), key=lambda x: x[1].get("added_date", ""), reverse=True):
        tier = lead.get("tier", "unknown")
        if tier_filter and tier != tier_filter:
            continue

        status = lead.get("status", "unknown")
        added = lead.get("added_date", "unknown")

        # Truncate URL for display
        display_url = url[-58:] if len(url) > 58 else url
        print(f"{display_url:<60} {tier:<8} {status:<15} {added:<12}")


def cmd_update(args):
    """Update lead status."""
    data = load_leads()

    url = args.url
    new_status = args.status

    if new_status not in VALID_STATUSES:
        print(f"Error: Invalid status '{new_status}'")
        print(f"Valid statuses: {', '.join(VALID_STATUSES)}")
        sys.exit(1)

    if url not in data.get("leads", {}):
        # Check if it's a partial match
        matches = [u for u in data.get("leads", {}) if url in u]
        if len(matches) == 1:
            url = matches[0]
        elif len(matches) > 1:
            print(f"Multiple matches for '{url}':")
            for m in matches[:5]:
                print(f"  {m}")
            sys.exit(1)
        else:
            print(f"Error: Lead not found: {url}")
            sys.exit(1)

    old_status = data["leads"][url].get("status", "unknown")
    data["leads"][url]["status"] = new_status
    data["leads"][url]["last_updated"] = datetime.now().isoformat()
    data["leads"][url].setdefault("actions", []).append({
        "date": datetime.now().strftime("%Y-%m-%d"),
        "type": f"status_change:{old_status}->{new_status}"
    })

    save_leads(data)
    print(f"Updated: {url}")
    print(f"  Status: {old_status} -> {new_status}")


def cmd_queue_inmail(args):
    """Add lead to InMail queue."""
    data = load_leads()

    url = args.url

    # Find lead
    if url not in data.get("leads", {}):
        matches = [u for u in data.get("leads", {}) if url in u]
        if len(matches) == 1:
            url = matches[0]
        else:
            print(f"Error: Lead not found: {url}")
            sys.exit(1)

    lead = data["leads"][url]

    # Load or create queue
    queue_data = {"queue": [], "updated": None}
    if LINKEDIN_INMAIL_QUEUE_FILE.exists():
        try:
            with open(LINKEDIN_INMAIL_QUEUE_FILE) as f:
                queue_data = json.load(f)
        except Exception:
            pass

    # Check if already in queue
    existing = [q for q in queue_data.get("queue", []) if q.get("profile_url") == url]
    if existing:
        print(f"Already in queue: {url}")
        return

    # Add to queue
    queue_data.setdefault("queue", []).append({
        "profile_url": url,
        "name": args.name or lead.get("name", ""),
        "company": args.company or lead.get("company", ""),
        "city": args.city or lead.get("city", "Vietnam"),
        "tier": lead.get("tier", "tier2"),
        "added_at": datetime.now().isoformat()
    })
    queue_data["updated"] = datetime.now().isoformat()

    LINKEDIN_INMAIL_QUEUE_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(LINKEDIN_INMAIL_QUEUE_FILE, 'w') as f:
        json.dump(queue_data, f, indent=2, ensure_ascii=False)

    print(f"Added to InMail queue: {url}")
    print(f"  Queue size: {len(queue_data['queue'])}")


def cmd_report(args):
    """Generate weekly report."""
    data = load_leads()
    leads = data.get("leads", {})
    connections = load_connections()
    inmails = load_inmails()

    # Calculate date range
    today = datetime.now()
    week_start = today - timedelta(days=7)

    # Count activity this week
    def is_this_week(date_str):
        try:
            dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
            return dt >= week_start
        except Exception:
            return False

    # Recent leads
    recent_leads = [
        (url, lead) for url, lead in leads.items()
        if is_this_week(lead.get("added_date", "1970-01-01") + "T00:00:00")
    ]

    # Recent connections
    recent_connections = [
        c for c in connections.get("sent", [])
        # Assume they're all recent if we can't track dates
    ]

    # Generate report
    report = f"""# LinkedIn Sales Nav - Week {today.strftime('%W')} Report

## Activity Summary
- Connections Sent: {len(connections.get('sent', []))}
- Connections Accepted: {len(connections.get('accepted', []))} ({len(connections.get('accepted', []))/max(len(connections.get('sent', [])),1)*100:.0f}%)
- InMails Sent: {len(inmails.get('sent', []))}
- New Leads Added: {len(recent_leads)}

## Pipeline Status
"""

    # Add status breakdown
    status_counts = Counter(lead.get("status", "unknown") for lead in leads.values())
    for status in VALID_STATUSES:
        count = status_counts.get(status, 0)
        if count > 0:
            report += f"- {status}: {count}\n"

    report += f"""
## Tier Breakdown
"""
    tier_counts = Counter(lead.get("tier", "unknown") for lead in leads.values())
    for tier in ["tier1", "tier2", "tier3"]:
        report += f"- {tier}: {tier_counts.get(tier, 0)}\n"

    report += f"""
## Next Week Focus
- [ ] Review connection acceptance rate
- [ ] Follow up on pending InMails
- [ ] Add new leads from saved searches

---
Generated: {today.isoformat()}
"""

    # Save report
    LINKEDIN_WEEKLY_REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    report_file = LINKEDIN_WEEKLY_REPORTS_DIR / f"week-{today.strftime('%Y-%W')}.md"
    with open(report_file, 'w') as f:
        f.write(report)

    print(f"Report saved: {report_file}")
    print()
    print(report)


def main():
    parser = argparse.ArgumentParser(description="LinkedIn Lead Tracker")
    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # status
    sub_status = subparsers.add_parser("status", help="Show funnel status")

    # list
    sub_list = subparsers.add_parser("list", help="List leads")
    sub_list.add_argument("tier", nargs="?", help="Filter by tier (tier1, tier2, tier3)")

    # update
    sub_update = subparsers.add_parser("update", help="Update lead status")
    sub_update.add_argument("url", help="Lead profile URL (can be partial)")
    sub_update.add_argument("status", help=f"New status ({', '.join(VALID_STATUSES)})")

    # queue-inmail
    sub_queue = subparsers.add_parser("queue-inmail", help="Add lead to InMail queue")
    sub_queue.add_argument("url", help="Lead profile URL")
    sub_queue.add_argument("--name", help="Contact name")
    sub_queue.add_argument("--company", help="Company name")
    sub_queue.add_argument("--city", help="City (default: Vietnam)")

    # report
    sub_report = subparsers.add_parser("report", help="Generate weekly report")

    args = parser.parse_args()

    if args.command == "status":
        cmd_status(args)
    elif args.command == "list":
        cmd_list(args)
    elif args.command == "update":
        cmd_update(args)
    elif args.command == "queue-inmail":
        cmd_queue_inmail(args)
    elif args.command == "report":
        cmd_report(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()

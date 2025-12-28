#!/usr/bin/env python3
"""
Lead Model for ProCaffe Social Media CRM.

Provides schema, validation, and CRUD operations for leads in Firestore.

Usage:
    from lead_model import create_lead, update_lead, find_lead, calculate_score
"""

import re
import sys
from datetime import datetime, timedelta
from typing import Optional

import firebase_admin
from firebase_admin import credentials, firestore

from config import (
    FIREBASE_SERVICE_ACCOUNT,
    FIREBASE_PROJECT_ID,
    CRM_LEADS_COLLECTION,
    ENGAGEMENT_WEIGHTS,
    LEAD_STATUS_COLD,
    LEAD_TIER_1,
    LEAD_TIER_2,
    LEAD_TIER_3,
)

# Valid platforms
PLATFORMS = ["tiktok", "linkedin", "facebook"]

# Valid statuses
STATUSES = ["cold", "engaged", "contacted", "qualified", "disqualified"]

# Global Firebase instance
_firebase_app = None


def initialize_firebase():
    """Initialize Firebase Admin SDK."""
    global _firebase_app
    if _firebase_app is not None:
        return firestore.client()

    if not FIREBASE_SERVICE_ACCOUNT.exists():
        print(f"ERROR: Service account not found: {FIREBASE_SERVICE_ACCOUNT}")
        sys.exit(1)

    cred = credentials.Certificate(str(FIREBASE_SERVICE_ACCOUNT))
    _firebase_app = firebase_admin.initialize_app(cred, {
        'projectId': FIREBASE_PROJECT_ID,
    })
    return firestore.client()


def normalize_username(username: str) -> str:
    """Normalize username for consistent document IDs."""
    # Remove @ prefix, lowercase, remove special chars
    username = username.lstrip("@").lower()
    username = re.sub(r'[^a-z0-9_.-]', '', username)
    return username


def generate_lead_id(platform: str, username: str) -> str:
    """Generate composite document ID."""
    return f"{platform}_{normalize_username(username)}"


def calculate_engagement_score(interactions: list[dict]) -> int:
    """
    Calculate engagement score based on interactions.

    Score = sum of (weight * recency_multiplier)
    Recency: today=1.0, <7d=0.8, <30d=0.5, older=0.3
    """
    now = datetime.now()
    score = 0

    for interaction in interactions:
        interaction_type = interaction.get("type", "")
        weight = ENGAGEMENT_WEIGHTS.get(interaction_type, 1)

        # Parse date
        date_str = interaction.get("date", "")
        try:
            if "T" in date_str:
                interaction_date = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
            else:
                interaction_date = datetime.strptime(date_str, "%Y-%m-%d")
        except (ValueError, TypeError):
            interaction_date = now - timedelta(days=30)  # Default to old

        # Calculate recency multiplier
        days_ago = (now - interaction_date.replace(tzinfo=None)).days
        if days_ago <= 1:
            multiplier = 1.0
        elif days_ago <= 7:
            multiplier = 0.8
        elif days_ago <= 30:
            multiplier = 0.5
        else:
            multiplier = 0.3

        score += int(weight * multiplier)

    return score


def determine_tier(score: int) -> str:
    """Determine lead tier based on engagement score."""
    if score >= 30:
        return LEAD_TIER_1
    elif score >= 10:
        return LEAD_TIER_2
    else:
        return LEAD_TIER_3


def create_lead(
    platform: str,
    username: str,
    profile_url: str,
    engagement_type: str,
    name: str = "",
    bio: str = "",
    company: str = "",
    platform_data: dict = None,
) -> dict:
    """
    Create or update a lead in Firestore.

    Returns the lead document.
    """
    if platform not in PLATFORMS:
        raise ValueError(f"Invalid platform: {platform}")

    db = initialize_firebase()
    doc_id = generate_lead_id(platform, username)
    doc_ref = db.collection(CRM_LEADS_COLLECTION).document(doc_id)

    # Check if lead exists
    existing = doc_ref.get()
    now = datetime.now().isoformat()
    today = datetime.now().strftime("%Y-%m-%d")

    if existing.exists:
        # Update existing lead
        data = existing.to_dict()

        # Add new interaction if not already recorded today for this type
        interactions = data.get("interactions", [])
        today_types = {i["type"] for i in interactions if i.get("date", "").startswith(today)}

        if engagement_type not in today_types:
            interactions.append({
                "type": engagement_type,
                "date": today,
            })
            # Keep only last 100 interactions
            interactions = interactions[-100:]

        # Update engagement types list
        engagement_types = list(set(data.get("engagement_types", []) + [engagement_type]))

        # Recalculate score
        score = calculate_engagement_score(interactions)
        tier = determine_tier(score)

        update_data = {
            "engagement_types": engagement_types,
            "interactions": interactions,
            "engagement_score": score,
            "tier": tier,
            "interaction_count": len(interactions),
            "last_interaction": now,
            "updated_at": now,
        }

        # Update name/bio if provided and empty
        if name and not data.get("name"):
            update_data["name"] = name
        if bio and not data.get("bio"):
            update_data["bio"] = bio
        if company and not data.get("company"):
            update_data["company"] = company
        if platform_data:
            update_data["platform_data"] = {**data.get("platform_data", {}), **platform_data}

        doc_ref.update(update_data)
        return {**data, **update_data}

    else:
        # Create new lead
        interactions = [{"type": engagement_type, "date": today}]
        score = calculate_engagement_score(interactions)
        tier = determine_tier(score)

        lead_data = {
            "id": doc_id,
            "platform": platform,
            "username": normalize_username(username),
            "profile_url": profile_url,
            "name": name,
            "bio": bio,
            "company": company,
            "status": LEAD_STATUS_COLD,
            "tier": tier,
            "engagement_score": score,
            "engagement_types": [engagement_type],
            "interaction_count": 1,
            "first_seen": now,
            "last_interaction": now,
            "created_at": now,
            "updated_at": now,
            "platform_data": platform_data or {},
            "interactions": interactions,
            "notes": "",
            "actions": [],
        }

        doc_ref.set(lead_data)
        return lead_data


def find_lead(platform: str, username: str) -> Optional[dict]:
    """Find a lead by platform and username."""
    db = initialize_firebase()
    doc_id = generate_lead_id(platform, username)
    doc_ref = db.collection(CRM_LEADS_COLLECTION).document(doc_id)
    doc = doc_ref.get()

    if doc.exists:
        return doc.to_dict()
    return None


def update_lead_status(platform: str, username: str, status: str) -> bool:
    """Update lead status."""
    if status not in STATUSES:
        raise ValueError(f"Invalid status: {status}")

    db = initialize_firebase()
    doc_id = generate_lead_id(platform, username)
    doc_ref = db.collection(CRM_LEADS_COLLECTION).document(doc_id)

    doc = doc_ref.get()
    if not doc.exists:
        return False

    doc_ref.update({
        "status": status,
        "updated_at": datetime.now().isoformat(),
    })
    return True


def get_leads_by_platform(platform: str, limit: int = 100) -> list[dict]:
    """Get leads for a specific platform."""
    db = initialize_firebase()
    query = db.collection(CRM_LEADS_COLLECTION).where("platform", "==", platform).limit(limit)
    return [doc.to_dict() for doc in query.stream()]


def get_leads_by_tier(tier: str, limit: int = 100) -> list[dict]:
    """Get leads by tier (tier1 = high value)."""
    db = initialize_firebase()
    query = db.collection(CRM_LEADS_COLLECTION).where("tier", "==", tier).limit(limit)
    return [doc.to_dict() for doc in query.stream()]


def get_leads_stats() -> dict:
    """Get aggregate stats for all leads."""
    db = initialize_firebase()
    leads = list(db.collection(CRM_LEADS_COLLECTION).stream())

    stats = {
        "total": len(leads),
        "by_platform": {},
        "by_status": {},
        "by_tier": {},
    }

    for lead in leads:
        data = lead.to_dict()
        platform = data.get("platform", "unknown")
        status = data.get("status", "unknown")
        tier = data.get("tier", "unknown")

        stats["by_platform"][platform] = stats["by_platform"].get(platform, 0) + 1
        stats["by_status"][status] = stats["by_status"].get(status, 0) + 1
        stats["by_tier"][tier] = stats["by_tier"].get(tier, 0) + 1

    return stats


if __name__ == "__main__":
    # Quick test
    print("Testing lead model...")

    # Create test lead
    lead = create_lead(
        platform="tiktok",
        username="test_user_123",
        profile_url="https://tiktok.com/@test_user_123",
        engagement_type="follower",
        name="Test User",
    )
    print(f"Created: {lead['id']} (score: {lead['engagement_score']}, tier: {lead['tier']})")

    # Get stats
    stats = get_leads_stats()
    print(f"Stats: {stats}")

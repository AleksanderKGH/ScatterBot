import os
import json
from typing import Tuple, Optional, Union

XP_FILE = "xp.json"


def _normalize_record(value: Union[dict, int, None]) -> dict:
    """
    Normalize a stored user record into the new schema:
    {"xp": int, "stats": {str: int}}
    """
    if value is None:
        return {"xp": 0, "stats": {}}
    if isinstance(value, int):
        return {"xp": value, "stats": {}}
    if isinstance(value, dict):
        xp_value = value.get("xp", 0)
        stats_value = value.get("stats", {})
        if not isinstance(stats_value, dict):
            stats_value = {}
        return {"xp": int(xp_value or 0), "stats": stats_value}
    return {"xp": 0, "stats": {}}

def load_xp():
    """Load XP data from xp.json. Returns dict of {user_id: record}"""
    if not os.path.exists(XP_FILE):
        return {}
    try:
        with open(XP_FILE, "r") as f:
            data = json.load(f)
            # Convert string keys to int for consistency
            return {int(k): _normalize_record(v) for k, v in data.items()}
    except (json.JSONDecodeError, ValueError):
        print("⚠️ Corrupt XP JSON — resetting to empty.")
        return {}

def save_xp(xp_data):
    """Save XP data to xp.json"""
    with open(XP_FILE, "w") as f:
        json.dump(xp_data, f, indent=2)


def _get_or_create_record(xp_data: dict, user_id: int) -> dict:
    record = _normalize_record(xp_data.get(user_id))
    xp_data[user_id] = record
    return record

def get_user_xp(user_id: int) -> int:
    """Get a specific user's XP total"""
    xp_data = load_xp()
    record = _normalize_record(xp_data.get(user_id))
    return record["xp"]

def add_xp(user_id: int, amount: int = 1):
    """Add XP to a user (floor at 0)"""
    xp_data = load_xp()
    record = _get_or_create_record(xp_data, user_id)
    current = record["xp"]
    new_total = max(0, current + amount)  # Floor at 0
    record["xp"] = new_total
    save_xp(xp_data)
    return new_total

def subtract_xp(user_id: int, amount: int = 1):
    """Subtract XP from a user (convenience wrapper)"""
    return add_xp(user_id, -amount)

def get_leaderboard(limit: int = 10):
    """Get top XP earners. Returns list of (user_id, xp) tuples"""
    xp_data = load_xp()
    sorted_users = sorted(
        xp_data.items(),
        key=lambda x: _normalize_record(x[1])["xp"],
        reverse=True
    )
    return [(user_id, _normalize_record(record)["xp"]) for user_id, record in sorted_users[:limit]]

def get_user_rank(user_id: int) -> Tuple[Optional[int], int]:
    """
    Get user's rank and total XP.
    Returns (rank, xp) where rank is 1-indexed.
    Returns (None, 0) if user has no XP.
    """
    xp_data = load_xp()
    record = _normalize_record(xp_data.get(user_id))
    if user_id not in xp_data or record["xp"] == 0:
        return (None, 0)
    
    sorted_users = sorted(
        xp_data.items(),
        key=lambda x: _normalize_record(x[1])["xp"],
        reverse=True
    )
    for rank, (uid, user_record) in enumerate(sorted_users, start=1):
        if uid == user_id:
            return (rank, _normalize_record(user_record)["xp"])
    
    return (None, 0)


def get_user_stat(user_id: int, stat_key: str) -> int:
    """Get a specific stat value for a user."""
    xp_data = load_xp()
    record = _normalize_record(xp_data.get(user_id))
    return int(record["stats"].get(stat_key, 0) or 0)


def add_stat(user_id: int, stat_key: str, amount: int = 1) -> int:
    """Increment a stat for a user (floored at 0). Returns new total."""
    xp_data = load_xp()
    record = _get_or_create_record(xp_data, user_id)
    current = int(record["stats"].get(stat_key, 0) or 0)
    new_total = max(0, current + amount)
    record["stats"][stat_key] = new_total
    save_xp(xp_data)
    return new_total


def set_stat(user_id: int, stat_key: str, value: int) -> int:
    """Set a stat for a user. Returns stored value."""
    xp_data = load_xp()
    record = _get_or_create_record(xp_data, user_id)
    record["stats"][stat_key] = int(value)
    save_xp(xp_data)
    return record["stats"][stat_key]


def set_stats_bulk(stats_by_user: dict) -> None:
    """Set multiple stats for multiple users in one write."""
    xp_data = load_xp()
    for user_id, stats in stats_by_user.items():
        record = _get_or_create_record(xp_data, int(user_id))
        for stat_key, value in stats.items():
            record["stats"][stat_key] = int(value)
    save_xp(xp_data)

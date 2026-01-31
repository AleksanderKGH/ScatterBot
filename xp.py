import os
import json

XP_FILE = "xp.json"

def load_xp():
    """Load XP data from xp.json. Returns dict of {user_id: xp_amount}"""
    if not os.path.exists(XP_FILE):
        return {}
    try:
        with open(XP_FILE, "r") as f:
            data = json.load(f)
            # Convert string keys to int for consistency
            return {int(k): v for k, v in data.items()}
    except (json.JSONDecodeError, ValueError):
        print("⚠️ Corrupt XP JSON — resetting to empty.")
        return {}

def save_xp(xp_data):
    """Save XP data to xp.json"""
    with open(XP_FILE, "w") as f:
        json.dump(xp_data, f, indent=2)

def get_user_xp(user_id: int) -> int:
    """Get a specific user's XP total"""
    xp_data = load_xp()
    return xp_data.get(user_id, 0)

def add_xp(user_id: int, amount: int = 1):
    """Add XP to a user (floor at 0)"""
    xp_data = load_xp()
    current = xp_data.get(user_id, 0)
    new_total = max(0, current + amount)  # Floor at 0
    xp_data[user_id] = new_total
    save_xp(xp_data)
    return new_total

def subtract_xp(user_id: int, amount: int = 1):
    """Subtract XP from a user (convenience wrapper)"""
    return add_xp(user_id, -amount)

def get_leaderboard(limit: int = 10):
    """Get top XP earners. Returns list of (user_id, xp) tuples"""
    xp_data = load_xp()
    sorted_users = sorted(xp_data.items(), key=lambda x: x[1], reverse=True)
    return sorted_users[:limit]

def get_user_rank(user_id: int) -> tuple[int, int]:
    """
    Get user's rank and total XP.
    Returns (rank, xp) where rank is 1-indexed.
    Returns (None, 0) if user has no XP.
    """
    xp_data = load_xp()
    if user_id not in xp_data or xp_data[user_id] == 0:
        return (None, 0)
    
    sorted_users = sorted(xp_data.items(), key=lambda x: x[1], reverse=True)
    for rank, (uid, xp) in enumerate(sorted_users, start=1):
        if uid == user_id:
            return (rank, xp)
    
    return (None, 0)

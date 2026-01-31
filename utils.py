import discord
from discord import Interaction
from typing import Optional
import config  # Use dynamic access

async def log_action(interaction: discord.Interaction, message: str):
    channel = interaction.client.get_channel(config.LOG_CHANNEL_ID)
    if channel:
        await channel.send(f"📌 {interaction.user.mention}: {message}")
    else:
        print(f"⚠️ Log channel not found: {config.LOG_CHANNEL_ID}")

def require_channel(*required_channel_ids):
    """
    Decorator to restrict commands to specific channels.
    Can accept either a single channel ID or multiple channel IDs.
    """
    async def wrapper(interaction: Interaction):
        if interaction.channel_id not in required_channel_ids:
            if len(required_channel_ids) == 1:
                await interaction.response.send_message(
                    f"❌ This command can only be used in <#{required_channel_ids[0]}>.",
                    ephemeral=True
                )
            else:
                channel_mentions = ", ".join([f"<#{ch_id}>" for ch_id in required_channel_ids])
                await interaction.response.send_message(
                    f"❌ This command can only be used in: {channel_mentions}",
                    ephemeral=True
                )
            return False
        return True
    return wrapper


# Point storage helper functions for backwards compatibility
def create_point(x: float, y: float, color: str, user_id: int = None) -> dict:
    """Create a new point in the current format (dict with optional user_id)."""
    point = {"x": x, "y": y, "color": color.lower()}
    if user_id is not None:
        point["user_id"] = user_id
    return point


def normalize_point(point) -> dict:
    """Convert old list format [x, y, color] to new dict format for consistent access."""
    if isinstance(point, dict):
        return point
    elif isinstance(point, list) and len(point) >= 3:
        return {"x": point[0], "y": point[1], "color": point[2]}
    else:
        raise ValueError(f"Invalid point format: {point}")


def get_point_data(point) -> tuple:
    """Extract (x, y, color) from a point regardless of format."""
    normalized = normalize_point(point)
    return normalized["x"], normalized["y"], normalized["color"]


def get_point_user(point) -> Optional[int]:
    """Get the user_id from a point, or None if not present."""
    normalized = normalize_point(point)
    return normalized.get("user_id")


def get_top_contributors(points: list, limit: int = 3) -> list:
    """
    Returns top contributors as list of tuples: [(user_id, count), ...]
    Points without user_id are counted under None.
    """
    from collections import Counter
    user_counts = Counter()
    
    for point in points:
        user_id = get_point_user(point)
        user_counts[user_id] += 1
    
    # Return top N, excluding None (unknown users) from the list
    return [(user_id, count) for user_id, count in user_counts.most_common(limit + 10) if user_id is not None][:limit]

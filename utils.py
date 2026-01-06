import discord
from discord import Interaction
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

import discord
from discord import Interaction
import config  # Use dynamic access

async def log_action(interaction: discord.Interaction, message: str):
    channel = interaction.client.get_channel(config.LOG_CHANNEL_ID)
    if channel:
        await channel.send(f"📌 {interaction.user.mention}: {message}")
    else:
        print(f"⚠️ Log channel not found: {config.LOG_CHANNEL_ID}")

def require_channel(required_channel_id):
    async def wrapper(interaction: Interaction):
        if interaction.channel_id != required_channel_id:
            await interaction.response.send_message(
                f"❌ This command can only be used in <#{required_channel_id}>.",
                ephemeral=True
            )
            return False
        return True
    return wrapper

from config import LOG_CHANNEL_ID
import discord
from discord import Interaction
from config import POINT_CHANNEL_ID, PLOT_CHANNEL_ID

async def log_action(interaction: discord.Interaction, message: str):
    channel = interaction.client.get_channel(LOG_CHANNEL_ID)
    if channel:
        await channel.send(f"📌 {interaction.user.mention}: {message}")
    else:
        print(f"⚠️ Log channel not found: {LOG_CHANNEL_ID}")

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

def has_role(user: discord.Member, role_id: int) -> bool:
    return any(role.id == role_id for role in user.roles)
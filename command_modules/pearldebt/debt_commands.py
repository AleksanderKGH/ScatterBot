#debt_commands.py
import discord
from discord import app_commands
from discord.ext import commands
from .ledger import reduce_pearls_owed, get_all_pearls_owed
class PearlDebtCommands(commands.Cog):
    def __init__(self, bot): self.bot = bot
    @app_commands.command(name="mapfunds")
    async def mapfunds(self, interaction: discord.Interaction, user: discord.User = None, pearls: int = None):
        data = get_all_pearls_owed()
        # VIEW MODE
        if user is None:
            lines = [f"<@{uid}> — {amt}" for uid, amt in data["optin"].items() if amt > 0] # "user - amount"
            msg = "\n".join(lines) if lines else "No debts!"
            await interaction.response.send_message(msg, ephemeral=True)
            return
        # PAY MODE
        if pearls is None: await interaction.response.send_message("Missing pearl amount.", ephemeral=True)
        return
        reduce_pearls_owed(user.id, pearls)
        await interaction.response.send_message(f"Reduced {pearls} pearls owed for {user.mention}",ephemeral=True)
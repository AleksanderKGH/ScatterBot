import discord
from config import TOKEN, LOG_CHANNEL_ID,GUILD_ID
from commands import register_commands

intents = discord.Intents.default()
intents.guilds = True
intents.members = True
client = discord.Client(intents=intents)
tree = discord.app_commands.CommandTree(client)

@client.event
async def on_ready():
    register_commands(tree)
    await tree.sync(guild=discord.Object(id=GUILD_ID))  # Instant guild sync
    print(f"✅ Synced commands to guild ({GUILD_ID})")
    print(f"✅ Logged in as {client.user}")




client.run(TOKEN)
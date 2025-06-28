import discord
from config import TOKEN
from commands import register_commands

intents = discord.Intents.default()
intents.guilds = True
intents.members = True
client = discord.Client(intents=intents)
tree = discord.app_commands.CommandTree(client)

@client.event
async def on_ready():
    register_commands(tree)
    await tree.sync()
    print(f"✅ Logged in as {client.user}")



client.run(TOKEN)
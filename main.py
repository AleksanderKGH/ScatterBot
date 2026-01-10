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
    await tree.sync()  # Global sync (takes up to 1 hour)
    print(f"✅ Synced commands globally")
    
    # Debug: Print all registered commands  
    all_commands = tree.get_commands()  
    print(f"📋 Registered commands: {[cmd.name for cmd in all_commands]}")
    
    print(f"✅ Logged in as {client.user}")




client.run(TOKEN)
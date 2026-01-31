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
    # Sync to specific guild for instant updates (instead of global 1-hour delay)
    guild = discord.Object(id=GUILD_ID)
    tree.copy_global_to(guild=guild)
    await tree.sync(guild=guild)
    print(f"✅ Synced commands to guild {GUILD_ID}")
    
    # Debug: Print all registered commands  
    all_commands = tree.get_commands(guild=guild)  
    print(f"📋 Registered commands: {[cmd.name for cmd in all_commands]}")
    
    print(f"✅ Logged in as {client.user}")




client.run(TOKEN)
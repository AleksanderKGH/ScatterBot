import discord
import json
import os
from datetime import datetime
from discord.ext import tasks
from config import TOKEN, LOG_CHANNEL_ID, GUILD_ID, PLOT_CHANNEL_ID, POINT_CHANNEL_ID
from commands import register_commands, clear_all_points

intents = discord.Intents.default()
intents.guilds = True
intents.members = True
client = discord.Client(intents=intents)
tree = discord.app_commands.CommandTree(client)

RESET_STATE_FILE = "reset_state.json"
last_reset_date = None


def load_last_reset_date():
    if not os.path.exists(RESET_STATE_FILE):
        return None
    try:
        with open(RESET_STATE_FILE, "r") as f:
            payload = json.load(f)
            return payload.get("last_reset_date")
    except (json.JSONDecodeError, OSError):
        return None


def save_last_reset_date(date_str: str):
    with open(RESET_STATE_FILE, "w") as f:
        json.dump({"last_reset_date": date_str}, f, indent=2)


async def send_reset_messages(goats, daily_stats):
    channels = []
    if PLOT_CHANNEL_ID:
        channels.append(PLOT_CHANNEL_ID)
    if POINT_CHANNEL_ID and POINT_CHANNEL_ID != PLOT_CHANNEL_ID:
        channels.append(POINT_CHANNEL_ID)

    for channel_id in channels:
        channel = client.get_channel(channel_id)
        if channel is None:
            try:
                channel = await client.fetch_channel(channel_id)
            except Exception:
                continue

        if channel_id == PLOT_CHANNEL_ID:
            embed = discord.Embed(
                title="🔄 Pearl Spawns Reset",
                description="The maps have been reset. Please wait for today's pearls to be plotted!",
                color=discord.Color.blue()
            )
            
            # Add daily stats
            if daily_stats:
                stats_text = f"**Total Points:** {daily_stats['total_points']}\n"
                stats_text += f"**Contributors:** {daily_stats['contributors']}\n"
                stats_text += f"**Villages Mapped:** {daily_stats['villages']}"
                embed.add_field(name="📊 Yesterday's Stats", value=stats_text, inline=False)
            
            # Add GOAT celebrations
            if goats:
                goat_lines = [f"🐐 <@{user_id}> — **{count}** points in **{village}**" for user_id, count, village in goats]
                embed.add_field(name="🏆 GOAT Achievements", value="\n".join(goat_lines), inline=False)
            
            embed.set_footer(text="Maps cleared • Good luck mapping today!")
            await channel.send(embed=embed)
        else:
            embed = discord.Embed(
                title="🧹 Maps Cleared",
                description="All village maps have been reset for today.",
                color=discord.Color.green()
            )
            if daily_stats:
                embed.add_field(
                    name="Yesterday's Total",
                    value=f"**{daily_stats['total_points']}** points mapped",
                    inline=False
                )
            await channel.send(embed=embed)

@client.event
async def on_ready():
    global last_reset_date
    register_commands(tree)
    guild = discord.Object(id=GUILD_ID)
    tree.copy_global_to(guild=guild)
    tree.clear_commands(guild=None)
    await tree.sync()
    await tree.sync(guild=guild)
    print(f"✅ Synced commands to guild {GUILD_ID} and cleared global commands")
    
    # Debug: Print all registered commands  
    all_commands = tree.get_commands(guild=guild)  
    print(f"📋 Registered commands: {[cmd.name for cmd in all_commands]}")
    
    print(f"✅ Logged in as {client.user}")

    if last_reset_date is None:
        last_reset_date = load_last_reset_date()
        if last_reset_date is None:
            last_reset_date = datetime.utcnow().strftime("%Y-%m-%d")
            save_last_reset_date(last_reset_date)
    if not reset_loop.is_running():
        reset_loop.start()


@tasks.loop(minutes=1)
async def reset_loop():
    global last_reset_date
    today = datetime.utcnow().strftime("%Y-%m-%d")
    if last_reset_date == today:
        return

    _, goats, daily_stats = clear_all_points()
    await send_reset_messages(goats, daily_stats)
    last_reset_date = today
    save_last_reset_date(today)




client.run(TOKEN)
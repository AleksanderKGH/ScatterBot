import discord
from discord import app_commands, Interaction, ui
import matplotlib.pyplot as plt
import matplotlib.image as mpimg
from PIL import Image
import io, os
import config
from data import load_data, save_data
from utils import log_action, require_channel, create_point, get_point_data, normalize_point, get_top_contributors, get_point_user
from views import ConfirmYesterdayView, ConfirmClearView, UndoPointView, SampleModal
import xp
# https://discord.com/oauth2/authorize?client_id=1385341075572396215&permissions=2147609600
import json
import random
from datetime import datetime, timedelta
from discord import ui


BACKUP_DIR = "backups"
os.makedirs(BACKUP_DIR, exist_ok=True)

def backup_points(data):
    date_key = datetime.utcnow().strftime("%Y-%m-%d")
    path = os.path.join(BACKUP_DIR, f"{date_key}.json")
    with open(path, "w") as f:
        json.dump(data, f, indent=2)

def load_yesterdays_points():
    yesterday = (datetime.utcnow() - timedelta(days=1)).strftime("%Y-%m-%d")
    path = os.path.join(BACKUP_DIR, f"{yesterday}.json")
    if os.path.exists(path):
        with open(path, "r") as f:
            return json.load(f)
    return {}




def generate_plot(village: str, include_fake: bool, user_id: int = None) -> io.BytesIO:
    fig, ax = plt.subplots(figsize=(6, 6))

    # Optional image overlay
    for ext in [".png", ".jpg", ".jpeg"]:
        path = f"{village}{ext}"
        if os.path.exists(path):
            try:
                print(f"Attempting to load: {path}")
                img = Image.open(path)
                ax.imshow(img, extent=[160, -160, -160, 160], zorder=0)
                break
            except Exception as e:
                print(f"Image load failed for {village} at {path}: {e}")
                break

    # Plot actual points
    for point in data[village]:
        x, y, color = get_point_data(point)
        plot_color = config.PLOT_COLORS.get(color.lower(), color.lower())
        # ax.scatter(x, y, color=plot_color, zorder=1)
        ax.scatter(x, y, color=plot_color, s=50, edgecolors='black')
        ax.text(x, y -4, f"({int(x)}, {int(y)})", fontsize=10, color='black', ha='center', va='top')
 
    # Add fake point if needed
    if include_fake and user_id is not None:
        from datetime import datetime
        import random
        date_seed = datetime.utcnow().strftime("%Y-%m-%d")
        random.seed(f"{user_id}-{date_seed}")

        axis_type = random.choice(["x=80", "x=-80", "y=80", "y=-80"])
        if axis_type == "x=80":
            fake_x = 80
            fake_y = random.randint(-160, 160)
        elif axis_type == "x=-80":
            fake_x = -80
            fake_y = random.randint(-160, 160)
        elif axis_type == "y=80":
            fake_y = 80
            fake_x = random.randint(-160, 160)
        else:
            fake_y = -80
            fake_x = random.randint(-160, 160)

        fake_color = random.choice(config.COLOR_OPTIONS).lower()
        fake_plot_color = config.PLOT_COLORS.get(fake_color, fake_color)
        ax.scatter(fake_x, fake_y, color=fake_plot_color, zorder=1)
        ax.text(fake_x, fake_y - 4, f"({int(fake_x)}, {int(fake_y)})", fontsize=10, color='black', ha='center', va='top')
        return_info = (fake_x, fake_y, fake_color)
    else:
        return_info = None

    # Configure plot
    ax.set_title(f"Village: {village}")
    ax.set_xlim(160, -160)
    ax.set_ylim(-160, 160)

    # Set ticks at every 20
    ax.set_xticks([x for x in range(160, -161, -20)])
    ax.set_yticks([y for y in range(-160, 161, 20)])

    # Add grid lines
    ax.grid(True, linestyle="--", linewidth=0.5, color="gray", zorder=0)

    # Add bold origin lines
    ax.axhline(y=0, color='black', linewidth=1)
    ax.axvline(x=0, color='black', linewidth=1)

    # Save to buffer
    buf = io.BytesIO()
    fig.savefig(buf, format="png", bbox_inches='tight', pad_inches=0.2)
    buf.seek(0)
    plt.close(fig)
    return buf, return_info


data = load_data()


def check_milestone(old_value: int, new_value: int) -> int:
    """Check if a milestone was hit. Returns the milestone value or 0."""
    milestones = [100, 200, 300, 400, 500, 600, 700, 800, 900, 1000, 1500, 2000, 2500, 3000, 4000, 5000]
    for milestone in milestones:
        if old_value < milestone <= new_value:
            return milestone
    return 0


async def send_milestone_message(client, user_id: int, milestone_type: str, value: int, detail: str = ""):
    """Send a milestone celebration message to the point channel."""
    channel = client.get_channel(config.POINT_CHANNEL_ID)
    if channel is None:
        try:
            channel = await client.fetch_channel(config.POINT_CHANNEL_ID)
        except Exception:
            return
    
    embed = discord.Embed(
        title="🎉 Milestone Achieved!",
        description=f"<@{user_id}> has reached a new milestone!",
        color=discord.Color.gold()
    )
    
    if detail:
        embed.add_field(name=milestone_type, value=f"**{value}** {detail}", inline=False)
    else:
        embed.add_field(name=milestone_type, value=f"**{value}**", inline=False)
    
    await channel.send(embed=embed)


def clear_all_points():
    global data
    current_data = load_data()
    backup_points(current_data)

    goats = []
    total_points = 0
    contributors = set()
    villages_mapped = 0
    
    for village, points in current_data.items():
        if points:
            villages_mapped += 1
            total_points += len(points)
        
        user_counts = {}
        for point in points:
            user_id = get_point_user(point)
            if user_id:
                user_counts[user_id] = user_counts.get(user_id, 0) + 1
                contributors.add(user_id)
        
        for user_id, count in user_counts.items():
            if count >= 45:
                xp.add_stat(user_id, "goat_points", 1)
                # Only add to public celebration list if not incognito
                is_incognito = xp.get_user_stat(user_id, "incognito") == 1
                if not is_incognito:
                    goats.append((user_id, count, village))

    daily_stats = {
        'total_points': total_points,
        'contributors': len(contributors),
        'villages': villages_mapped
    }

    for village in list(current_data.keys()):
        current_data[village] = []

    save_data(current_data)
    data = current_data
    return current_data, goats, daily_stats

def register_commands(tree: app_commands.CommandTree):

    @tree.command(name="point", description="Add a point to a village!")
    @app_commands.describe(
        x="X coordinate (-160 to 160)",
        y="Y coordinate (-160 to 160)",
        color="Color",
        village="Village name (optional)"
    )
    async def point(interaction: discord.Interaction, x: float, y: float, color: str, village: str = "Dogville"):
        if not await require_channel(config.POINT_CHANNEL_ID)(interaction):
            return
        if not (-160 <= x <= 160) or not (-160 <= y <= 160):
            await interaction.response.send_message(
                f"🚫 Coordinates must be between -160 and 160. You entered: ({x}, {y})",
                ephemeral=True
            )
            return

        # Block 20x20 center zone
        if -10 <= x <= 10 and -10 <= y <= 10:
            await interaction.response.send_message(
                f"🚫 You cannot place points on the bakery! You entered: ({x}, {y})",
                ephemeral=True
            )
            return

        # Only allow valid colors
        if color.lower() not in [c.lower() for c in config.COLOR_OPTIONS]:
            await interaction.response.send_message(
                f"🚫 Invalid color '{color}'. Valid options are: {', '.join(config.COLOR_OPTIONS)}",
                ephemeral=True
            )
            return

        if village not in data:
            data[village] = []

        # Check for duplicate
        if any(
            get_point_data(existing) == (x, y, color.lower())
            for existing in data[village]
        ):
            await interaction.response.send_message(
                f"🚫 That point already exists in '{village}' with the same color.",
                ephemeral=True
            )
            return
        # Check yesterday's data before adding
        # Check yesterday's data
        yesterdays_data = load_yesterdays_points()
        # print(f"Loaded yesterday: {yesterdays_data}")
        y_points = yesterdays_data.get(village, [])
        if any(
            round(get_point_data(existing)[0], 2) == round(x, 2) and
            round(get_point_data(existing)[1], 2) == round(y, 2) and
            get_point_data(existing)[2].lower() == color.lower()
            for existing in y_points
        ):
            view = ConfirmYesterdayView(interaction.user.id)
            embed = discord.Embed(
                title="👀 Pearl Spotted Yesterday",
                description=f"There's already a pearl at ({x}, {y}, {color}) from **yesterday**.\nDid you see it fall from the sky?",
                color=discord.Color.gold()
            )
            await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
            await view.wait()

            if not view.confirmed:
                return




        new_point = create_point(x, y, color, user_id=interaction.user.id)
        data[village].append(new_point)
        save_data(data)

        # Award XP and stats with milestone checking
        old_xp = xp.get_user_xp(interaction.user.id)
        new_xp = xp.add_xp(interaction.user.id, 1)
        
        color_key = f"color_{color.lower()}"
        old_color_count = xp.get_user_stat(interaction.user.id, color_key)
        new_color_count = xp.add_stat(interaction.user.id, color_key, 1)

        # Check for milestones (only if not incognito)
        is_incognito = xp.get_user_stat(interaction.user.id, "incognito") == 1
        
        if not is_incognito:
            xp_milestone = check_milestone(old_xp, new_xp)
            color_milestone = check_milestone(old_color_count, new_color_count)
            
            if xp_milestone:
                await send_milestone_message(interaction.client, interaction.user.id, "Total XP", xp_milestone)
            
            if color_milestone:
                await send_milestone_message(interaction.client, interaction.user.id, f"{color.capitalize()} Pearls", color_milestone, "pearls mapped")

        await log_action(interaction, f"Added ({x}, {y}, {color}) to **{village}**")
        await interaction.response.send_message(f"✅ Added to '{village}' (+1 XP, Total: {new_xp})", ephemeral=True)

    @point.autocomplete("color")
    async def color_autocomplete(interaction: discord.Interaction, current: str):
        return [
            app_commands.Choice(name=color, value=color)
            for color in config.COLOR_OPTIONS if current.lower() in color.lower()
        ]
    @point.autocomplete("village")
    async def village_autocomplete(interaction: discord.Interaction, current: str):
        return [
            app_commands.Choice(name=village, value=village)
            for village in config.VILLAGE_OPTIONS if current.lower() in village.lower()
        ]

    @tree.command(name="plot", description="Plot points from a village.")
    @app_commands.describe(village="Village name (optional)")
    async def plot(interaction: discord.Interaction, village: str = "Dogville"):
        if not await require_channel(config.PLOT_CHANNEL_ID, config.POINT_CHANNEL_ID)(interaction):
            return
        if village not in data or not data[village]:
            await interaction.response.send_message("That village has no data.", ephemeral=True)
            return

        buf, fake_point = generate_plot(village, include_fake=True, user_id=interaction.user.id)
        
        # Get top contributors
        top_contributors = get_top_contributors(data[village], limit=3)
        
        # Build embed with credits
        embed = discord.Embed(
            title=f"🗺️ {village} Pearl Map",
            color=discord.Color.blue()
        )
        
        if top_contributors:
            credits = []
            medals = ["🥇", "🥈", "🥉"]
            for i, (user_id, count) in enumerate(top_contributors):
                medal = medals[i] if i < len(medals) else "🏅"
                credits.append(f"{medal} <@{user_id}>: **{count}** point{'s' if count != 1 else ''}")
            
            embed.add_field(
                name="Top Contributors",
                value="\n".join(credits),
                inline=False
            )
        
        embed.set_footer(text=f"Total points: {len(data[village])}")
        embed.set_image(url="attachment://map.png")
        
        await log_action(
            interaction,
            f"Plotted village **{village}** — fake pearl at `({fake_point[0]}, {fake_point[1]})` in `{fake_point[2]}`"
        )
        
        file = discord.File(buf, "map.png")
        await interaction.response.send_message(embed=embed, file=file, ephemeral=True)
    

    @tree.command(name="plotdetailed", description="Plot a detailed map")
    @app_commands.describe(village="Village name (optional)")
    async def plotpure(interaction: discord.Interaction, village: str = "Dogville"):
        if not await require_channel(config.LOG_CHANNEL_ID)(interaction):
            return
        if village not in data or not data[village]:
            await interaction.response.send_message("That village has no data.", ephemeral=True)
            return

        buf, _ = generate_plot(village, include_fake=False)
        await log_action(interaction, f"Plotted **pure** village map for **{village}**")
        await interaction.response.send_message(file=discord.File(buf, "scatter.png"), ephemeral=True)



    @tree.command(name="clearmaps", description="Clear all points from all villages")
    async def clearmaps(interaction: Interaction):
        if interaction.channel_id != config.LOG_CHANNEL_ID:
            await interaction.response.send_message(
                f"❌ This command can only be used in <#{config.LOG_CHANNEL_ID}>.",
                ephemeral=True
            )
            return

        view = ConfirmClearView(interaction.user.id)
        await interaction.response.send_message(
            "⚠️ Are you sure you want to **clear all points** in every village?", 
            view=view, ephemeral=True
        )

        timeout = await view.wait()

        if not view.confirmed and not timeout:
            await interaction.followup.send("❌ Timed out. No data was cleared.", ephemeral=True)
            return


        _, goats, daily_stats = clear_all_points()
        goat_msg = ""
        if goats:
            goat_lines = [f"🐐 <@{user_id}> mapped **{count}** points in **{village}**!" for user_id, count, village in goats]
            goat_msg = "\n" + "\n".join(goat_lines)
        await interaction.followup.send(f"🧹 All points have been cleared from all villages (villages preserved).{goat_msg}")
    

    @tree.command(name="villages", description="List all tracked villages and how many points are in each")
    async def list_villages(interaction: discord.Interaction):
        if interaction.channel_id != config.POINT_CHANNEL_ID:
                await interaction.response.send_message(
                    f"❌ This command can only be used in <#{config.POINT_CHANNEL_ID}>.",
                    ephemeral=True
                )
                return

        from data import load_data  # Reload in case it was updated externally
        current_data = load_data()

        embed = discord.Embed(
            title="🌾 Tracked Villages",
            description="Here's how many points each village currently has, with color breakdown:",
            color=discord.Color.green()
        )

        for village in config.VILLAGE_OPTIONS:
            points = current_data.get(village, [])
            count = len(points)

            if count == 0:
                embed.add_field(name=f"🏘️ {village}", value="`0` point(s)", inline=False)
                continue

            # Count color distribution
            color_counts = {}
            for point in points:
                _, _, color = get_point_data(point)
                color = color.lower()
                color_counts[color] = color_counts.get(color, 0) + 1

            breakdown = []
            for color, c in sorted(color_counts.items(), key=lambda x: -x[1]):
                percent = (c / count) * 100
                breakdown.append(f"- {color.capitalize()}: {c} ({percent:.0f}%)")

            embed.add_field(
                name=f"🏘️ {village} — `{count}` point{'s' if count != 1 else ''}",
                value="\n".join(breakdown),
                inline=False
            )

        await interaction.response.send_message(embed=embed, ephemeral=True)



    @tree.command(name="undo", description="Remove a point you added to a village")
    @app_commands.describe(village="Village to remove points from")
    @app_commands.autocomplete(village=village_autocomplete)
    async def undo(interaction: discord.Interaction, village: str = "Dogville"):
        from data import load_data
        from utils import get_point_user
        
        # Check channel permissions
        is_admin_channel = interaction.channel_id == config.LOG_CHANNEL_ID
        if not is_admin_channel and interaction.channel_id != config.POINT_CHANNEL_ID:
            await interaction.response.send_message(
                f"❌ This command can only be used in <#{config.POINT_CHANNEL_ID}> or <#{config.LOG_CHANNEL_ID}>.",
                ephemeral=True
            )
            return

        data = load_data()
        
        if village not in data or not data[village]:
            await interaction.response.send_message(
                f"❌ No points to remove from **{village}**.",
                ephemeral=True
            )
            return

        # Filter points based on channel
        if is_admin_channel:
            # Admin mode: show all points
            points_with_indices = [(i, point) for i, point in enumerate(data[village])]
        else:
            # Normal mode: only show user's points
            points_with_indices = [
                (i, point) for i, point in enumerate(data[village])
                if get_point_user(point) == interaction.user.id
            ]
        
        if not points_with_indices:
            if is_admin_channel:
                await interaction.response.send_message(
                    f"❌ No points to remove from **{village}**.",
                    ephemeral=True
                )
            else:
                await interaction.response.send_message(
                    f"❌ You haven't added any points to **{village}** yet.",
                    ephemeral=True
                )
            return

        # Reverse to show newest first
        points_with_indices.reverse()
        
        view = UndoPointView(
            author_id=interaction.user.id,
            village=village,
            points_with_indices=points_with_indices,
            is_admin=is_admin_channel
        )
        
        await interaction.response.send_message(
            embed=view.get_embed(),
            view=view,
            ephemeral=True
        )





    @tree.command(name="noob", description="List all available commands")
    async def noob_command(interaction: discord.Interaction):
        from config import POINT_CHANNEL_ID, PLOT_CHANNEL_ID  # import your channel IDs

        embed = discord.Embed(
            title="📖 PearlMapBot Help",
            description="Here's a breakdown of available commands and their usage:",
            color=discord.Color.blurple()
        )

        embed.add_field(
            name="🎯 /point",
            value=f"Add a point to a village. Earns 1 XP per point added.\nMust be used in <#{POINT_CHANNEL_ID}>.",
            inline=False
        )
        embed.add_field(
            name="🗺️ /plot",
            value=f"Generate a plotted map image. Must be used in <#{PLOT_CHANNEL_ID}>.",
            inline=False
        )
        embed.add_field(
            name="📊 /villages",
            value=f"Shows current tracked village stats (use in <#{POINT_CHANNEL_ID}>).",
            inline=False
        )
        embed.add_field(
            name="♻️ /undo",
            value="Remove points from a village. Admins can remove any point, regular users can only remove their own.",
            inline=False
        )
        embed.add_field(
            name="🌟 /xp",
            value="Check your XP total and server rank. Optionally check another user's XP.",
            inline=False
        )
        embed.add_field(
            name="🏆 /leaderboard",
            value="View the top XP earners on the server (default: top 10).",
            inline=False
        )
        embed.add_field(
            name="🧹 /clearmaps",
            value="Admin-only: Clears all village points. XP is preserved. Requires confirmation.",
            inline=False
        )
        embed.set_footer(text="More features coming soon. Stay crusty 🥖")

        await interaction.response.send_message(embed=embed, ephemeral=True)

    @tree.command(name="residentjson", description="Dumps all users with specific roles as JSON")
    async def resident_json(interaction: discord.Interaction):
        if interaction.channel_id != config.LOG_CHANNEL_ID:
            await interaction.response.send_message(
                f"❌ This command can only be used in <#{config.LOG_CHANNEL_ID}>.",
                ephemeral=True
            )
            return

        guild = interaction.guild
        roles_to_check = [
            config.RESIDENT_ROLE_ID,
            config.PEARL_ROLE_ID
        ]

        residents = []
        for member in guild.members:
            if any(role.id in roles_to_check for role in member.roles):
                resident_info = {
                    "id": member.id,
                    "name": str(member),
                    "roles": [role.name for role in member.roles if role.id in roles_to_check]
                }
                residents.append(resident_info)

        json_data = json.dumps(residents, indent=2)
        buf = io.BytesIO(json_data.encode('utf-8'))
        buf.seek(0)

        await log_action(interaction, "Exported residents as JSON")
        await interaction.response.send_message(
            content="📋 Here is the list of residents with specified roles:",
            file=discord.File(buf, "residents.json"),
            ephemeral=True
        )

    @tree.command(name="residentcsv", description="Exports users with specific roles as CSV (Excel/Sheets compatible)")
    async def resident_csv(interaction: discord.Interaction):
        if interaction.channel_id != config.LOG_CHANNEL_ID:
            await interaction.response.send_message(
                f"❌ This command can only be used in <#{config.LOG_CHANNEL_ID}>.",
                ephemeral=True
            )
            return

        guild = interaction.guild
        roles_to_check = [
            config.RESIDENT_ROLE_ID,
            config.PEARL_ROLE_ID
        ]

        residents = []
        for member in guild.members:
            if any(role.id in roles_to_check for role in member.roles):
                roles_list = [role.name for role in member.roles if role.id in roles_to_check]
                residents.append({
                    "id": member.id,
                    "name": str(member.name),
                    "nickname": str(member.nick) if member.nick else "",
                    "global_name": str(member.global_name),
                    "roles": "; ".join(roles_list)  # Semicolon-separated for CSV safety
                })

        # Build CSV
        import csv
        output = io.StringIO()
        if residents:
            writer = csv.DictWriter(output, fieldnames=["id", "name","nickname", "global_name", "roles"])
            writer.writeheader()
            writer.writerows(residents)
        
        csv_data = output.getvalue()
        buf = io.BytesIO(csv_data.encode('utf-8'))
        buf.seek(0)

        await log_action(interaction, "Exported residents as CSV")
        await interaction.response.send_message(
            content="📊 Here is the CSV file — opens directly in Excel and Google Sheets:",
            file=discord.File(buf, "residents.csv"),
            ephemeral=True
        )

    @tree.command(name="sync", description="Sync commands to the guild (admin only)")
    async def sync_commands(interaction: discord.Interaction):
        if interaction.channel_id != config.LOG_CHANNEL_ID:
            await interaction.response.send_message(
                f"❌ This command can only be used in <#{config.LOG_CHANNEL_ID}>.",
                ephemeral=True
            )
            return

        await tree.sync(guild=discord.Object(id=config.GUILD_ID))
        await interaction.response.send_message("✅ Commands synced to the guild.", ephemeral=True)

    @tree.command(name="xp", description="Check your XP or someone else's XP")
    @app_commands.describe(user="User to check XP for (optional)")
    async def check_xp(interaction: discord.Interaction, user: discord.User = None):
        target_user = user or interaction.user
        
        rank, user_xp = xp.get_user_rank(target_user.id)
        goat_points = xp.get_user_stat(target_user.id, "goat_points")
        color_lines = []
        for color_name in config.COLOR_OPTIONS:
            color_key = color_name.lower()
            color_count = xp.get_user_stat(target_user.id, f"color_{color_key}")
            color_lines.append(f"{color_name}: `{color_count}`")
        
        embed = discord.Embed(
            title=f"🌟 XP Stats for {target_user.display_name}",
            color=discord.Color.gold()
        )
        
        if rank:
            embed.add_field(name="Total XP", value=f"`{user_xp}`", inline=True)
            embed.add_field(name="Server Rank", value=f"`#{rank}`", inline=True)
        else:
            embed.add_field(name="Total XP", value="`0`", inline=True)
            embed.add_field(name="Server Rank", value="`Unranked`", inline=True)

        embed.add_field(name="🐐 GOAT Points", value=f"`{goat_points}`", inline=True)
        embed.add_field(name="Color Stats", value="\n".join(color_lines), inline=False)
        
        embed.set_thumbnail(url=target_user.display_avatar.url)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @tree.command(name="leaderboard", description="View the XP leaderboard")
    @app_commands.describe(limit="Number of top users to show (default: 10)")
    async def leaderboard(interaction: discord.Interaction, limit: int = 10):
        if limit < 1 or limit > 25:
            await interaction.response.send_message("❌ Limit must be between 1 and 25.", ephemeral=True)
            return

        top_users = xp.get_leaderboard(limit * 3)
        top_users = [
            (user_id, user_xp)
            for user_id, user_xp in top_users
            if xp.get_user_stat(user_id, "incognito") != 1
        ][:limit]
        
        if not top_users:
            await interaction.response.send_message("📊 No one has earned XP yet!", ephemeral=True)
            return
        
        embed = discord.Embed(
            title="🏆 XP Leaderboard",
            description=f"Top {len(top_users)} pearl mappers",
            color=discord.Color.gold()
        )
        
        leaderboard_text = []
        for rank, (user_id, user_xp) in enumerate(top_users, start=1):
            medal = "🥇" if rank == 1 else "🥈" if rank == 2 else "🥉" if rank == 3 else f"`{rank}.`"
            leaderboard_text.append(f"{medal} <@{user_id}> — **{user_xp} XP**")
        
        embed.description = "\n".join(leaderboard_text)
        
        # Show where the requesting user ranks if not in top list
        requester_rank, requester_xp = xp.get_user_rank(interaction.user.id)
        if requester_rank and requester_rank > limit:
            embed.set_footer(text=f"Your rank: #{requester_rank} with {requester_xp} XP")
        
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @tree.command(name="incognito", description="Opt in or out of the XP leaderboard")
    @app_commands.describe(enabled="Enable incognito mode (hide from leaderboard)")
    async def incognito(interaction: discord.Interaction, enabled: bool):
        xp.set_stat(interaction.user.id, "incognito", 1 if enabled else 0)
        if enabled:
            message = "🕶️ Incognito enabled. You will be hidden from the leaderboard."
        else:
            message = "👀 Incognito disabled. You will appear on the leaderboard."
        await interaction.response.send_message(message, ephemeral=True)
import discord
from discord import app_commands, Interaction, ui
import matplotlib.pyplot as plt
import matplotlib.image as mpimg
from PIL import Image
import io, os
import config
from data import load_data, save_data
from utils import log_action, require_channel
# https://discord.com/oauth2/authorize?client_id=1385341075572396215&permissions=2147609600
import json
import random
from datetime import datetime, timedelta


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


VILLAGE_OPTIONS = [
    "Dogville",
    "Wheat Street",
    "An Bread Capital",
    "Honey Wheat Hallow",
    "Yeastopia",
    "Harvesta",
    "Kitsune Ville"
]

class ConfirmYesterdayView(discord.ui.View):
    def __init__(self, author_id):
        super().__init__(timeout=30)
        self.author_id = author_id
        self.confirmed = False

    @discord.ui.button(label="✅ Yes, I saw it fall!", style=discord.ButtonStyle.success)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.author_id:
            await interaction.response.send_message("❌ You didn’t start this confirmation.", ephemeral=True)
            return

        self.confirmed = True
        for item in self.children:
            item.disabled = True
        await interaction.response.edit_message(content="📍 Pearl confirmed. Adding to the map...", view=self)
        self.stop()

    @discord.ui.button(label="❌ Nope, don’t add it", style=discord.ButtonStyle.danger)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.author_id:
            await interaction.response.send_message("❌ You didn’t start this confirmation.", ephemeral=True)
            return

        await interaction.response.edit_message(content="❌ Cancelled. Pearl not added.", view=None)
        self.stop()


class ConfirmClearView(ui.View):
    def __init__(self, author_id):
        super().__init__(timeout=30)
        self.author_id = author_id
        self.confirmed = False
    @ui.button(label="✅ Confirm", style=discord.ButtonStyle.danger)
    async def confirm(self, interaction: Interaction, button: ui.Button):
        if interaction.user.id != self.author_id:
            await interaction.response.send_message("❌ You didn't start this confirmation.", ephemeral=True)
            return

        self.confirmed = True
        for item in self.children:
            item.disabled = True
        await interaction.response.edit_message(content="✅ Confirmed. Clearing all points...", view=self)
        self.stop()

    @ui.button(label="❌ Cancel", style=discord.ButtonStyle.secondary)
    async def cancel(self, interaction: Interaction, button: ui.Button):
        if interaction.user.id != self.author_id:
            await interaction.response.send_message("❌ You didn't start this confirmation.", ephemeral=True)
            return

        await interaction.response.edit_message(content="❌ Cancelled. No data was cleared.", view=None)
        self.stop()

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
    for x, y, color in data[village]:
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
        if any(existing[0] == x and existing[1] == y and existing[2] == color.lower() for existing in data[village]):
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
            round(existing[0], 2) == round(x, 2) and
            round(existing[1], 2) == round(y, 2) and
            existing[2].lower() == color.lower()
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




        data[village].append([x, y, color.lower()])
        save_data(data)

        await log_action(interaction, f"Added ({x}, {y}, {color}) to **{village}**")
        await interaction.response.send_message(f"✅ Added to '{village}'", ephemeral=True)

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
            for village in VILLAGE_OPTIONS if current.lower() in village.lower()
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
        await log_action(
            interaction,
            f"Plotted village **{village}** — fake pearl at `({fake_point[0]}, {fake_point[1]})` in `{fake_point[2]}`"
        )
        await interaction.response.send_message(file=discord.File(buf, "scatter.png"), ephemeral=True)
    

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


        backup_points(data)
        data.clear()
        save_data(data)
        # Clear points but keep village keys
        for village in data.keys():
            data[village] = []

        save_data(data)
        await interaction.followup.send("🧹 All points have been cleared from all villages (villages preserved).")
    

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

        for village in VILLAGE_OPTIONS:
            points = current_data.get(village, [])
            count = len(points)

            if count == 0:
                embed.add_field(name=f"🏘️ {village}", value="`0` point(s)", inline=False)
                continue

            # Count color distribution
            color_counts = {}
            for _, _, color in points:
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



    @tree.command(name="undo", description="Undo the last point added to a village")
    @app_commands.describe(village="Village to remove the last point from")
    @app_commands.autocomplete(village=village_autocomplete)  # Optional: use your existing autocomplete
    async def undo(interaction: discord.Interaction, village: str = "Dogville"):
        from data import load_data, save_data
        data = load_data()
        if interaction.channel_id != config.POINT_CHANNEL_ID:
            await interaction.response.send_message(
                f"❌ This command can only be used in <#{config.POINT_CHANNEL_ID}>.",
                ephemeral=True
            )
            return


        if village not in data or not data[village]:
            await interaction.response.send_message(
                f"❌ No points to remove from **{village}**.",
                ephemeral=True
            )
            return

        last_point = data[village].pop()
        save_data(data)

        x, y, color = last_point
        await interaction.response.send_message(
            f"↩️ Removed latest point: ({x}, {y}, {color}) from **{village}**.",
            ephemeral=True
        )
        await log_action(interaction, f"Removed last point ({x}, {y}, {color}) from **{village}**")





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
            value=f"Add a point to a village. Must be used in <#{POINT_CHANNEL_ID}>.\n"
                "Includes coordinate validation and color selection.",
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
            value="Removes the most recently added point.",
            inline=False
        )
        embed.add_field(
            name="🧹 /clearmaps",
            value="Admin-only: Clears all village points. Requires confirmation and must be used in the log channel.",
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
                    "roles": "; ".join(roles_list)  # Semicolon-separated for CSV safety
                })

        # Build CSV
        import csv
        output = io.StringIO()
        if residents:
            writer = csv.DictWriter(output, fieldnames=["id", "name","nickname", "roles"])
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
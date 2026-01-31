import discord
from discord import app_commands, Interaction, ui
import matplotlib.pyplot as plt
import matplotlib.image as mpimg
from PIL import Image
import io, os
import config
from data import load_data, save_data
from utils import log_action, require_channel, create_point, get_point_data, normalize_point, get_top_contributors, get_point_user
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


class UndoPointView(ui.View):
    def __init__(self, author_id, village, points_with_indices, is_admin=False):
        super().__init__(timeout=60)
        self.author_id = author_id
        self.village = village
        self.points_with_indices = points_with_indices  # List of (index, point) tuples
        self.is_admin = is_admin
        self.page = 0
        self.items_per_page = 5
        self.selected_index = None
        self.update_buttons()

    def get_embed(self):
        start = self.page * self.items_per_page
        end = start + self.items_per_page
        page_points = self.points_with_indices[start:end]
        
        embed = discord.Embed(
            title=f"🗑️ Remove Point from {self.village}",
            description="Select a point to remove:" if not self.is_admin else "Admin Mode: Remove any point",
            color=discord.Color.orange()
        )
        
        for i, (idx, point) in enumerate(page_points):
            x, y, color = get_point_data(point)
            user_id = get_point_user(point)
            user_info = f"<@{user_id}>" if user_id else "Unknown"
            embed.add_field(
                name=f"{start + i + 1}. ({x}, {y}) - {color.capitalize()}",
                value=f"Added by: {user_info}",
                inline=False
            )
        
        embed.set_footer(text=f"Page {self.page + 1}/{self.total_pages()} • Total: {len(self.points_with_indices)} points")
        return embed

    def total_pages(self):
        return (len(self.points_with_indices) - 1) // self.items_per_page + 1

    def update_buttons(self):
        self.clear_items()
        
        # Number buttons for selection
        start = self.page * self.items_per_page
        end = min(start + self.items_per_page, len(self.points_with_indices))
        
        for i in range(start, end):
            relative_num = i - start + 1
            button = ui.Button(
                label=str(relative_num),
                style=discord.ButtonStyle.primary,
                custom_id=f"select_{i}"
            )
            button.callback = self.make_select_callback(i)
            self.add_item(button)
        
        # Navigation buttons
        if self.page > 0:
            prev_button = ui.Button(label="◀️ Previous", style=discord.ButtonStyle.secondary)
            prev_button.callback = self.previous_page
            self.add_item(prev_button)
        
        if self.page < self.total_pages() - 1:
            next_button = ui.Button(label="Next ▶️", style=discord.ButtonStyle.secondary)
            next_button.callback = self.next_page
            self.add_item(next_button)
        
        # Cancel button
        cancel_button = ui.Button(label="❌ Cancel", style=discord.ButtonStyle.danger)
        cancel_button.callback = self.cancel
        self.add_item(cancel_button)

    def make_select_callback(self, index):
        async def callback(interaction: discord.Interaction):
            if interaction.user.id != self.author_id:
                await interaction.response.send_message("❌ You didn't start this action.", ephemeral=True)
                return
            
            self.selected_index = self.points_with_indices[index][0]
            point = self.points_with_indices[index][1]
            x, y, color = get_point_data(point)
            
            # Confirm deletion
            confirm_view = ui.View(timeout=30)
            
            async def confirm_delete(confirm_interaction: discord.Interaction):
                if confirm_interaction.user.id != self.author_id:
                    await confirm_interaction.response.send_message("❌ You didn't start this action.", ephemeral=True)
                    return
                
                from data import load_data, save_data
                data = load_data()
                if self.village in data and self.selected_index < len(data[self.village]):
                    removed_point = data[self.village].pop(self.selected_index)
                    save_data(data)
                    
                    # Deduct XP from the point owner
                    point_owner = get_point_user(removed_point)
                    if point_owner:
                        new_xp = xp.subtract_xp(point_owner, 1)
                        xp_msg = f" (-1 XP for <@{point_owner}>, now at {new_xp})"
                    else:
                        xp_msg = ""
                    
                    rx, ry, rcolor = get_point_data(removed_point)
                    await confirm_interaction.response.edit_message(
                        content=f"✅ Removed point: ({rx}, {ry}, {rcolor}) from **{self.village}**{xp_msg}",
                        embed=None,
                        view=None
                    )
                    from utils import log_action
                    await log_action(confirm_interaction, f"Removed point ({rx}, {ry}, {rcolor}) from **{self.village}**{xp_msg}")
                else:
                    await confirm_interaction.response.edit_message(
                        content="❌ Point no longer exists.",
                        embed=None,
                        view=None
                    )
            
            async def cancel_delete(cancel_interaction: discord.Interaction):
                if cancel_interaction.user.id != self.author_id:
                    await cancel_interaction.response.send_message("❌ You didn't start this action.", ephemeral=True)
                    return
                await cancel_interaction.response.edit_message(
                    content="❌ Deletion cancelled.",
                    embed=None,
                    view=None
                )
            
            confirm_button = ui.Button(label="✅ Confirm Delete", style=discord.ButtonStyle.danger)
            confirm_button.callback = confirm_delete
            cancel_button = ui.Button(label="❌ Cancel", style=discord.ButtonStyle.secondary)
            cancel_button.callback = cancel_delete
            
            confirm_view.add_item(confirm_button)
            confirm_view.add_item(cancel_button)
            
            confirm_embed = discord.Embed(
                title="⚠️ Confirm Deletion",
                description=f"Are you sure you want to delete this point?\n\n**Location:** ({x}, {y})\n**Color:** {color.capitalize()}\n**Village:** {self.village}",
                color=discord.Color.red()
            )
            
            await interaction.response.edit_message(embed=confirm_embed, view=confirm_view)
        
        return callback

    async def previous_page(self, interaction: discord.Interaction):
        if interaction.user.id != self.author_id:
            await interaction.response.send_message("❌ You didn't start this action.", ephemeral=True)
            return
        
        self.page -= 1
        self.update_buttons()
        await interaction.response.edit_message(embed=self.get_embed(), view=self)

    async def next_page(self, interaction: discord.Interaction):
        if interaction.user.id != self.author_id:
            await interaction.response.send_message("❌ You didn't start this action.", ephemeral=True)
            return
        
        self.page += 1
        self.update_buttons()
        await interaction.response.edit_message(embed=self.get_embed(), view=self)

    async def cancel(self, interaction: discord.Interaction):
        if interaction.user.id != self.author_id:
            await interaction.response.send_message("❌ You didn't start this action.", ephemeral=True)
            return
        
        await interaction.response.edit_message(content="❌ Cancelled.", embed=None, view=None)
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

        # Award XP
        new_xp = xp.add_xp(interaction.user.id, 1)

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
    @tree.command(name="newmenutest", description="testing")
    async def newmenutest(interaction: discord.Interaction):
        class SampleModal(ui.Modal, title="Sample Form"):
            # Define text input fields
            name_input = ui.TextInput(
                label="Village Name",
                placeholder="Enter the village name...",
                required=True,
                max_length=50
            )
            
            pearl_input = ui.TextInput(
                label="Pearl Color",
                placeholder="Enter the pearl color...",
                required=True,
                max_length=10
            )
            
            x_input = ui.TextInput(
                label="X Coordinate",
                placeholder="Enter X coordinate...",
                required=True,
                max_length=4
            )

            y_input = ui.TextInput(
                label="Y Coordinate",
                placeholder="Enter Y coordinate...",
                required=True,
                max_length=4
            )


            async def on_submit(self, interaction: discord.Interaction):
                # This runs when user clicks "Submit" on the modal
                name = self.name_input.value
                pearl_color = self.pearl_input.value
                x_coordinate = self.x_input.value
                y_coordinate = self.y_input.value
                await interaction.response.send_message(
                    f"✅ Form submitted!\n"
                    f"**Village Name:** {name}\n"
                    f"**Pearl Color:** {pearl_color}\n"
                    f"**X Coordinate:** {x_coordinate}\n"
                    f"**Y Coordinate:** {y_coordinate}",
                    ephemeral=True
                )

        # Send the modal to the user
        await interaction.response.send_modal(SampleModal())

    @tree.command(name="xp", description="Check your XP or someone else's XP")
    @app_commands.describe(user="User to check XP for (optional)")
    async def check_xp(interaction: discord.Interaction, user: discord.User = None):
        target_user = user or interaction.user
        
        rank, user_xp = xp.get_user_rank(target_user.id)
        
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
        
        embed.set_thumbnail(url=target_user.display_avatar.url)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @tree.command(name="leaderboard", description="View the XP leaderboard")
    @app_commands.describe(limit="Number of top users to show (default: 10)")
    async def leaderboard(interaction: discord.Interaction, limit: int = 10):
        if limit < 1 or limit > 25:
            await interaction.response.send_message("❌ Limit must be between 1 and 25.", ephemeral=True)
            return
        
        top_users = xp.get_leaderboard(limit)
        
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
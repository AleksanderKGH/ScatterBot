import discord
from discord import app_commands, Interaction, ui
import matplotlib.pyplot as plt
import matplotlib.image as mpimg
import io, os
from config import COLOR_OPTIONS, PLOT_COLORS
from config import POINT_CHANNEL_ID, PLOT_CHANNEL_ID, ADMIN_ROLE_ID, LOG_CHANNEL_ID
from data import load_data, save_data
from utils import log_action, require_channel
# https://discord.com/oauth2/authorize?client_id=1385341075572396215&permissions=2147609600

import random
from datetime import datetime


VILLAGE_OPTIONS = [
    "Dogville",
    "Wheat Street",
    "An Bread Capital",
    "Sourdough Hills",
    "Yeastopia"
]

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
                img = mpimg.imread(path)
                ax.imshow(img, extent=[160, -160, -160, 160], zorder=0)
                break
            except Exception as e:
                print(f"Image load failed for {village}: {e}")
                break

    # Plot actual points
    for x, y, color in data[village]:
        plot_color = PLOT_COLORS.get(color.lower(), color.lower())
        ax.scatter(x, y, color=plot_color, zorder=1)

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
        fake_color = random.choice(COLOR_OPTIONS).lower()
        fake_plot_color = PLOT_COLORS.get(fake_color, fake_color)
        ax.scatter(fake_x, fake_y, color=fake_plot_color, zorder=1)

        return_info = (fake_x, fake_y, fake_color)
    else:
        return_info = None

    # Configure plot
    ax.set_title(f"Village: {village}")
    ax.set_xlim(160, -160)
    ax.set_ylim(-160, 160)
    ax.set_xticks([x for x in range(160, -161, -40)])
    ax.set_yticks([y for y in range(-160, 161, 40)])

    # Save to buffer
    buf = io.BytesIO()
    fig.savefig(buf, format="png", bbox_inches='tight', pad_inches=0.2)
    buf.seek(0)
    plt.close(fig)
    return buf, return_info




data = load_data()

def register_commands(tree: app_commands.CommandTree):

    @tree.command(name="point", description="Add a point to a village")
    @app_commands.describe(
        x="X coordinate (-160 to 160)",
        y="Y coordinate (-160 to 160)",
        color="Color",
        village="Village name (optional)"
    )
    async def point(interaction: discord.Interaction, x: float, y: float, color: str, village: str = "Dogville"):
        if not await require_channel(POINT_CHANNEL_ID)(interaction):
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

        if village not in data:
            data[village] = []

        # Check for duplicate
        if any(existing[0] == x and existing[1] == y and existing[2] == color.lower() for existing in data[village]):
            await interaction.response.send_message(
                f"🚫 That point already exists in '{village}' with the same color.",
                ephemeral=True
            )
            return

        data[village].append([x, y, color.lower()])
        save_data(data)

        await log_action(interaction, f"Added ({x}, {y}, {color}) to **{village}**")
        await interaction.response.send_message(f"✅ Added to '{village}'", ephemeral=True)

    @point.autocomplete("color")
    async def color_autocomplete(interaction: discord.Interaction, current: str):
        return [
            app_commands.Choice(name=color, value=color)
            for color in COLOR_OPTIONS if current.lower() in color.lower()
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
        if not await require_channel(PLOT_CHANNEL_ID)(interaction):
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
        if not await require_channel(LOG_CHANNEL_ID)(interaction):
            return
        if village not in data or not data[village]:
            await interaction.response.send_message("That village has no data.", ephemeral=True)
            return

        buf, _ = generate_plot(village, include_fake=False)
        await log_action(interaction, f"Plotted **pure** village map for **{village}**")
        await interaction.response.send_message(file=discord.File(buf, "scatter.png"), ephemeral=True)



    @tree.command(name="clearmaps", description="Clear all points from all villages")
    async def clearmaps(interaction: Interaction):
        if interaction.channel_id != LOG_CHANNEL_ID:
            await interaction.response.send_message(
                f"❌ This command can only be used in <#{LOG_CHANNEL_ID}>.",
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

        # Clear points but keep village keys
        for village in data.keys():
            data[village] = []

        save_data(data)
        await interaction.followup.send("🧹 All points have been cleared from all villages (villages preserved).")
    

    @tree.command(name="villages", description="List all tracked villages and how many points are in each")
    async def list_villages(interaction: discord.Interaction):
        if interaction.channel_id != POINT_CHANNEL_ID:
                await interaction.response.send_message(
                    f"❌ This command can only be used in <#{POINT_CHANNEL_ID}>.",
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









    @tree.command(name="noob", description="List all available commands")
    async def noob_command(interaction: discord.Interaction):
        embed = discord.Embed(
            title="🗺️ PearlMap Bot Commands",
            description="Here are the available commands you can use!",
            color=discord.Color.blurple()
        )

        embed.add_field(
            name="🧭 /point",
            value="Add a point to a village. Provide coordinates, color, and village name (optional, defaults to Dogville).",
            inline=False
        )
        embed.add_field(
            name="🖼️ /plot",
            value="Generate a scatter plot of points in a village. Defaults to Dogville if none provided.",
            inline=False
        )
        embed.add_field(
            name="📜 /villages",
            value="List all tracked villages and the number of points in each.",
            inline=False
        )
        embed.add_field(
            name="🧹 /clearmaps",
            value="Clear all points in all villages (admin-only, confirmation required).",
            inline=False
        )
        embed.add_field(
            name="❓ /noob",
            value="You're looking at it! Shows all available commands.",
            inline=False
        )

        await interaction.response.send_message(embed=embed, ephemeral=True)
"""
Discord UI View classes for PearlMapBot.
Contains interactive components like buttons, modals, and confirmation dialogs.
"""

import discord
from discord import ui, Interaction
from utils import get_point_data, get_point_user
from data import load_data, save_data
import xp


class ConfirmYesterdayView(discord.ui.View):
    """Confirmation view for pearls that were spotted yesterday."""
    
    def __init__(self, author_id):
        super().__init__(timeout=30)
        self.author_id = author_id
        self.confirmed = False

    @discord.ui.button(label="✅ Yes, I saw it fall!", style=discord.ButtonStyle.success)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.author_id:
            await interaction.response.send_message("❌ You didn't start this confirmation.", ephemeral=True)
            return

        self.confirmed = True
        for item in self.children:
            item.disabled = True
        await interaction.response.edit_message(content="📍 Pearl confirmed. Adding to the map...", view=self)
        self.stop()

    @discord.ui.button(label="❌ Nope, don't add it", style=discord.ButtonStyle.danger)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.author_id:
            await interaction.response.send_message("❌ You didn't start this confirmation.", ephemeral=True)
            return

        await interaction.response.edit_message(content="❌ Cancelled. Pearl not added.", view=None)
        self.stop()


class ConfirmClearView(ui.View):
    """Confirmation view for clearing all village points."""
    
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
    """Interactive paginated view for selecting and removing points from a village."""
    
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
        """Generate the embed for the current page."""
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
        """Calculate total number of pages needed."""
        return (len(self.points_with_indices) - 1) // self.items_per_page + 1

    def update_buttons(self):
        """Update button state and layout based on current page."""
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
        """Create a callback for selecting a point to remove."""
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
        """Navigate to the previous page."""
        if interaction.user.id != self.author_id:
            await interaction.response.send_message("❌ You didn't start this action.", ephemeral=True)
            return
        
        self.page -= 1
        self.update_buttons()
        await interaction.response.edit_message(embed=self.get_embed(), view=self)

    async def next_page(self, interaction: discord.Interaction):
        """Navigate to the next page."""
        if interaction.user.id != self.author_id:
            await interaction.response.send_message("❌ You didn't start this action.", ephemeral=True)
            return
        
        self.page += 1
        self.update_buttons()
        await interaction.response.edit_message(embed=self.get_embed(), view=self)

    async def cancel(self, interaction: discord.Interaction):
        """Cancel the point removal action."""
        if interaction.user.id != self.author_id:
            await interaction.response.send_message("❌ You didn't start this action.", ephemeral=True)
            return
        
        await interaction.response.edit_message(content="❌ Cancelled.", embed=None, view=None)
        self.stop()


class SampleModal(ui.Modal, title="Sample Form"):
    """Sample modal form for testing purposes."""
    
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
        """Handle modal form submission."""
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

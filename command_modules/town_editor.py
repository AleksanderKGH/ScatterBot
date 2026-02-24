from __future__ import annotations

import os
import time

import discord
from discord import ui


def build_house_options(houses: list[dict], village: str) -> list[discord.SelectOption]:
    options = []
    prefix = f"{village.lower()}-"
    for house in houses[:25]:
        house_id = str(house.get("id", ""))
        label = house_id
        if label.lower().startswith(prefix):
            label = label[len(prefix):]
        x = house.get("x", "?")
        y = house.get("y", "?")
        desc = f"{house.get('class', '')} ({x}, {y})"
        options.append(discord.SelectOption(label=label or "(no id)", value=house_id, description=desc[:100]))
    return options


class TownChunkSelect(ui.Select):
    def __init__(self, options: list[discord.SelectOption]):
        super().__init__(placeholder="Select a chunk", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        view = self.view
        if isinstance(view, TownEditView):
            await view.render_chunk(interaction, self.values[0])


class TownHouseSelect(ui.Select):
    def __init__(self):
        super().__init__(
            placeholder="Select a house",
            min_values=1,
            max_values=1,
            options=[discord.SelectOption(label="Select a chunk first", value="__none__")]
        )
        self.disabled = True

    def update_options(self, options: list[discord.SelectOption]):
        if options:
            self.options = options
            self.disabled = False
        else:
            self.options = [discord.SelectOption(label="No houses", value="__none__")]
            self.disabled = True

    async def callback(self, interaction: discord.Interaction):
        view = self.view
        if isinstance(view, TownEditView):
            view.selected_house_id = self.values[0]
            await interaction.response.defer(ephemeral=True)


class AddHouseModal(ui.Modal):
    def __init__(self, view_ref, chunk_key: str):
        super().__init__(title="Add House")
        self.view_ref = view_ref
        self.chunk_key = chunk_key

        self.house_id = ui.TextInput(label="House ID", placeholder="a2-001", required=True)
        self.house_class = ui.TextInput(label="Class", placeholder="A2", required=True)
        self.house_rotation = ui.TextInput(label="Rotation", placeholder="0", required=True)
        self.house_x = ui.TextInput(label="X", placeholder="Top-left x", required=True)
        self.house_y = ui.TextInput(label="Y", placeholder="Top-left y", required=True)

        self.add_item(self.house_id)
        self.add_item(self.house_class)
        self.add_item(self.house_rotation)
        self.add_item(self.house_x)
        self.add_item(self.house_y)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            rotation = int(self.house_rotation.value)
            x = float(self.house_x.value)
            y = float(self.house_y.value)
        except ValueError:
            await interaction.response.send_message("❌ Rotation, X, and Y must be numeric.", ephemeral=True)
            return

        house_id = self.house_id.value.strip()
        class_name = self.house_class.value.strip().upper()
        occupants = ""

        try:
            classes = self.view_ref.load_house_classes_fn()
        except Exception as exc:
            await interaction.response.send_message(f"❌ Failed to load classes: {exc}", ephemeral=True)
            return

        if class_name not in classes.get("classes", {}):
            await interaction.response.send_message(f"❌ Unknown class '{class_name}'.", ephemeral=True)
            return

        town_path = os.path.join(self.view_ref.towns_dir, f"{self.view_ref.village}.json")
        current_mtime = os.path.getmtime(town_path)
        town_data = self.view_ref.load_town_layout_fn(self.view_ref.village)
        existing_ids = {house.get("id") for house in self.view_ref.get_town_houses_fn(town_data) if isinstance(house, dict)}
        if house_id in existing_ids:
            await interaction.response.send_message(f"❌ ID '{house_id}' already exists.", ephemeral=True)
            return

        target_chunk = self.view_ref.get_chunk_key_for_point_fn(x, y, town_data)
        warning = ""
        if current_mtime > self.view_ref.last_mtime:
            warning = "⚠️ Town data changed since you opened the editor. "
        if target_chunk != self.chunk_key:
            warning += f"⚠️ Note: Added to {target_chunk} based on coordinates."

        entry = self.view_ref.ensure_chunk_entry_fn(town_data, target_chunk)
        entry.setdefault("houses", []).append(
            {
                "id": house_id,
                "class": class_name,
                "rotation": rotation,
                "x": x,
                "y": y,
                "occupants": occupants,
                "notes": "added via editor"
            }
        )

        self.view_ref.save_town_layout_fn(self.view_ref.village, town_data)
        self.view_ref.last_mtime = os.path.getmtime(town_path)

        message = f"✅ Added {house_id} to {self.view_ref.village}. {warning}".strip()
        await interaction.response.send_message(message, ephemeral=True)


class AddHouseButton(ui.Button):
    def __init__(self):
        super().__init__(label="Add House", style=discord.ButtonStyle.primary, row=2)

    async def callback(self, interaction: discord.Interaction):
        view = self.view
        if not isinstance(view, TownEditView) or not view.chunk_key:
            await interaction.response.send_message("Select a chunk first.", ephemeral=True)
            return
        await interaction.response.send_modal(AddHouseModal(view, view.chunk_key))


class MoveHouseButton(ui.Button):
    def __init__(self):
        super().__init__(label="Move", style=discord.ButtonStyle.secondary, row=2)

    async def callback(self, interaction: discord.Interaction):
        view = self.view
        if not isinstance(view, TownEditView) or not view.selected_house_id:
            await interaction.response.send_message("Select a house first.", ephemeral=True)
            return
        await view.start_move(interaction, view.selected_house_id)


class NudgeButton(ui.Button):
    def __init__(self, label: str, dx: float, dy: float, row: int):
        super().__init__(label=label, style=discord.ButtonStyle.secondary, row=row)
        self.dx = dx
        self.dy = dy

    async def callback(self, interaction: discord.Interaction):
        view = self.view
        if not isinstance(view, TownEditView) or not view.move_mode:
            await interaction.response.send_message("Move mode is not active.", ephemeral=True)
            return
        await view.nudge(interaction, self.dx, self.dy)


class SaveMoveButton(ui.Button):
    def __init__(self, row: int):
        super().__init__(label="Save Move", style=discord.ButtonStyle.success, row=row)

    async def callback(self, interaction: discord.Interaction):
        view = self.view
        if not isinstance(view, TownEditView) or not view.move_mode:
            await interaction.response.send_message("Move mode is not active.", ephemeral=True)
            return
        await view.save_move(interaction)


class CancelMoveButton(ui.Button):
    def __init__(self, row: int):
        super().__init__(label="Cancel Move", style=discord.ButtonStyle.danger, row=row)

    async def callback(self, interaction: discord.Interaction):
        view = self.view
        if not isinstance(view, TownEditView) or not view.move_mode:
            await interaction.response.send_message("Move mode is not active.", ephemeral=True)
            return
        await view.cancel_move(interaction)


class RefreshButton(ui.Button):
    def __init__(self):
        super().__init__(label="🔄 Refresh", style=discord.ButtonStyle.secondary, row=2)

    async def callback(self, interaction: discord.Interaction):
        view = self.view
        if not isinstance(view, TownEditView) or not view.chunk_key:
            await interaction.response.send_message("Select a chunk first.", ephemeral=True)
            return
        await view.render_chunk(interaction, view.chunk_key)


class RotateCWButton(ui.Button):
    def __init__(self):
        super().__init__(label="⟳ +90°", style=discord.ButtonStyle.secondary, row=2)

    async def callback(self, interaction: discord.Interaction):
        view = self.view
        if not isinstance(view, TownEditView) or not view.selected_house_id:
            await interaction.response.send_message("Select a house first.", ephemeral=True)
            return
        await view.rotate_house(interaction, view.selected_house_id, 90)


class RotateCCWButton(ui.Button):
    def __init__(self):
        super().__init__(label="⟲ -90°", style=discord.ButtonStyle.secondary, row=2)

    async def callback(self, interaction: discord.Interaction):
        view = self.view
        if not isinstance(view, TownEditView) or not view.selected_house_id:
            await interaction.response.send_message("Select a house first.", ephemeral=True)
            return
        await view.rotate_house(interaction, view.selected_house_id, -90)


class TownEditView(ui.View):
    def __init__(
        self,
        village: str,
        use_footprints: bool,
        towns_dir: str,
        load_town_layout_fn,
        save_town_layout_fn,
        load_house_classes_fn,
        get_town_houses_fn,
        build_chunk_options_fn,
        generate_chunk_plot_fn,
        find_house_by_id_fn,
        get_chunk_key_for_point_fn,
        ensure_chunk_entry_fn,
    ):
        super().__init__(timeout=600)
        self.village = village
        self.use_footprints = use_footprints
        self.towns_dir = towns_dir

        self.load_town_layout_fn = load_town_layout_fn
        self.save_town_layout_fn = save_town_layout_fn
        self.load_house_classes_fn = load_house_classes_fn
        self.get_town_houses_fn = get_town_houses_fn
        self.build_chunk_options_fn = build_chunk_options_fn
        self.generate_chunk_plot_fn = generate_chunk_plot_fn
        self.find_house_by_id_fn = find_house_by_id_fn
        self.get_chunk_key_for_point_fn = get_chunk_key_for_point_fn
        self.ensure_chunk_entry_fn = ensure_chunk_entry_fn

        self.chunk_key = None
        self.selected_house_id = None
        self.move_mode = False
        self.move_house_id = None
        self.move_x = None
        self.move_y = None
        self.move_chunk_key = None
        self.created_at = time.time()
        self.last_mtime = os.path.getmtime(os.path.join(towns_dir, f"{village}.json"))

        town_data = self.load_town_layout_fn(village)
        options = self.build_chunk_options_fn(town_data)
        self.chunk_select = TownChunkSelect(options)
        self.house_select = TownHouseSelect()

        self.add_item(self.chunk_select)
        self.add_item(self.house_select)
        self.add_item(AddHouseButton())
        self.add_item(MoveHouseButton())
        self.add_item(RefreshButton())
        self.add_item(RotateCWButton())
        self.add_item(RotateCCWButton())

        self.nudge_up = NudgeButton("Up", 0, 1, row=3)
        self.nudge_down = NudgeButton("Down", 0, -1, row=3)
        self.nudge_left = NudgeButton("Left", 1, 0, row=3)
        self.nudge_right = NudgeButton("Right", -1, 0, row=3)
        self.save_move_btn = SaveMoveButton(row=4)
        self.cancel_move_btn = CancelMoveButton(row=4)

        for btn in [self.nudge_up, self.nudge_down, self.nudge_left, self.nudge_right, self.save_move_btn, self.cancel_move_btn]:
            btn.disabled = True
            self.add_item(btn)

    def set_move_mode(self, enabled: bool):
        self.move_mode = enabled
        for btn in [self.nudge_up, self.nudge_down, self.nudge_left, self.nudge_right, self.save_move_btn, self.cancel_move_btn]:
            btn.disabled = not enabled

    async def render_chunk(self, interaction: discord.Interaction, chunk_key: str):
        self.chunk_key = chunk_key

        self.last_mtime = os.path.getmtime(os.path.join(self.towns_dir, f"{self.village}.json"))
        town_data = self.load_town_layout_fn(self.village)
        chunk_entry = town_data.get("houses_by_chunk", {}).get(chunk_key, {})
        chunk_houses = chunk_entry.get("houses", []) if isinstance(chunk_entry, dict) else []

        self.selected_house_id = None
        self.house_select.update_options(build_house_options(chunk_houses, self.village))

        overrides = None
        highlight_id = None
        if self.move_mode and self.move_house_id is not None and self.move_x is not None and self.move_y is not None:
            overrides = {self.move_house_id: {"x": self.move_x, "y": self.move_y}}
            highlight_id = self.move_house_id

        buf, stats = self.generate_chunk_plot_fn(
            self.village,
            chunk_key,
            use_footprints=self.use_footprints,
            overrides=overrides,
            highlight_house_id=highlight_id
        )
        embed = discord.Embed(
            title=f"🏘️ {self.village} {chunk_key}",
            description=f"Mode: `{stats['mode']}` · Houses: `{stats['houses_drawn']}`",
            color=discord.Color.green()
        )
        embed.set_image(url="attachment://chunk.png")

        file = discord.File(buf, "chunk.png")
        await interaction.response.edit_message(embed=embed, attachments=[file], view=self)

    async def start_move(self, interaction: discord.Interaction, house_id: str):
        if not self.chunk_key:
            await interaction.response.send_message("Select a chunk first.", ephemeral=True)
            return

        town_data = self.load_town_layout_fn(self.village)
        found = self.find_house_by_id_fn(town_data, house_id)
        if not found:
            await interaction.response.send_message("House not found.", ephemeral=True)
            return

        chunk_key, _, house = found
        self.move_mode = True
        self.move_house_id = house_id
        self.move_x = float(house.get("x", 0))
        self.move_y = float(house.get("y", 0))
        self.move_chunk_key = chunk_key
        self.set_move_mode(True)

        await self.render_chunk(interaction, self.chunk_key)

    async def nudge(self, interaction: discord.Interaction, dx: float, dy: float):
        if self.move_x is None or self.move_y is None:
            await interaction.response.send_message("Move state not initialized.", ephemeral=True)
            return
        self.move_x += dx
        self.move_y += dy
        await self.render_chunk(interaction, self.chunk_key)

    async def save_move(self, interaction: discord.Interaction):
        if self.move_house_id is None or self.move_x is None or self.move_y is None:
            await interaction.response.send_message("Move state not initialized.", ephemeral=True)
            return

        town_path = os.path.join(self.towns_dir, f"{self.village}.json")
        current_mtime = os.path.getmtime(town_path)
        town_data = self.load_town_layout_fn(self.village)

        found = self.find_house_by_id_fn(town_data, self.move_house_id)
        if not found:
            await interaction.response.send_message("House not found.", ephemeral=True)
            return

        old_chunk, index, house = found
        house["x"] = self.move_x
        house["y"] = self.move_y

        new_chunk = self.get_chunk_key_for_point_fn(self.move_x, self.move_y, town_data)
        warning = ""
        if current_mtime > self.last_mtime:
            warning = "⚠️ Town data changed since you opened the editor. "

        if new_chunk != old_chunk:
            old_entry = self.ensure_chunk_entry_fn(town_data, old_chunk)
            if index < len(old_entry.get("houses", [])):
                old_entry["houses"].pop(index)
            self.ensure_chunk_entry_fn(town_data, new_chunk)["houses"].append(house)
            warning += f"⚠️ Moved to {new_chunk}."

        self.save_town_layout_fn(self.village, town_data)
        self.last_mtime = os.path.getmtime(town_path)

        self.set_move_mode(False)
        self.move_house_id = None
        self.move_x = None
        self.move_y = None
        self.move_chunk_key = None

        await interaction.response.send_message(f"✅ Move saved. {warning}".strip(), ephemeral=True)

    async def cancel_move(self, interaction: discord.Interaction):
        self.set_move_mode(False)
        self.move_house_id = None
        self.move_x = None
        self.move_y = None
        self.move_chunk_key = None
        await self.render_chunk(interaction, self.chunk_key)

    async def rotate_house(self, interaction: discord.Interaction, house_id: str, delta_rotation: int):
        town_path = os.path.join(self.towns_dir, f"{self.village}.json")
        current_mtime = os.path.getmtime(town_path)
        town_data = self.load_town_layout_fn(self.village)

        found = self.find_house_by_id_fn(town_data, house_id)
        if not found:
            await interaction.response.send_message("❌ House not found.", ephemeral=True)
            return

        _, _, house = found
        current_rotation = house.get("rotation", 0)
        new_rotation = (current_rotation + delta_rotation) % 360
        house["rotation"] = new_rotation

        warning = ""
        if current_mtime > self.last_mtime:
            warning = "⚠️ Town data changed since you opened the editor. "

        self.save_town_layout_fn(self.village, town_data)
        self.last_mtime = os.path.getmtime(town_path)

        await interaction.response.send_message(f"✅ Rotated {house_id} to {new_rotation}°. {warning}".strip(), ephemeral=True)


def create_town_edit_view(
    village: str,
    use_footprints: bool,
    towns_dir: str,
    load_town_layout_fn,
    save_town_layout_fn,
    load_house_classes_fn,
    get_town_houses_fn,
    build_chunk_options_fn,
    generate_chunk_plot_fn,
    find_house_by_id_fn,
    get_chunk_key_for_point_fn,
    ensure_chunk_entry_fn,
):
    return TownEditView(
        village=village,
        use_footprints=use_footprints,
        towns_dir=towns_dir,
        load_town_layout_fn=load_town_layout_fn,
        save_town_layout_fn=save_town_layout_fn,
        load_house_classes_fn=load_house_classes_fn,
        get_town_houses_fn=get_town_houses_fn,
        build_chunk_options_fn=build_chunk_options_fn,
        generate_chunk_plot_fn=generate_chunk_plot_fn,
        find_house_by_id_fn=find_house_by_id_fn,
        get_chunk_key_for_point_fn=get_chunk_key_for_point_fn,
        ensure_chunk_entry_fn=ensure_chunk_entry_fn,
    )

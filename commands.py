import discord
from discord import app_commands, Interaction, ui
import matplotlib.pyplot as plt
import matplotlib.image as mpimg
import matplotlib.patches as mpatches
from PIL import Image
import io, os
import config
from data import load_data, save_data
from utils import log_action, require_channel, create_point, get_point_data, get_top_contributors, get_point_user
from views import ConfirmClearView
import xp
# https://discord.com/oauth2/authorize?client_id=1385341075572396215&permissions=2147609600
import json
import time
import random
from datetime import datetime, timedelta
from discord import ui
from command_modules import points as points_module, town as town_module, admin as admin_module


BACKUP_DIR = "backups"
TOWNS_DIR = "towns"
HOUSE_CLASSES_FILE = "house_classes.json"
os.makedirs(BACKUP_DIR, exist_ok=True)
os.makedirs(TOWNS_DIR, exist_ok=True)

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


def load_house_classes() -> dict:
    if not os.path.exists(HOUSE_CLASSES_FILE):
        raise FileNotFoundError(f"Missing {HOUSE_CLASSES_FILE}")
    with open(HOUSE_CLASSES_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def load_town_layout(village: str) -> dict:
    path = os.path.join(TOWNS_DIR, f"{village}.json")
    if not os.path.exists(path):
        raise FileNotFoundError(f"Missing town file: {path}")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_town_layout(village: str, town_data: dict) -> None:
    path = os.path.join(TOWNS_DIR, f"{village}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(town_data, f, indent=2)


def list_town_layout_names() -> list[str]:
    villages = []
    for file_name in os.listdir(TOWNS_DIR):
        if file_name.lower().endswith(".json"):
            villages.append(os.path.splitext(file_name)[0])
    return sorted(villages)


def normalize_house_size(footprint: dict, rotation: int) -> tuple[float, float]:
    width = footprint.get("width")
    height = footprint.get("height")
    if width is None or height is None:
        return 0, 0

    if rotation % 180 == 90:
        return float(height), float(width)
    return float(width), float(height)


def expand_footprint_tiles(footprint: dict) -> list[tuple[int, int, str]]:
    tiles = footprint.get("tiles", [])
    if isinstance(tiles, list) and tiles:
        expanded = []
        for entry in tiles:
            if isinstance(entry, (list, tuple)) and len(entry) >= 2:
                role = str(entry[2]) if len(entry) >= 3 else "house"
                expanded.append((int(entry[0]), int(entry[1]), role))
        if expanded:
            return expanded

    tile_rects = footprint.get("tile_rects", [])
    if isinstance(tile_rects, list) and tile_rects:
        expanded = []
        for rect in tile_rects:
            if not isinstance(rect, dict):
                continue
            start_x = int(rect.get("x", 0))
            start_y = int(rect.get("y", 0))
            rect_w = int(rect.get("width", 0))
            rect_h = int(rect.get("height", 0))
            role = str(rect.get("role", "house"))
            for tile_x in range(start_x, start_x + max(0, rect_w)):
                for tile_y in range(start_y, start_y + max(0, rect_h)):
                    expanded.append((tile_x, tile_y, role))
        if expanded:
            return expanded

    width = int(footprint.get("width") or 0)
    height = int(footprint.get("height") or 0)
    if width <= 0 or height <= 0:
        return []

    return [(tile_x, tile_y, "house") for tile_x in range(width) for tile_y in range(height)]


def rotate_tile(tile_x: int, tile_y: int, base_w: int, base_h: int, rotation: int) -> tuple[int, int]:
    rotation = rotation % 360
    if rotation == 0:
        return tile_x, tile_y
    if rotation == 90:
        return base_h - 1 - tile_y, tile_x
    if rotation == 180:
        return base_w - 1 - tile_x, base_h - 1 - tile_y
    if rotation == 270:
        return tile_y, base_w - 1 - tile_x
    return tile_x, tile_y


def get_chunking_config(town_data: dict) -> tuple[int, int, int]:
    grid = town_data.get("grid", {})
    width = int(grid.get("width", 320))
    height = int(grid.get("height", 320))
    chunking = town_data.get("chunking", {})
    chunk_size = int(chunking.get("chunk_size", 80))
    rows = int(chunking.get("grid_chunks", {}).get("rows", height // chunk_size))
    cols = int(chunking.get("grid_chunks", {}).get("cols", width // chunk_size))
    return chunk_size, rows, cols


def parse_chunk_key(chunk_key: str) -> tuple[int, int] | None:
    if not chunk_key.startswith("r") or "c" not in chunk_key:
        return None
    try:
        row_part, col_part = chunk_key[1:].split("c", 1)
        return int(row_part), int(col_part)
    except ValueError:
        return None


def get_chunk_bounds(row: int, col: int, town_data: dict) -> dict:
    grid = town_data.get("grid", {})
    width = int(grid.get("width", 320))
    height = int(grid.get("height", 320))
    chunk_size, _, _ = get_chunking_config(town_data)
    min_x = -(width // 2)
    max_y = height // 2
    x_min = min_x + (col * chunk_size)
    x_max = x_min + chunk_size
    y_max = max_y - (row * chunk_size)
    y_min = y_max - chunk_size
    return {"x": [x_min, x_max], "y": [y_min, y_max]}


def get_chunk_key_for_point(x: float, y: float, town_data: dict) -> str:
    grid = town_data.get("grid", {})
    width = int(grid.get("width", 320))
    height = int(grid.get("height", 320))
    chunk_size, rows, cols = get_chunking_config(town_data)
    min_x = -(width // 2)
    max_y = height // 2

    col = int((x - min_x) // chunk_size)
    row = int((max_y - y) // chunk_size)
    col = max(0, min(cols - 1, col))
    row = max(0, min(rows - 1, row))
    return f"r{row}c{col}"


def ensure_chunk_entry(town_data: dict, chunk_key: str) -> dict:
    houses_by_chunk = town_data.setdefault("houses_by_chunk", {})
    entry = houses_by_chunk.get(chunk_key)
    if isinstance(entry, dict):
        entry.setdefault("houses", [])
        row_col = parse_chunk_key(chunk_key)
        if row_col is not None:
            entry.setdefault("bounds", get_chunk_bounds(row_col[0], row_col[1], town_data))
        return entry

    row_col = parse_chunk_key(chunk_key)
    if row_col is None:
        raise ValueError(f"Invalid chunk key: {chunk_key}")
    entry = {
        "bounds": get_chunk_bounds(row_col[0], row_col[1], town_data),
        "houses": []
    }
    houses_by_chunk[chunk_key] = entry
    return entry


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


def find_house_by_id(town_data: dict, house_id: str) -> tuple[str, int, dict] | None:
    houses_by_chunk = town_data.get("houses_by_chunk", {})
    for chunk_key, chunk_entry in houses_by_chunk.items():
        if not isinstance(chunk_entry, dict):
            continue
        houses = chunk_entry.get("houses", [])
        if not isinstance(houses, list):
            continue
        for index, house in enumerate(houses):
            if isinstance(house, dict) and house.get("id") == house_id:
                return chunk_key, index, house
    return None


def draw_houses(
    ax,
    houses: list[dict],
    classes_data: dict,
    palette: dict,
    class_palette: dict,
    use_footprints: bool,
    grass_color: str,
    connector_color: str,
    village: str,
    overrides: dict | None = None,
    highlight_house_id: str | None = None,
    highlight_color: str = "#00b4d8"
) -> tuple[int, int]:
    class_defs = classes_data.get("classes", {})
    houses_drawn = 0
    houses_skipped = 0

    for house in houses:
        class_name = house.get("class")
        class_def = class_defs.get(class_name)
        if not class_def:
            houses_skipped += 1
            continue

        footprint = class_def.get("footprint", {})
        rotation = int(house.get("rotation", 0))
        width, height = normalize_house_size(footprint, rotation)
        if width <= 0 or height <= 0:
            houses_skipped += 1
            continue

        family = class_def.get("family", "")
        palette_key = class_palette.get(family, "house_a")
        house_color = palette.get(palette_key, "#d62828")

        house_id = str(house.get("id") or "")
        top_left_x = float(house.get("x", 0))
        top_left_y = float(house.get("y", 0))
        if overrides and house_id in overrides:
            override = overrides[house_id]
            top_left_x = float(override.get("x", top_left_x))
            top_left_y = float(override.get("y", top_left_y))
            if "rotation" in override:
                rotation = int(override.get("rotation"))
        corner_x = top_left_x - width
        corner_y = top_left_y - height

        center_x = top_left_x - (width / 2)
        center_y = top_left_y - (height / 2)

        base_w = int(footprint.get("width") or 0)
        base_h = int(footprint.get("height") or 0)
        tile_cells = expand_footprint_tiles(footprint) if use_footprints else []

        if base_w > 0 and base_h > 0 and tile_cells:
            grass_rect = mpatches.Rectangle(
                (corner_x, corner_y),
                width,
                height,
                facecolor=grass_color,
                edgecolor=grass_color,
                linewidth=0,
                alpha=1.0,
                zorder=2.5
            )
            ax.add_patch(grass_rect)

            for tile_x, tile_y, tile_role in tile_cells:
                rot_x, rot_y = rotate_tile(tile_x, tile_y, base_w, base_h, rotation)
                tile_corner_x = top_left_x - (rot_x + 1)
                tile_corner_y = top_left_y - (rot_y + 1)
                tile_color = connector_color if tile_role == "connector" else house_color
                tile_rect = mpatches.Rectangle(
                    (tile_corner_x, tile_corner_y),
                    1,
                    1,
                    facecolor=tile_color,
                    edgecolor=tile_color,
                    linewidth=0,
                    alpha=1.0,
                    zorder=3
                )
                ax.add_patch(tile_rect)
        else:
            rect = mpatches.Rectangle(
                (corner_x, corner_y),
                width,
                height,
                facecolor=house_color,
                edgecolor=house_color,
                linewidth=0,
                alpha=1.0,
                zorder=3
            )
            ax.add_patch(rect)

        if highlight_house_id and house_id == highlight_house_id:
            highlight_rect = mpatches.Rectangle(
                (corner_x, corner_y),
                width,
                height,
                fill=False,
                edgecolor=highlight_color,
                linewidth=1.5,
                zorder=4.5
            )
            ax.add_patch(highlight_rect)

        house_label = str(house.get("id") or class_name)
        prefix = f"{village.lower()}-"
        if house_label.lower().startswith(prefix):
            house_label = house_label[len(prefix):]
        ax.text(center_x, center_y, house_label, fontsize=6, ha="center", va="center", color="black", zorder=4)
        if house.get("occupants"):
            ax.text(center_x, corner_y - 1.5, house["occupants"], fontsize=6, ha="center", va="top", color="black", zorder=4)

        houses_drawn += 1

    return houses_drawn, houses_skipped


def get_town_houses(town_data: dict) -> list[dict]:
    houses = town_data.get("houses")
    if isinstance(houses, list):
        return houses

    grouped = town_data.get("houses_by_chunk", {})
    if not isinstance(grouped, dict):
        return []

    flattened = []
    for chunk_value in grouped.values():
        if isinstance(chunk_value, list):
            flattened.extend([entry for entry in chunk_value if isinstance(entry, dict)])
        elif isinstance(chunk_value, dict):
            chunk_houses = chunk_value.get("houses", [])
            if isinstance(chunk_houses, list):
                flattened.extend([entry for entry in chunk_houses if isinstance(entry, dict)])
    return flattened


def build_chunk_options(town_data: dict) -> list[discord.SelectOption]:
    chunk_size, rows, cols = get_chunking_config(town_data)
    houses_by_chunk = town_data.get("houses_by_chunk", {})
    options = []

    for row in range(rows):
        for col in range(cols):
            key = f"r{row}c{col}"
            bounds = get_chunk_bounds(row, col, town_data)
            count = 0
            chunk_entry = houses_by_chunk.get(key, {})
            if isinstance(chunk_entry, dict):
                houses = chunk_entry.get("houses", [])
                if isinstance(houses, list):
                    count = len(houses)
            description = f"x {bounds['x'][0]}..{bounds['x'][1]} y {bounds['y'][0]}..{bounds['y'][1]} · {count}"
            options.append(discord.SelectOption(label=key, value=key, description=description))

    return options


def generate_town_layout_plot(village: str, use_footprints: bool = True) -> tuple[io.BytesIO, dict]:
    classes_data = load_house_classes()
    town_data = load_town_layout(village)

    fig, ax = plt.subplots(figsize=(7, 7))

    grid_cfg = town_data.get("grid", {})
    half_w = int(grid_cfg.get("width", 320) / 2)
    half_h = int(grid_cfg.get("height", 320) / 2)

    palette = town_data.get("palette", {})
    class_palette = classes_data.get("class_palette", {})
    class_defs = classes_data.get("classes", {})

    grass_color = palette.get("grass", "#5b8f4f")
    road_color = palette.get("road", "#4a4e69")
    poi_color = palette.get("poi", "#457b9d")
    connector_color = palette.get("house_connector", "#b5651d")

    roads_drawn = 0
    for road in town_data.get("roads", []):
        if road.get("type") != "line":
            continue
        start = road.get("from", {})
        end = road.get("to", {})
        ax.plot(
            [start.get("x", 0), end.get("x", 0)],
            [start.get("y", 0), end.get("y", 0)],
            color=road_color,
            linewidth=road.get("width", 2),
            alpha=0.9,
            zorder=1
        )
        roads_drawn += 1

    pois_drawn = 0
    for poi in town_data.get("points_of_interest", []):
        cx = poi.get("x", 0)
        cy = poi.get("y", 0)
        radius = poi.get("radius", 2)
        current_poi_color = poi.get("color", poi_color)
        poi_shape = str(poi.get("shape", "circle")).lower()

        if poi_shape == "square":
            size = radius * 2
            square = mpatches.Rectangle(
                (cx - radius, cy - radius),
                size,
                size,
                fill=False,
                edgecolor=current_poi_color,
                linewidth=1.5,
                zorder=2
            )
            ax.add_patch(square)
        else:
            circle = mpatches.Circle((cx, cy), radius=radius, fill=False, edgecolor=current_poi_color, linewidth=1.5, zorder=2)
            ax.add_patch(circle)

        if poi.get("label"):
            ax.text(cx, cy + radius + 2, poi["label"], fontsize=8, ha="center", va="bottom", color=current_poi_color)
        pois_drawn += 1

    houses = get_town_houses(town_data)
    houses_drawn, houses_skipped = draw_houses(
        ax=ax,
        houses=houses,
        classes_data=classes_data,
        palette=palette,
        class_palette=class_palette,
        use_footprints=use_footprints,
        grass_color=grass_color,
        connector_color=connector_color,
        village=village
    )

    ax.set_title(f"Town Layout: {village}")
    ax.set_xlim(half_w, -half_w)
    ax.set_ylim(-half_h, half_h)
    ax.set_xticks([x for x in range(half_w, -half_w - 1, -20)])
    ax.set_yticks([y for y in range(-half_h, half_h + 1, 20)])
    ax.grid(True, linestyle="--", linewidth=0.5, color="gray", zorder=0)
    ax.axhline(y=0, color="black", linewidth=1)
    ax.axvline(x=0, color="black", linewidth=1)

    buf = io.BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight", pad_inches=0.2)
    buf.seek(0)
    plt.close(fig)

    stats = {
        "houses_drawn": houses_drawn,
        "houses_skipped": houses_skipped,
        "roads_drawn": roads_drawn,
        "pois_drawn": pois_drawn,
        "mode": "footprints" if use_footprints else "squares",
    }
    return buf, stats


def generate_chunk_plot(
    village: str,
    chunk_key: str,
    use_footprints: bool = False,
    overrides: dict | None = None,
    highlight_house_id: str | None = None
) -> tuple[io.BytesIO, dict]:
    classes_data = load_house_classes()
    town_data = load_town_layout(village)
    palette = town_data.get("palette", {})
    class_palette = classes_data.get("class_palette", {})
    grass_color = palette.get("grass", "#5b8f4f")
    connector_color = palette.get("house_connector", "#b5651d")

    houses_by_chunk = town_data.get("houses_by_chunk", {})
    chunk_entry = houses_by_chunk.get(chunk_key, {})
    bounds = chunk_entry.get("bounds") if isinstance(chunk_entry, dict) else None
    row_col = parse_chunk_key(chunk_key)
    if bounds is None and row_col is not None:
        bounds = get_chunk_bounds(row_col[0], row_col[1], town_data)
    if bounds is None:
        raise ValueError(f"Unknown chunk: {chunk_key}")

    houses = []
    if isinstance(chunk_entry, dict):
        houses = chunk_entry.get("houses", []) if isinstance(chunk_entry.get("houses", []), list) else []

    fig, ax = plt.subplots(figsize=(5, 5))

    houses_drawn, houses_skipped = draw_houses(
        ax=ax,
        houses=houses,
        classes_data=classes_data,
        palette=palette,
        class_palette=class_palette,
        use_footprints=use_footprints,
        grass_color=grass_color,
        connector_color=connector_color,
        village=village,
        overrides=overrides,
        highlight_house_id=highlight_house_id
    )

    x_min, x_max = bounds["x"][0], bounds["x"][1]
    y_min, y_max = bounds["y"][0], bounds["y"][1]

    boundary = mpatches.Rectangle(
        (x_min, y_min),
        x_max - x_min,
        y_max - y_min,
        fill=False,
        edgecolor="#666666",
        linewidth=0.8,
        zorder=2
    )
    ax.add_patch(boundary)

    ax.set_title(f"{village} {chunk_key}")
    ax.set_xlim(x_max, x_min)
    ax.set_ylim(y_min, y_max)

    ax.set_xticks([x for x in range(x_max, x_min - 1, -10)])
    ax.set_yticks([y for y in range(y_min, y_max + 1, 10)])
    ax.grid(True, linestyle="--", linewidth=0.5, color="gray", zorder=0)

    buf = io.BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight", pad_inches=0.2)
    buf.seek(0)
    plt.close(fig)

    stats = {
        "houses_drawn": houses_drawn,
        "houses_skipped": houses_skipped,
        "mode": "footprints" if use_footprints else "squares",
    }
    return buf, stats


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
    def __init__(self, village: str, chunk_key: str, view_ref):
        super().__init__(title="Add House")
        self.village = village
        self.chunk_key = chunk_key
        self.view_ref = view_ref

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
            classes = load_house_classes()
        except Exception as exc:
            await interaction.response.send_message(f"❌ Failed to load classes: {exc}", ephemeral=True)
            return

        if class_name not in classes.get("classes", {}):
            await interaction.response.send_message(f"❌ Unknown class '{class_name}'.", ephemeral=True)
            return

        town_path = os.path.join(TOWNS_DIR, f"{self.village}.json")
        current_mtime = os.path.getmtime(town_path)
        town_data = load_town_layout(self.village)
        existing_ids = {house.get("id") for house in get_town_houses(town_data) if isinstance(house, dict)}
        if house_id in existing_ids:
            await interaction.response.send_message(f"❌ ID '{house_id}' already exists.", ephemeral=True)
            return

        target_chunk = get_chunk_key_for_point(x, y, town_data)
        warning = ""
        if self.view_ref is not None and current_mtime > self.view_ref.last_mtime:
            warning = "⚠️ Town data changed since you opened the editor. "
        if target_chunk != self.chunk_key:
            warning += f"⚠️ Note: Added to {target_chunk} based on coordinates."

        entry = ensure_chunk_entry(town_data, target_chunk)
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

        save_town_layout(self.village, town_data)

        if self.view_ref is not None:
            self.view_ref.last_mtime = os.path.getmtime(town_path)

        message = f"✅ Added {house_id} to {self.village}. {warning}".strip()
        await interaction.response.send_message(message, ephemeral=True)


class AddHouseButton(ui.Button):
    def __init__(self):
        super().__init__(label="Add House", style=discord.ButtonStyle.primary, row=2)

    async def callback(self, interaction: discord.Interaction):
        view = self.view
        if not isinstance(view, TownEditView) or not view.chunk_key:
            await interaction.response.send_message("Select a chunk first.", ephemeral=True)
            return
        await interaction.response.send_modal(AddHouseModal(view.village, view.chunk_key, view))


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
    def __init__(self, village: str, use_footprints: bool = False):
        super().__init__(timeout=600)
        self.village = village
        self.use_footprints = use_footprints
        self.chunk_key = None
        self.selected_house_id = None
        self.move_mode = False
        self.move_house_id = None
        self.move_x = None
        self.move_y = None
        self.move_chunk_key = None
        self.created_at = time.time()
        self.last_mtime = os.path.getmtime(os.path.join(TOWNS_DIR, f"{village}.json"))

        town_data = load_town_layout(village)
        options = build_chunk_options(town_data)
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

        self.last_mtime = os.path.getmtime(os.path.join(TOWNS_DIR, f"{self.village}.json"))
        town_data = load_town_layout(self.village)
        chunk_entry = town_data.get("houses_by_chunk", {}).get(chunk_key, {})
        chunk_houses = chunk_entry.get("houses", []) if isinstance(chunk_entry, dict) else []

        self.selected_house_id = None
        self.house_select.update_options(build_house_options(chunk_houses, self.village))

        overrides = None
        highlight_id = None
        if self.move_mode and self.move_house_id is not None and self.move_x is not None and self.move_y is not None:
            overrides = {self.move_house_id: {"x": self.move_x, "y": self.move_y}}
            highlight_id = self.move_house_id

        buf, stats = generate_chunk_plot(
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

        town_data = load_town_layout(self.village)
        found = find_house_by_id(town_data, house_id)
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

        town_path = os.path.join(TOWNS_DIR, f"{self.village}.json")
        current_mtime = os.path.getmtime(town_path)
        town_data = load_town_layout(self.village)

        found = find_house_by_id(town_data, self.move_house_id)
        if not found:
            await interaction.response.send_message("House not found.", ephemeral=True)
            return

        old_chunk, index, house = found
        house["x"] = self.move_x
        house["y"] = self.move_y

        new_chunk = get_chunk_key_for_point(self.move_x, self.move_y, town_data)
        warning = ""
        if current_mtime > self.last_mtime:
            warning = "⚠️ Town data changed since you opened the editor. "

        if new_chunk != old_chunk:
            old_entry = ensure_chunk_entry(town_data, old_chunk)
            if index < len(old_entry.get("houses", [])):
                old_entry["houses"].pop(index)
            ensure_chunk_entry(town_data, new_chunk)["houses"].append(house)
            warning += f"⚠️ Moved to {new_chunk}."

        save_town_layout(self.village, town_data)
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
        town_path = os.path.join(TOWNS_DIR, f"{self.village}.json")
        current_mtime = os.path.getmtime(town_path)
        town_data = load_town_layout(self.village)

        found = find_house_by_id(town_data, house_id)
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

        save_town_layout(self.village, town_data)
        self.last_mtime = os.path.getmtime(town_path)

        await interaction.response.send_message(f"✅ Rotated {house_id} to {new_rotation}°. {warning}".strip(), ephemeral=True)




def generate_plot(village: str, points: list, include_fake: bool, user_id: int = None) -> io.BytesIO:
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
    for point in points:
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


def refresh_data_cache() -> dict:
    global data
    data = load_data()
    return data


def set_cached_data(new_data: dict) -> None:
    global data
    data = new_data


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
    points_deps = {
        "refresh_data_cache": refresh_data_cache,
        "require_channel": require_channel,
        "load_yesterdays_points": load_yesterdays_points,
        "create_point": create_point,
        "log_action": log_action,
        "check_milestone": check_milestone,
        "send_milestone_message": send_milestone_message,
        "set_cached_data": set_cached_data,
        "generate_plot": generate_plot,
        "get_top_contributors": get_top_contributors,
    }

    town_deps = {
        "require_channel": require_channel,
        "generate_town_layout_plot": generate_town_layout_plot,
        "list_town_layout_names": list_town_layout_names,
        "house_classes_file": HOUSE_CLASSES_FILE,
        "load_town_layout": load_town_layout,
        "town_edit_view_cls": TownEditView,
        "log_action": log_action,
        "plot_channel_id": config.PLOT_CHANNEL_ID,
        "point_channel_id": config.POINT_CHANNEL_ID,
    }

    admin_deps = {
        "require_channel": require_channel,
        "clear_all_points": clear_all_points,
        "confirm_clear_view_cls": ConfirmClearView,
        "log_action": log_action,
    }

    @tree.command(name="point", description="Add a point to a village!")
    @app_commands.describe(
        x="X coordinate (-160 to 160)",
        y="Y coordinate (-160 to 160)",
        color="Color",
        village="Village name (optional)"
    )
    async def point(interaction: discord.Interaction, x: float, y: float, color: str, village: str = "Dogville"):
        await points_module.handle_point(interaction, x, y, color, village, points_deps)

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

    async def town_village_autocomplete(interaction: discord.Interaction, current: str):
        village_names = list_town_layout_names()
        return [
            app_commands.Choice(name=village, value=village)
            for village in village_names if current.lower() in village.lower()
        ][:25]

    @tree.command(name="plot", description="Plot points from a village.")
    @app_commands.describe(village="Village name (optional)")
    async def plot(interaction: discord.Interaction, village: str = "Dogville"):
        await points_module.handle_plot(interaction, village, points_deps)
    

    @tree.command(name="plotdetailed", description="Plot a detailed map")
    @app_commands.describe(village="Village name (optional)")
    async def plotpure(interaction: discord.Interaction, village: str = "Dogville"):
        await points_module.handle_plot_detailed(interaction, village, points_deps)

    @tree.command(name="townplot", description="Render a town layout from towns/<village>.json")
    @app_commands.describe(
        village="Town layout file name without .json",
        footprints="True = detailed footprint tiles, False = fast basic squares"
    )
    @app_commands.autocomplete(village=town_village_autocomplete)
    async def townplot(interaction: discord.Interaction, village: str = "Dogville", footprints: bool = True):
        await town_module.handle_townplot(interaction, village, footprints, town_deps)

    @tree.command(name="townedit", description="Edit a town layout by chunk")
    @app_commands.describe(village="Town layout file name without .json")
    @app_commands.autocomplete(village=town_village_autocomplete)
    async def townedit(interaction: discord.Interaction, village: str = "Dogville"):
        await town_module.handle_townedit(interaction, village, town_deps)



    @tree.command(name="clearmaps", description="Clear all points from all villages")
    async def clearmaps(interaction: Interaction):
        await admin_module.handle_clearmaps(interaction, admin_deps)
    

    @tree.command(name="villages", description="List all tracked villages and how many points are in each")
    async def list_villages(interaction: discord.Interaction):
        await points_module.handle_villages(interaction, points_deps)



    @tree.command(name="undo", description="Remove a point you added to a village")
    @app_commands.describe(village="Village to remove points from")
    @app_commands.autocomplete(village=village_autocomplete)
    async def undo(interaction: discord.Interaction, village: str = "Dogville"):
        await points_module.handle_undo(interaction, village, points_deps)





    @tree.command(name="noob", description="List all available commands")
    async def noob_command(interaction: discord.Interaction):
        await admin_module.handle_noob(interaction)

    @tree.command(name="residentjson", description="Dumps all users with specific roles as JSON")
    async def resident_json(interaction: discord.Interaction):
        await admin_module.handle_resident_json(interaction, admin_deps)

    @tree.command(name="residentcsv", description="Exports users with specific roles as CSV (Excel/Sheets compatible)")
    async def resident_csv(interaction: discord.Interaction):
        await admin_module.handle_resident_csv(interaction, admin_deps)

    @tree.command(name="sync", description="Sync commands to the guild (admin only)")
    async def sync_commands(interaction: discord.Interaction):
        await admin_module.handle_sync(interaction, tree, admin_deps)

    @tree.command(name="xp", description="Check your XP or someone else's XP")
    @app_commands.describe(user="User to check XP for (optional)")
    async def check_xp(interaction: discord.Interaction, user: discord.User = None):
        await admin_module.handle_xp(interaction, user)

    @tree.command(name="leaderboard", description="View the XP leaderboard")
    @app_commands.describe(limit="Number of top users to show (default: 10)")
    async def leaderboard(interaction: discord.Interaction, limit: int = 10):
        await admin_module.handle_leaderboard(interaction, limit)

    @tree.command(name="incognito", description="Opt in or out of the XP leaderboard")
    @app_commands.describe(enabled="Enable incognito mode (hide from leaderboard)")
    async def incognito(interaction: discord.Interaction, enabled: bool):
        await admin_module.handle_incognito(interaction, enabled)
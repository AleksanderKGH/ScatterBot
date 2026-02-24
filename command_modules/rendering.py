from __future__ import annotations

from datetime import datetime
import io
import os
import random

import discord
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from PIL import Image


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


def generate_town_layout_plot(
    village: str,
    use_footprints: bool,
    load_house_classes_fn,
    load_town_layout_fn,
) -> tuple[io.BytesIO, dict]:
    classes_data = load_house_classes_fn()
    town_data = load_town_layout_fn(village)

    fig, ax = plt.subplots(figsize=(7, 7))

    grid_cfg = town_data.get("grid", {})
    half_w = int(grid_cfg.get("width", 320) / 2)
    half_h = int(grid_cfg.get("height", 320) / 2)

    palette = town_data.get("palette", {})
    class_palette = classes_data.get("class_palette", {})

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
    use_footprints: bool,
    overrides: dict | None,
    highlight_house_id: str | None,
    load_house_classes_fn,
    load_town_layout_fn,
) -> tuple[io.BytesIO, dict]:
    classes_data = load_house_classes_fn()
    town_data = load_town_layout_fn(village)
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


def generate_plot(
    village: str,
    points: list,
    include_fake: bool,
    user_id: int | None,
    get_point_data_fn,
    plot_colors: dict,
    color_options: list[str],
) -> tuple[io.BytesIO, tuple[int, int, str] | None]:
    fig, ax = plt.subplots(figsize=(6, 6))

    for ext in [".png", ".jpg", ".jpeg"]:
        path = f"{village}{ext}"
        if os.path.exists(path):
            try:
                print(f"Attempting to load: {path}")
                img = Image.open(path)
                ax.imshow(img, extent=[160, -160, -160, 160], zorder=0)
                break
            except Exception as exc:
                print(f"Image load failed for {village} at {path}: {exc}")
                break

    for point in points:
        x, y, color = get_point_data_fn(point)
        plot_color = plot_colors.get(color.lower(), color.lower())
        ax.scatter(x, y, color=plot_color, s=50, edgecolors="black")
        ax.text(x, y - 4, f"({int(x)}, {int(y)})", fontsize=10, color="black", ha="center", va="top")

    if include_fake and user_id is not None:
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

        fake_color = random.choice(color_options).lower()
        fake_plot_color = plot_colors.get(fake_color, fake_color)
        ax.scatter(fake_x, fake_y, color=fake_plot_color, zorder=1)
        ax.text(fake_x, fake_y - 4, f"({int(fake_x)}, {int(fake_y)})", fontsize=10, color="black", ha="center", va="top")
        return_info = (fake_x, fake_y, fake_color)
    else:
        return_info = None

    ax.set_title(f"Village: {village}")
    ax.set_xlim(160, -160)
    ax.set_ylim(-160, 160)
    ax.set_xticks([x for x in range(160, -161, -20)])
    ax.set_yticks([y for y in range(-160, 161, 20)])
    ax.grid(True, linestyle="--", linewidth=0.5, color="gray", zorder=0)
    ax.axhline(y=0, color="black", linewidth=1)
    ax.axvline(x=0, color="black", linewidth=1)

    buf = io.BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight", pad_inches=0.2)
    buf.seek(0)
    plt.close(fig)
    return buf, return_info

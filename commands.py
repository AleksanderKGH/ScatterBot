from __future__ import annotations

import discord
from discord import app_commands, Interaction
import io, os
import config
from data import load_data, save_data
from utils import log_action, require_channel, create_point, get_point_data, get_top_contributors, get_point_user
from views import ConfirmClearView
import xp
# https://discord.com/oauth2/authorize?client_id=1385341075572396215&permissions=2147609600
from datetime import datetime
from command_modules import points as points_module, town as town_module, admin as admin_module, rendering as rendering_module, town_storage as town_storage_module, backup_storage as backup_storage_module, town_editor as town_editor_module, registry_helpers as registry_helpers_module, services as services_module, command_registry as command_registry_module


BACKUP_DIR = "backups"
TOWNS_DIR = "towns"
HOUSE_CLASSES_FILE = "house_classes.json"
os.makedirs(BACKUP_DIR, exist_ok=True)
os.makedirs(TOWNS_DIR, exist_ok=True)

def backup_points(data):
    backup_storage_module.backup_points(data, BACKUP_DIR)

def load_yesterdays_points():
    return backup_storage_module.load_yesterdays_points(BACKUP_DIR)


def load_house_classes() -> dict:
    return town_storage_module.load_house_classes(HOUSE_CLASSES_FILE)


def load_town_layout(village: str) -> dict:
    return town_storage_module.load_town_layout(village, TOWNS_DIR)


def save_town_layout(village: str, town_data: dict) -> None:
    town_storage_module.save_town_layout(village, town_data, TOWNS_DIR)


def list_town_layout_names() -> list[str]:
    return town_storage_module.list_town_layout_names(TOWNS_DIR)


def normalize_house_size(footprint: dict, rotation: int) -> tuple[float, float]:
    return rendering_module.normalize_house_size(footprint, rotation)


def expand_footprint_tiles(footprint: dict) -> list[tuple[int, int, str]]:
    return rendering_module.expand_footprint_tiles(footprint)


def rotate_tile(tile_x: int, tile_y: int, base_w: int, base_h: int, rotation: int) -> tuple[int, int]:
    return rendering_module.rotate_tile(tile_x, tile_y, base_w, base_h, rotation)


def get_chunking_config(town_data: dict) -> tuple[int, int, int]:
    return rendering_module.get_chunking_config(town_data)


def parse_chunk_key(chunk_key: str) -> tuple[int, int] | None:
    return rendering_module.parse_chunk_key(chunk_key)


def get_chunk_bounds(row: int, col: int, town_data: dict) -> dict:
    return rendering_module.get_chunk_bounds(row, col, town_data)


def get_chunk_key_for_point(x: float, y: float, town_data: dict) -> str:
    return rendering_module.get_chunk_key_for_point(x, y, town_data)


def ensure_chunk_entry(town_data: dict, chunk_key: str) -> dict:
    return rendering_module.ensure_chunk_entry(town_data, chunk_key)


def build_house_options(houses: list[dict], village: str) -> list[discord.SelectOption]:
    return town_editor_module.build_house_options(houses, village)


def find_house_by_id(town_data: dict, house_id: str) -> tuple[str, int, dict] | None:
    return rendering_module.find_house_by_id(town_data, house_id)


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
    return rendering_module.draw_houses(
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
        highlight_house_id=highlight_house_id,
        highlight_color=highlight_color,
    )


def get_town_houses(town_data: dict) -> list[dict]:
    return rendering_module.get_town_houses(town_data)


def build_chunk_options(town_data: dict) -> list[discord.SelectOption]:
    return rendering_module.build_chunk_options(town_data)


def generate_town_layout_plot(village: str, use_footprints: bool = True) -> tuple[io.BytesIO, dict]:
    return rendering_module.generate_town_layout_plot(
        village=village,
        use_footprints=use_footprints,
        load_house_classes_fn=load_house_classes,
        load_town_layout_fn=load_town_layout,
    )


def generate_chunk_plot(
    village: str,
    chunk_key: str,
    use_footprints: bool = False,
    overrides: dict | None = None,
    highlight_house_id: str | None = None
) -> tuple[io.BytesIO, dict]:
    return rendering_module.generate_chunk_plot(
        village=village,
        chunk_key=chunk_key,
        use_footprints=use_footprints,
        overrides=overrides,
        highlight_house_id=highlight_house_id,
        load_house_classes_fn=load_house_classes,
        load_town_layout_fn=load_town_layout,
    )


def create_town_edit_view(village: str, use_footprints: bool = False):
    return town_editor_module.create_town_edit_view(
        village=village,
        use_footprints=use_footprints,
        towns_dir=TOWNS_DIR,
        load_town_layout_fn=load_town_layout,
        save_town_layout_fn=save_town_layout,
        load_house_classes_fn=load_house_classes,
        get_town_houses_fn=get_town_houses,
        build_chunk_options_fn=build_chunk_options,
        generate_chunk_plot_fn=generate_chunk_plot,
        find_house_by_id_fn=find_house_by_id,
        get_chunk_key_for_point_fn=get_chunk_key_for_point,
        ensure_chunk_entry_fn=ensure_chunk_entry,
    )




def generate_plot(village: str, points: list, include_fake: bool, user_id: int = None) -> io.BytesIO:
    return rendering_module.generate_plot(
        village=village,
        points=points,
        include_fake=include_fake,
        user_id=user_id,
        get_point_data_fn=get_point_data,
        plot_colors=config.PLOT_COLORS,
        color_options=config.COLOR_OPTIONS,
    )


data = load_data()


def refresh_data_cache() -> dict:
    global data
    data = load_data()
    return data


def set_cached_data(new_data: dict) -> None:
    global data
    data = new_data


def check_milestone(old_value: int, new_value: int) -> int:
    return services_module.check_milestone(old_value, new_value)


async def send_milestone_message(client, user_id: int, milestone_type: str, value: int, detail: str = ""):
    await services_module.send_milestone_message(
        client=client,
        user_id=user_id,
        milestone_type=milestone_type,
        value=value,
        point_channel_id=config.POINT_CHANNEL_ID,
        detail=detail,
    )


def clear_all_points():
    global data
    current_data, goats, daily_stats = services_module.clear_all_points(
        load_data_fn=load_data,
        save_data_fn=save_data,
        backup_points_fn=backup_points,
        get_point_user_fn=get_point_user,
        xp_module=xp,
    )
    data = current_data
    return current_data, goats, daily_stats

def register_commands(tree: app_commands.CommandTree):
    command_registry_module.register_commands(
        tree,
        config_module=config,
        points_module=points_module,
        town_module=town_module,
        admin_module=admin_module,
        registry_helpers_module=registry_helpers_module,
        confirm_clear_view_cls=ConfirmClearView,
        require_channel_fn=require_channel,
        load_yesterdays_points_fn=load_yesterdays_points,
        create_point_fn=create_point,
        log_action_fn=log_action,
        check_milestone_fn=check_milestone,
        send_milestone_message_fn=send_milestone_message,
        set_cached_data_fn=set_cached_data,
        generate_plot_fn=generate_plot,
        get_top_contributors_fn=get_top_contributors,
        generate_town_layout_plot_fn=generate_town_layout_plot,
        list_town_layout_names_fn=list_town_layout_names,
        house_classes_file=HOUSE_CLASSES_FILE,
        load_town_layout_fn=load_town_layout,
        create_town_edit_view_fn=create_town_edit_view,
        clear_all_points_fn=clear_all_points,
        refresh_data_cache_fn=refresh_data_cache,
    )
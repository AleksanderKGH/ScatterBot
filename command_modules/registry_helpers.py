from __future__ import annotations

from discord import app_commands


def build_points_deps(
    refresh_data_cache_fn,
    require_channel_fn,
    load_yesterdays_points_fn,
    create_point_fn,
    log_action_fn,
    check_milestone_fn,
    send_milestone_message_fn,
    set_cached_data_fn,
    generate_plot_fn,
    get_top_contributors_fn,
) -> dict:
    return {
        "refresh_data_cache": refresh_data_cache_fn,
        "require_channel": require_channel_fn,
        "load_yesterdays_points": load_yesterdays_points_fn,
        "create_point": create_point_fn,
        "log_action": log_action_fn,
        "check_milestone": check_milestone_fn,
        "send_milestone_message": send_milestone_message_fn,
        "set_cached_data": set_cached_data_fn,
        "generate_plot": generate_plot_fn,
        "get_top_contributors": get_top_contributors_fn,
    }


def build_town_deps(
    require_channel_fn,
    generate_town_layout_plot_fn,
    list_town_layout_names_fn,
    house_classes_file: str,
    load_town_layout_fn,
    town_edit_view_cls,
    log_action_fn,
    plot_channel_id: int,
    point_channel_id: int,
) -> dict:
    return {
        "require_channel": require_channel_fn,
        "generate_town_layout_plot": generate_town_layout_plot_fn,
        "list_town_layout_names": list_town_layout_names_fn,
        "house_classes_file": house_classes_file,
        "load_town_layout": load_town_layout_fn,
        "town_edit_view_cls": town_edit_view_cls,
        "log_action": log_action_fn,
        "plot_channel_id": plot_channel_id,
        "point_channel_id": point_channel_id,
    }


def build_admin_deps(require_channel_fn, clear_all_points_fn, confirm_clear_view_cls, log_action_fn) -> dict:
    return {
        "require_channel": require_channel_fn,
        "clear_all_points": clear_all_points_fn,
        "confirm_clear_view_cls": confirm_clear_view_cls,
        "log_action": log_action_fn,
    }


def color_autocomplete_choices(current: str, color_options: list[str]) -> list[app_commands.Choice[str]]:
    return [
        app_commands.Choice(name=color, value=color)
        for color in color_options
        if current.lower() in color.lower()
    ]


def village_autocomplete_choices(current: str, village_options: list[str]) -> list[app_commands.Choice[str]]:
    return [
        app_commands.Choice(name=village, value=village)
        for village in village_options
        if current.lower() in village.lower()
    ]


def town_village_autocomplete_choices(current: str, list_town_layout_names_fn) -> list[app_commands.Choice[str]]:
    village_names = list_town_layout_names_fn()
    return [
        app_commands.Choice(name=village, value=village)
        for village in village_names
        if current.lower() in village.lower()
    ][:25]

from __future__ import annotations

import discord
from discord import app_commands, Interaction


def register_commands(
    tree: app_commands.CommandTree,
    *,
    config_module,
    points_module,
    town_module,
    admin_module,
    registry_helpers_module,
    confirm_clear_view_cls,
    require_channel_fn,
    load_yesterdays_points_fn,
    create_point_fn,
    log_action_fn,
    check_milestone_fn,
    send_milestone_message_fn,
    set_cached_data_fn,
    generate_plot_fn,
    get_top_contributors_fn,
    generate_town_layout_plot_fn,
    list_town_layout_names_fn,
    house_classes_file: str,
    load_town_layout_fn,
    create_town_edit_view_fn,
    clear_all_points_fn,
    refresh_data_cache_fn,
):
    points_deps = registry_helpers_module.build_points_deps(
        refresh_data_cache_fn=refresh_data_cache_fn,
        require_channel_fn=require_channel_fn,
        load_yesterdays_points_fn=load_yesterdays_points_fn,
        create_point_fn=create_point_fn,
        log_action_fn=log_action_fn,
        check_milestone_fn=check_milestone_fn,
        send_milestone_message_fn=send_milestone_message_fn,
        set_cached_data_fn=set_cached_data_fn,
        generate_plot_fn=generate_plot_fn,
        get_top_contributors_fn=get_top_contributors_fn,
    )

    town_deps = registry_helpers_module.build_town_deps(
        require_channel_fn=require_channel_fn,
        generate_town_layout_plot_fn=generate_town_layout_plot_fn,
        list_town_layout_names_fn=list_town_layout_names_fn,
        house_classes_file=house_classes_file,
        load_town_layout_fn=load_town_layout_fn,
        town_edit_view_cls=create_town_edit_view_fn,
        log_action_fn=log_action_fn,
        plot_channel_id=config_module.PLOT_CHANNEL_ID,
        point_channel_id=config_module.POINT_CHANNEL_ID,
    )

    admin_deps = registry_helpers_module.build_admin_deps(
        require_channel_fn=require_channel_fn,
        clear_all_points_fn=clear_all_points_fn,
        confirm_clear_view_cls=confirm_clear_view_cls,
        log_action_fn=log_action_fn,
    )

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
        return registry_helpers_module.color_autocomplete_choices(current, config_module.COLOR_OPTIONS)

    @point.autocomplete("village")
    async def village_autocomplete(interaction: discord.Interaction, current: str):
        return registry_helpers_module.village_autocomplete_choices(current, config_module.VILLAGE_OPTIONS)

    async def town_village_autocomplete(interaction: discord.Interaction, current: str):
        return registry_helpers_module.town_village_autocomplete_choices(current, list_town_layout_names_fn)

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

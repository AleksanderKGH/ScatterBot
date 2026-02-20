import discord
import json


async def handle_townplot(interaction: discord.Interaction, village: str, footprints: bool, deps: dict):
    require_channel = deps["require_channel"]
    generate_town_layout_plot = deps["generate_town_layout_plot"]
    list_town_layout_names = deps["list_town_layout_names"]
    house_classes_file = deps["house_classes_file"]
    log_action = deps["log_action"]

    if not await require_channel(deps["plot_channel_id"], deps["point_channel_id"])(interaction):
        return

    await interaction.response.defer(ephemeral=True)

    try:
        buf, stats = generate_town_layout_plot(village, use_footprints=footprints)
    except FileNotFoundError:
        available = list_town_layout_names()
        details = ", ".join(available) if available else "No town files found in towns/."
        await interaction.followup.send(
            f"❌ Could not find town layout for **{village}**. Available: {details}",
            ephemeral=True
        )
        return
    except json.JSONDecodeError:
        await interaction.followup.send(
            f"❌ Invalid JSON in towns/{village}.json or {house_classes_file}.",
            ephemeral=True
        )
        return
    except Exception as exc:
        await interaction.followup.send(
            f"❌ Failed to render town layout: {exc}",
            ephemeral=True
        )
        return

    embed = discord.Embed(
        title=f"🏘️ {village} Town Layout",
        description=(
            f"Mode: `{stats['mode']}`"
            f" · "
            f"Houses: `{stats['houses_drawn']}`"
            f" · Roads: `{stats['roads_drawn']}`"
            f" · POIs: `{stats['pois_drawn']}`"
            f" · Skipped: `{stats['houses_skipped']}`"
        ),
        color=discord.Color.teal()
    )
    embed.set_image(url="attachment://town_map.png")

    await log_action(interaction, f"Rendered town layout for **{village}** from JSON (mode: {stats['mode']})")
    await interaction.followup.send(embed=embed, file=discord.File(buf, "town_map.png"), ephemeral=True)


async def handle_townedit(interaction: discord.Interaction, village: str, deps: dict):
    require_channel = deps["require_channel"]
    load_town_layout = deps["load_town_layout"]
    list_town_layout_names = deps["list_town_layout_names"]
    town_edit_view_cls = deps["town_edit_view_cls"]

    if not await require_channel(deps["plot_channel_id"], deps["point_channel_id"])(interaction):
        return

    await interaction.response.defer(ephemeral=True)

    try:
        load_town_layout(village)
    except FileNotFoundError:
        available = list_town_layout_names()
        details = ", ".join(available) if available else "No town files found in towns/."
        await interaction.followup.send(
            f"❌ Could not find town layout for **{village}**. Available: {details}",
            ephemeral=True
        )
        return
    except json.JSONDecodeError:
        await interaction.followup.send(
            f"❌ Invalid JSON in towns/{village}.json.",
            ephemeral=True
        )
        return

    view = town_edit_view_cls(village=village, use_footprints=False)
    embed = discord.Embed(
        title=f"🧰 {village} Town Editor",
        description="Select a chunk to view and edit houses.",
        color=discord.Color.blurple()
    )
    await interaction.followup.send(embed=embed, view=view, ephemeral=True)

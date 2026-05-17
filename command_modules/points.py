import discord
import config
import xp
from data import load_data, save_data
from utils import get_point_data, get_point_user
from views import ConfirmYesterdayView, UndoPointView


async def handle_point(interaction: discord.Interaction, x: float, y: float, color: str, village: str, deps: dict):
    refresh_data_cache = deps["refresh_data_cache"]
    require_channel = deps["require_channel"]
    load_yesterdays_points = deps["load_yesterdays_points"]
    create_point = deps["create_point"]
    log_action = deps["log_action"]
    check_milestone = deps["check_milestone"]
    send_milestone_message = deps["send_milestone_message"]
    set_cached_data = deps["set_cached_data"]

    current_data = refresh_data_cache()
    if not await require_channel(config.POINT_CHANNEL_ID)(interaction):
        return
    if not (-160 <= x <= 160) or not (-160 <= y <= 160):
        await interaction.response.send_message(
            f"🚫 Coordinates must be between -160 and 160. You entered: ({x}, {y})",
            ephemeral=True
        )
        return

    if -10 <= x <= 10 and -10 <= y <= 10:
        await interaction.response.send_message(
            f"🚫 You cannot place points on the bakery! You entered: ({x}, {y})",
            ephemeral=True
        )
        return

    if color.lower() not in [c.lower() for c in config.COLOR_OPTIONS]:
        await interaction.response.send_message(
            f"🚫 Invalid color '{color}'. Valid options are: {', '.join(config.COLOR_OPTIONS)}",
            ephemeral=True
        )
        return

    if village not in current_data:
        current_data[village] = []

    if any(get_point_data(existing) == (x, y, color.lower()) for existing in current_data[village]):
        await interaction.response.send_message(
            f"🚫 That point already exists in '{village}' with the same color.",
            ephemeral=True
        )
        return

    yesterdays_data = load_yesterdays_points()
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
    current_data[village].append(new_point)
    save_data(current_data)
    set_cached_data(current_data)

    old_xp = xp.get_user_xp(interaction.user.id)
    new_xp = xp.add_xp(interaction.user.id, 1)

    color_key = f"color_{color.lower()}"
    old_color_count = xp.get_user_stat(interaction.user.id, color_key)
    new_color_count = xp.add_stat(interaction.user.id, color_key, 1)

    is_incognito = xp.get_user_stat(interaction.user.id, "incognito") == 1

    if not is_incognito:
        xp_milestone = check_milestone(old_xp, new_xp)
        color_milestone = check_milestone(old_color_count, new_color_count)

        if xp_milestone:
            await send_milestone_message(interaction.client, interaction.user.id, "Total XP", xp_milestone)

        if color_milestone:
            await send_milestone_message(interaction.client, interaction.user.id, f"{color.capitalize()} Pearls", color_milestone, "pearls mapped")

    await log_action(interaction, f"Added ({x}, {y}, {color}) to **{village}**")

    success_embed = discord.Embed(
        title="✅ Point documented",
        color=discord.Color.green()
    )
    success_embed.add_field(name="Village", value=village, inline=True)
    success_embed.add_field(name="Coordinates", value=f"({x}, {y})", inline=True)
    success_embed.add_field(name="Color", value=color.capitalize(), inline=True)
    success_embed.add_field(name="Village Total", value=str(len(current_data[village])), inline=True)
    success_embed.add_field(name="XP", value=f"+1 (Total: {new_xp})", inline=False)
    success_embed.set_footer(text=f"Submitted by {interaction.user.display_name}")

    await interaction.response.send_message(embed=success_embed, ephemeral=True)


async def handle_plot(interaction: discord.Interaction, village: str, deps: dict):
    refresh_data_cache = deps["refresh_data_cache"]
    require_channel = deps["require_channel"]
    generate_plot = deps["generate_plot"]
    get_top_contributors = deps["get_top_contributors"]
    log_action = deps["log_action"]

    current_data = refresh_data_cache()
    if not await require_channel(config.PLOT_CHANNEL_ID, config.POINT_CHANNEL_ID)(interaction):
        return
    if village not in current_data or not current_data[village]:
        await interaction.response.send_message("That village has no data.", ephemeral=True)
        return

    buf, fake_point = generate_plot(village, current_data[village], include_fake=True, user_id=interaction.user.id)

    top_contributors = get_top_contributors(current_data[village], limit=3)

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

    embed.set_footer(text=f"Total points: {len(current_data[village])}")
    embed.set_image(url="attachment://map.png")

    await log_action(
        interaction,
        f"Plotted village **{village}** — fake pearl at `({fake_point[0]}, {fake_point[1]})` in `{fake_point[2]}`"
    )

    file = discord.File(buf, "map.png")
    await interaction.response.send_message(embed=embed, file=file, ephemeral=True)


async def handle_plot_detailed(interaction: discord.Interaction, village: str, deps: dict):
    refresh_data_cache = deps["refresh_data_cache"]
    require_channel = deps["require_channel"]
    generate_plot = deps["generate_plot"]
    log_action = deps["log_action"]

    current_data = refresh_data_cache()
    if not await require_channel(config.LOG_CHANNEL_ID)(interaction):
        return
    if village not in current_data or not current_data[village]:
        await interaction.response.send_message("That village has no data.", ephemeral=True)
        return

    buf, _ = generate_plot(village, current_data[village], include_fake=False)
    await log_action(interaction, f"Plotted **pure** village map for **{village}**")
    await interaction.response.send_message(file=discord.File(buf, "scatter.png"), ephemeral=True)


async def handle_villages(interaction: discord.Interaction, deps: dict):
    require_channel = deps["require_channel"]

    if not await require_channel(config.POINT_CHANNEL_ID)(interaction):
        return

    current_data = load_data()

    embed = discord.Embed(
        title="🌾 Tracked Villages",
        description="Here's how many points each village currently has, with color breakdown:",
        color=discord.Color.green()
    )

    for village in config.VILLAGE_OPTIONS:
        points = current_data.get(village, [])
        count = len(points)

        if count == 0:
            embed.add_field(name=f"🏘️ {village}", value="`0` point(s)", inline=False)
            continue

        color_counts = {}
        for point in points:
            _, _, color = get_point_data(point)
            color = color.lower()
            color_counts[color] = color_counts.get(color, 0) + 1

        breakdown = []
        for color, c in sorted(color_counts.items(), key=lambda item: -item[1]):
            percent = (c / count) * 100
            breakdown.append(f"- {color.capitalize()}: {c} ({percent:.0f}%)")

        embed.add_field(
            name=f"🏘️ {village} — `{count}` point{'s' if count != 1 else ''}",
            value="\n".join(breakdown),
            inline=False
        )

    await interaction.response.send_message(embed=embed, ephemeral=True)


async def handle_undo(interaction: discord.Interaction, village: str, deps: dict):
    require_channel = deps["require_channel"]

    is_admin_channel = interaction.channel_id == config.LOG_CHANNEL_ID
    if not await require_channel(config.POINT_CHANNEL_ID, config.LOG_CHANNEL_ID)(interaction):
        return

    data = load_data()

    if village not in data or not data[village]:
        await interaction.response.send_message(
            f"❌ No points to remove from **{village}**.",
            ephemeral=True
        )
        return

    if is_admin_channel:
        points_with_indices = [(i, point) for i, point in enumerate(data[village])]
    else:
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

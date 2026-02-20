from __future__ import annotations

import csv
import io
import json

import discord
import config
import xp


async def handle_clearmaps(interaction: discord.Interaction, deps: dict):
    require_channel = deps["require_channel"]
    clear_all_points = deps["clear_all_points"]
    confirm_clear_view_cls = deps["confirm_clear_view_cls"]

    if not await require_channel(config.LOG_CHANNEL_ID)(interaction):
        return

    view = confirm_clear_view_cls(interaction.user.id)
    await interaction.response.send_message(
        "⚠️ Are you sure you want to **clear all points** in every village?",
        view=view,
        ephemeral=True
    )

    timeout = await view.wait()

    if not view.confirmed and not timeout:
        await interaction.followup.send("❌ Timed out. No data was cleared.", ephemeral=True)
        return

    _, goats, _daily_stats = clear_all_points()
    goat_msg = ""
    if goats:
        goat_lines = [f"🐐 <@{user_id}> mapped **{count}** points in **{village}**!" for user_id, count, village in goats]
        goat_msg = "\n" + "\n".join(goat_lines)
    await interaction.followup.send(f"🧹 All points have been cleared from all villages (villages preserved).{goat_msg}")


async def handle_resident_json(interaction: discord.Interaction, deps: dict):
    require_channel = deps["require_channel"]
    log_action = deps["log_action"]

    if not await require_channel(config.LOG_CHANNEL_ID)(interaction):
        return

    guild = interaction.guild
    roles_to_check = [
        config.RESIDENT_ROLE_ID,
        config.PEARL_ROLE_ID
    ]

    residents = []
    for member in guild.members:
        if any(role.id in roles_to_check for role in member.roles):
            resident_info = {
                "id": member.id,
                "name": str(member),
                "roles": [role.name for role in member.roles if role.id in roles_to_check]
            }
            residents.append(resident_info)

    json_data = json.dumps(residents, indent=2)
    buf = io.BytesIO(json_data.encode("utf-8"))
    buf.seek(0)

    await log_action(interaction, "Exported residents as JSON")
    await interaction.response.send_message(
        content="📋 Here is the list of residents with specified roles:",
        file=discord.File(buf, "residents.json"),
        ephemeral=True
    )


async def handle_resident_csv(interaction: discord.Interaction, deps: dict):
    require_channel = deps["require_channel"]
    log_action = deps["log_action"]

    if not await require_channel(config.LOG_CHANNEL_ID)(interaction):
        return

    guild = interaction.guild
    roles_to_check = [
        config.RESIDENT_ROLE_ID,
        config.PEARL_ROLE_ID
    ]

    residents = []
    for member in guild.members:
        if any(role.id in roles_to_check for role in member.roles):
            roles_list = [role.name for role in member.roles if role.id in roles_to_check]
            residents.append({
                "id": member.id,
                "name": str(member.name),
                "nickname": str(member.nick) if member.nick else "",
                "global_name": str(member.global_name),
                "roles": "; ".join(roles_list)
            })

    output = io.StringIO()
    if residents:
        writer = csv.DictWriter(output, fieldnames=["id", "name", "nickname", "global_name", "roles"])
        writer.writeheader()
        writer.writerows(residents)

    csv_data = output.getvalue()
    buf = io.BytesIO(csv_data.encode("utf-8"))
    buf.seek(0)

    await log_action(interaction, "Exported residents as CSV")
    await interaction.response.send_message(
        content="📊 Here is the CSV file — opens directly in Excel and Google Sheets:",
        file=discord.File(buf, "residents.csv"),
        ephemeral=True
    )


async def handle_sync(interaction: discord.Interaction, tree, deps: dict):
    require_channel = deps["require_channel"]

    if not await require_channel(config.LOG_CHANNEL_ID)(interaction):
        return

    await interaction.response.defer(ephemeral=True)
    guild = discord.Object(id=config.GUILD_ID)
    tree.copy_global_to(guild=guild)
    tree.clear_commands(guild=None)
    await tree.sync()
    synced = await tree.sync(guild=guild)
    await interaction.followup.send(
        f"✅ Synced {len(synced)} guild commands and cleared global commands.",
        ephemeral=True
    )


async def handle_noob(interaction: discord.Interaction):
    from config import POINT_CHANNEL_ID, PLOT_CHANNEL_ID

    embed = discord.Embed(
        title="📖 PearlMapBot Help",
        description="Here's a breakdown of available commands and their usage:",
        color=discord.Color.blurple()
    )

    embed.add_field(
        name="🎯 /point",
        value=f"Add a point to a village. Earns 1 XP per point added.\nMust be used in <#{POINT_CHANNEL_ID}>.",
        inline=False
    )
    embed.add_field(
        name="🗺️ /plot",
        value=f"Generate a plotted map image. Must be used in <#{PLOT_CHANNEL_ID}>.",
        inline=False
    )
    embed.add_field(
        name="📊 /villages",
        value=f"Shows current tracked village stats (use in <#{POINT_CHANNEL_ID}>).",
        inline=False
    )
    embed.add_field(
        name="♻️ /undo",
        value="Remove points from a village. Admins can remove any point, regular users can only remove their own.",
        inline=False
    )
    embed.add_field(
        name="🌟 /xp",
        value="Check your XP total and server rank. Optionally check another user's XP.",
        inline=False
    )
    embed.add_field(
        name="🏆 /leaderboard",
        value="View the top XP earners on the server (default: top 10).",
        inline=False
    )
    embed.add_field(
        name="🧹 /clearmaps",
        value="Admin-only: Clears all village points. XP is preserved. Requires confirmation.",
        inline=False
    )
    embed.set_footer(text="More features coming soon. Stay crusty 🥖")

    await interaction.response.send_message(embed=embed, ephemeral=True)


async def handle_xp(interaction: discord.Interaction, user: discord.User | None):
    target_user = user or interaction.user

    rank, user_xp = xp.get_user_rank(target_user.id)
    goat_points = xp.get_user_stat(target_user.id, "goat_points")
    color_lines = []
    for color_name in config.COLOR_OPTIONS:
        color_key = color_name.lower()
        color_count = xp.get_user_stat(target_user.id, f"color_{color_key}")
        color_lines.append(f"{color_name}: `{color_count}`")

    embed = discord.Embed(
        title=f"🌟 XP Stats for {target_user.display_name}",
        color=discord.Color.gold()
    )

    if rank:
        embed.add_field(name="Total XP", value=f"`{user_xp}`", inline=True)
        embed.add_field(name="Server Rank", value=f"`#{rank}`", inline=True)
    else:
        embed.add_field(name="Total XP", value="`0`", inline=True)
        embed.add_field(name="Server Rank", value="`Unranked`", inline=True)

    embed.add_field(name="🐐 GOAT Points", value=f"`{goat_points}`", inline=True)
    embed.add_field(name="Color Stats", value="\n".join(color_lines), inline=False)

    embed.set_thumbnail(url=target_user.display_avatar.url)
    await interaction.response.send_message(embed=embed, ephemeral=True)


async def handle_leaderboard(interaction: discord.Interaction, limit: int):
    if limit < 1 or limit > 25:
        await interaction.response.send_message("❌ Limit must be between 1 and 25.", ephemeral=True)
        return

    top_users = xp.get_leaderboard(limit * 3)
    top_users = [
        (user_id, user_xp)
        for user_id, user_xp in top_users
        if xp.get_user_stat(user_id, "incognito") != 1
    ][:limit]

    if not top_users:
        await interaction.response.send_message("📊 No one has earned XP yet!", ephemeral=True)
        return

    embed = discord.Embed(
        title="🏆 XP Leaderboard",
        description=f"Top {len(top_users)} pearl mappers",
        color=discord.Color.gold()
    )

    leaderboard_text = []
    for rank, (user_id, user_xp) in enumerate(top_users, start=1):
        medal = "🥇" if rank == 1 else "🥈" if rank == 2 else "🥉" if rank == 3 else f"`{rank}.`"
        leaderboard_text.append(f"{medal} <@{user_id}> — **{user_xp} XP**")

    embed.description = "\n".join(leaderboard_text)

    requester_rank, requester_xp = xp.get_user_rank(interaction.user.id)
    if requester_rank and requester_rank > limit:
        embed.set_footer(text=f"Your rank: #{requester_rank} with {requester_xp} XP")

    await interaction.response.send_message(embed=embed, ephemeral=True)


async def handle_incognito(interaction: discord.Interaction, enabled: bool):
    xp.set_stat(interaction.user.id, "incognito", 1 if enabled else 0)
    if enabled:
        message = "🕶️ Incognito enabled. You will be hidden from the leaderboard."
    else:
        message = "👀 Incognito disabled. You will appear on the leaderboard."
    await interaction.response.send_message(message, ephemeral=True)

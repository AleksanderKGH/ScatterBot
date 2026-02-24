from __future__ import annotations

import discord


def check_milestone(old_value: int, new_value: int) -> int:
    milestones = [100, 200, 300, 400, 500, 600, 700, 800, 900, 1000, 1500, 2000, 2500, 3000, 4000, 5000]
    for milestone in milestones:
        if old_value < milestone <= new_value:
            return milestone
    return 0


async def send_milestone_message(client, user_id: int, milestone_type: str, value: int, point_channel_id: int, detail: str = ""):
    channel = client.get_channel(point_channel_id)
    if channel is None:
        try:
            channel = await client.fetch_channel(point_channel_id)
        except Exception as exc:
            print(f"⚠️ Failed to fetch milestone channel {point_channel_id}: {exc}")
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


def clear_all_points(load_data_fn, save_data_fn, backup_points_fn, get_point_user_fn, xp_module):
    current_data = load_data_fn()
    backup_points_fn(current_data)

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
            user_id = get_point_user_fn(point)
            if user_id:
                user_counts[user_id] = user_counts.get(user_id, 0) + 1
                contributors.add(user_id)

        for user_id, count in user_counts.items():
            if count >= 45:
                xp_module.add_stat(user_id, "goat_points", 1)
                is_incognito = xp_module.get_user_stat(user_id, "incognito") == 1
                if not is_incognito:
                    goats.append((user_id, count, village))

    daily_stats = {
        "total_points": total_points,
        "contributors": len(contributors),
        "villages": villages_mapped
    }

    for village in list(current_data.keys()):
        current_data[village] = []

    save_data_fn(current_data)
    return current_data, goats, daily_stats

#points.py
import discord
import config
import xp

#inder here
import asyncio
import subprocess
import tempfile
import json
import os
import io
import hashlib
import shutil
import sys
#inder end

from typing import Optional, List
from data import load_data, save_data
from utils import get_point_data, get_point_user
from views import ConfirmYesterdayView, UndoPointView
from collections import defaultdict
from command_modules.pearldebt.ledger import add_pearls_owed
temp_dir = tempfile.mkdtemp(prefix="scatterbot_")

PLOT_CACHE: dict[str, dict] = {}
COOK_CACHE: dict[tuple, dict] = {}

COOKING: dict[str, dict] = {}
COOK_ID = defaultdict(int)

VILLAGE_ALIASES = {
    "capital": "An Bread Capital",
}
LAST_COOK_SECONDS: dict[tuple[str, str], int] = {}

NEW_PEARL: dict[str, bool] = defaultdict(lambda: True)
NEW_COLOR: dict[tuple[str, str], bool] = defaultdict(lambda: True)

def normalize_village_key(v: str) -> str:
    return v.strip().replace(" ", "_")

async def handle_point(interaction: discord.Interaction, x: float, y: float, color: str, village: str, deps: dict):
    village_raw = village.strip()
    village = normalize_village_input(village_raw, config.VILLAGE_OPTIONS)
    if not village:
        await interaction.response.send_message("❌ Invalid village.", ephemeral=True)
        return

    refresh_data_cache = deps["refresh_data_cache"]
    require_channel = deps["require_channel"]
    load_yesterdays_points = deps["load_yesterdays_points"]
    create_point = deps["create_point"]
    log_action = deps["log_action"]
    check_milestone = deps["check_milestone"]
    send_milestone_message = deps["send_milestone_message"]
    set_cached_data = deps["set_cached_data"]

    # ─────────────────────────────────────────
    # LOAD DATA FIRST (correct order)
    # ─────────────────────────────────────────
    current_data = refresh_data_cache()
    data = current_data.get(village, [])
    data_hash = make_data_hash(data)

    if not await require_channel(config.POINT_CHANNEL_ID)(interaction):
        return

    # ─────────────────────────────────────────
    # VALIDATION
    # ─────────────────────────────────────────
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

    # ─────────────────────────────────────────
    # DUPLICATE CHECK
    # ─────────────────────────────────────────
    if any(get_point_data(existing) == (x, y, color.lower()) for existing in current_data[village]):
        await interaction.response.send_message(
            f"🚫 That point already exists in '{village}' with the same color.",
            ephemeral=True
        )
        return

    # ─────────────────────────────────────────
    # YESTERDAY CHECK
    # ─────────────────────────────────────────
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

    # ─────────────────────────────────────────
    # APPLY POINT
    # ─────────────────────────────────────────
    new_point = create_point(x, y, color, user_id=interaction.user.id)
    current_data[village].append(new_point)

    save_data(current_data)
    set_cached_data(refresh_data_cache())

    NEW_PEARL[village] = True
    NEW_COLOR[(village, color.lower())] = True

    LAST_COOK_SECONDS[(village, "all")] = 0
    LAST_COOK_SECONDS[(village, color.lower())] = 0

    PLOT_CACHE.pop(village, None)
    for key in list(COOK_CACHE.keys()):
        if key[0] == village:
            del COOK_CACHE[key]

    # ─────────────────────────────────────────
    # XP SYSTEM
    # ─────────────────────────────────────────
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
            await send_milestone_message(
                interaction.client,
                interaction.user.id,
                "Total XP",
                xp_milestone
            )

        if color_milestone:
            await send_milestone_message(
                interaction.client,
                interaction.user.id,
                f"{color.capitalize()} Pearls",
                color_milestone,
                "pearls mapped"
            )

    # ─────────────────────────────────────────
    # LOG + RESPONSE
    # ─────────────────────────────────────────
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
    village_raw = village.strip()
    village = normalize_village_input(village_raw, config.VILLAGE_OPTIONS)
    if not village:
        await interaction.response.send_message("❌ Invalid village.", ephemeral=True)
        return
    refresh_data_cache = deps["refresh_data_cache"]
    require_channel = deps["require_channel"]
    generate_plot = deps["generate_plot"]
    get_top_contributors = deps["get_top_contributors"]
    log_action = deps["log_action"]

    cached = PLOT_CACHE.get(village)

    if cached:
        current_data = refresh_data_cache()
        current_hash = make_data_hash(current_data.get(village, []))

        if cached["hash"] == current_hash:
            buf = cached["buf"]
            embed = cached["embed"]
            buf.seek(0)

            await interaction.response.send_message(
                embed=embed,
                file=discord.File(buf, "map.png"),
                ephemeral=True
            )
            return
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

    #inder here
    PLOT_CACHE[village] = {
        "count": len(current_data[village]),
        "hash": make_data_hash(current_data[village]),
        "buf": buf,
        "embed": embed
    }
    #inder out

async def handle_plot_detailed(interaction: discord.Interaction, village: str, deps: dict):
    village_raw = village.strip()
    village = normalize_village_input(village_raw, config.VILLAGE_OPTIONS)
    if not village:
        await interaction.response.send_message("❌ Invalid village.", ephemeral=True)
        return
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

    village_raw = village.strip()
    village = normalize_village_input(village_raw, config.VILLAGE_OPTIONS)
    if not village:
        await interaction.response.send_message("❌ Invalid village.", ephemeral=True)
        return

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
        msg = (
            f"❌ No points to remove from **{village}**."
            if is_admin_channel
            else f"❌ You haven't added any points to **{village}** yet."
        )
        await interaction.response.send_message(msg, ephemeral=True)
        return

    points_with_indices.reverse()

    view = UndoPointView(
        author_id=interaction.user.id,
        village=village,
        points_with_indices=points_with_indices,
        is_admin=is_admin_channel
    )

    # IMPORTANT: attach deleted point AFTER selection, not placeholder
    removed = points_with_indices[0][1]

    color = get_point_data(removed)[2].lower()

    NEW_PEARL[village] = True
    NEW_COLOR[(village, color)] = True

    LAST_COOK_SECONDS[(village, "all")] = 0
    LAST_COOK_SECONDS[(village, color)] = 0

    await interaction.response.send_message(
        embed=view.get_embed(),
        view=view,
        ephemeral=True
    )
async def handle_cook(interaction: discord.Interaction, color: str, village: str, seconds: int, deps: dict):
    safe_village = village.strip() if village else "Dogville"
    safe_village = safe_village.replace(" ", "_")
    await interaction.response.defer(ephemeral=True)
    village_raw = village.strip()
    village = normalize_village_input(village_raw, config.VILLAGE_OPTIONS)
    color = (color or "all").strip().lower()
    if color in ("", "default", "all"):
        color = "all"
    if not village:
        await interaction.edit_original_response(content="❌ Invalid village.")
        return
    cook_scope = (village, color)
    last_cook = LAST_COOK_SECONDS.get(cook_scope, 0)
    latest_cached = None

    for key, value in COOK_CACHE.items():
        cached_village, cached_color, *_ = key
        if cached_village != village: continue
        if cached_color != color.lower(): continue
        if (latest_cached is None or value.get("seconds", 0) > latest_cached.get("seconds", 0)): latest_cached = value

    # lower/equal cook time requires new pearls
    if seconds <= last_cook:
        has_new = (
            NEW_PEARL[village]
            if color == "all"
            else NEW_COLOR[(village, color)]
        )
        if not has_new:
            if color == "all":
                message = (
                    f"❌ You must use a higher cook time than the previous run.\n"
                    f"Current: **{seconds}s** | Required: **>{last_cook}s**"
                )
            else:
                message = (
                    f"❌ No new {color} pearls detected. "
                    f"Add pearls to reset duration, or increase duration"
                )
            kwargs = {"content": message}
            if latest_cached:
                old_buf = latest_cached["buf"]
                old_embed = latest_cached["embed"]
                old_buf.seek(0)
                kwargs["embed"] = old_embed
                kwargs["attachments"] = [discord.File(old_buf, "route.png")]
            await interaction.edit_original_response(**kwargs)
            return
    refresh_data_cache = deps["refresh_data_cache"]
    require_channel = deps["require_channel"]
    generate_plot = deps["generate_plot"]

    current_data = refresh_data_cache()

    if not await require_channel(
        config.PLOT_CHANNEL_ID,
        config.POINT_CHANNEL_ID
    )(interaction):
        return

    if village not in current_data or not current_data[village]:
        await interaction.edit_original_response(content="That village has no data.")
        return

    if seconds < 1 or seconds > 500:
        await interaction.edit_original_response(content="Seconds must be 1–200.")
        return

    current_data = refresh_data_cache()
    data = current_data.get(village, [])
    data_hash = make_data_hash(data)

    cache_key = (village, color.lower(), seconds)

    old_distance = None

    if latest_cached:
        old_distance = latest_cached.get("distance")

    # EXACT CACHE HIT
    cached = COOK_CACHE.get(cache_key)

    if cached and cached.get("hash") == data_hash:
        buf = cached["buf"]
        embed = cached["embed"]

        buf.seek(0)

        await interaction.followup.send(
            embed=embed,
            file=discord.File(buf, "route.png"),
            ephemeral=True
        )
        return

    # SHOW OLD RESULT IMMEDIATELY WHILE NEW ONE COOKS
    if latest_cached:
        old_buf = latest_cached["buf"]
        old_embed = latest_cached["embed"]

        old_buf.seek(0)

        await interaction.followup.send(
            content="♻️ Showing previous cook while generating updated route...",
            embed=old_embed,
            file=discord.File(old_buf, "route.png"),
            ephemeral=True
        )

    COOK_ID[village] += 1
    job_id = COOK_ID[village]

    existing = COOKING.get(village)

    if isinstance(existing, dict):
        existing["cancelled"] = True

        COOKING[village] = {
            "job_id": job_id,
            "seconds": seconds
        }
    elif existing is not None:
        COOKING.pop(village, None)

    COOKING[village] = {"job_id": job_id,"seconds": seconds}

    await interaction.edit_original_response(
        content=f"⏳ Starting cook for **{village}**... ({seconds}s)"
    )

    buf_plot, _ = generate_plot(village,data,include_fake=True,user_id=interaction.user.id)
    plot_path = os.path.join(temp_dir, f"{safe_village}_bg.png")
    # IMPORTANT: force safe filename (NO SPACES ISSUES)

    with open(plot_path, "wb") as f:
        f.write(buf_plot.getvalue())

    bg_path = plot_path
    old_distance = latest_cached.get("distance") if latest_cached else None

    asyncio.create_task(_cook_worker(interaction,village,safe_village,color,seconds,deps,job_id,plot_path,data_hash,old_distance))
async def run_countdown(village, job_id, seconds, update_status):
    state = COOKING.get(village)
    if not state or state.get("job_id") != job_id or state.get("cancelled"):
        return
    for i in range(seconds):
        state = COOKING.get(village)
        if not state or state.get("job_id") != job_id or state.get("cancelled"):
            return
        await update_status("Cooking", seconds - i)
        await asyncio.sleep(1)

async def _cook_worker(interaction, village, safe_village, color, seconds, deps, job_id, bg_path, data_hash, old_distance):
    refresh_data_cache = deps["refresh_data_cache"]
    cook_scope = (village, color.lower())
    LAST_COOK_SECONDS[cook_scope] = seconds

    cache_key = (village, color.lower(), seconds)

    async def update_status(stage, remaining=None):
        state = COOKING.get(village)
        if not isinstance(state, dict) or state.get("job_id") != job_id or state.get("cancelled"):
            return
        msg = f"🚶 **Cooking {village}**\n\nStatus: **{stage}**"
        if remaining is not None:
            msg += f"\n⏳ Time left: **{remaining}s / {seconds}s**"
        await interaction.edit_original_response(content=msg)

    def run_render_sync(env, temp_dir, safe_village):
        subprocess.run(
            [sys.executable, "command_modules/tsp.py"],
            cwd=os.getcwd(),
            env=env,
            check=True
        )
        return os.path.join(temp_dir, f"{safe_village}.png")

    try:
        plot_path = os.path.join(temp_dir, f"{safe_village}_bg.png")
        points_path = os.path.join(temp_dir, "points.json")

        fresh_data = refresh_data_cache()
        village_points = fresh_data.get(village, [])

        with open(points_path, "w") as f:
            json.dump({village: village_points}, f)

        env = os.environ.copy()
        env.update({
            "INPUT": points_path,
            "GROUP": village,
            "OUTDIR": temp_dir,
            "COLOR_MODE": color,
            "SECONDS": str(seconds),
            "TIME_LIMIT": str(seconds + 3),
            "BG": os.path.abspath(bg_path),
        })

        # 🚀 START BOTH IMMEDIATELY (NO DEPENDENCY)
        render_task = asyncio.create_task(
            asyncio.to_thread(run_render_sync, env, temp_dir, safe_village)
        )

        countdown_task = asyncio.create_task(
            run_countdown(village, job_id, seconds, update_status)
        )

        image_path = await render_task
        await countdown_task

        distance_path = os.path.join(temp_dir, "distance.txt")

        distance = None

        if os.path.exists(distance_path):
            with open(distance_path) as f:
                try:
                    distance = float(f.read().strip())
                except:
                    distance = None

        if not os.path.exists(image_path):
            await interaction.edit_original_response(content="❌ Walk render failed.")
            return

        await update_status("Done")
        from PIL import Image
        import matplotlib.image as mpimg
        base = Image.open(bg_path).convert("RGBA")
        tsp = Image.open(image_path).convert("RGBA")
        # Ensure both images are same size + RGBA before compositing
        tsp = tsp.convert("RGBA")

        if base.size != tsp.size:
            tsp = tsp.resize(base.size, Image.Resampling.LANCZOS)

        base = Image.alpha_composite(base.convert("RGBA"), tsp)
        buf = io.BytesIO()
        base.save(buf, format="PNG")
        buf.seek(0)

        improvement_text = ""
        if (
            old_distance is not None and
            distance is not None
        ):
            diff = old_distance - distance

            if diff > 0:
                improvement_text = f"\n📉 Improved by `{diff:,.2f}`"
            elif diff < 0:
                improvement_text = f"\n📈 Worse by `{abs(diff):,.2f}`"
            else:
                improvement_text = "\n➖ Same distance"

        desc = f"Mode: {color} | Duration: {seconds}s"

        if distance is not None:
            desc += f"\n📏 Distance: `{distance:,.2f}`"

        desc += improvement_text

        embed = discord.Embed(
            title=f"🚶 {village} Walk Simulation",
            description=desc,
            color=discord.Color.purple()
        )
        embed.set_image(url="attachment://route.png")

        COOK_CACHE[cache_key] = {
            "seconds": seconds,
            "hash": data_hash,
            "buf": buf,
            "embed": embed,
            "distance": distance
        }

        # 🔥 cook consumed changes
        if color == "all":
            NEW_PEARL[village] = False
        else:
            NEW_COLOR[(village, color.lower())] = False
        PLOT_CACHE.pop(village, None)

        await interaction.followup.send(
            embed=embed,
            file=discord.File(buf, "route.png"),
            ephemeral=True
        )

    finally:
        state = COOKING.get(village)
        if state and state.get("job_id") == job_id:
            del COOKING[village]

        pass

def make_data_hash(data):
    return hashlib.md5(
        json.dumps(data, sort_keys=True).encode()
    ).hexdigest()

def normalize_village_input(village: str, valid_villages: list[str]) -> Optional[str]:
    v = village.strip().lower()
    # allow direct alias lookup (e.g. "capital" -> real name)
    if v in VILLAGE_ALIASES: return VILLAGE_ALIASES[v]
    for real in valid_villages:
        r_norm = real.strip().lower()
        if r_norm == v: return real
        if r_norm.replace("_", " ") == v or r_norm.replace(" ", "_") == v: return real
    return None
async def resolve_village(interaction: discord.Interaction, village: str, valid_villages: list[str]) -> Optional[str]:
    village = normalize_village_input(village, valid_villages)

    if not village:
        await interaction.response.send_message(
            "❌ Invalid village.",
            ephemeral=True
        )
        return None

    return village
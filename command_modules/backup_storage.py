from __future__ import annotations

from datetime import datetime, timedelta
import json
import os

import psycopg


CANONICAL_VILLAGES = {
    "Dogville",
    "An Bread Capital",
    "Wheat Street",
    "Kitsune Ville",
    "Yeastopia",
    "Rosemary Road",
    "Samurai Village",
    "Little Lamb Loaves",
    "Croissant Creek",
    "Honey Wheat Hollow",
}

VILLAGE_ALIASES = {
    "Honey Wheat Hallow": "Honey Wheat Hollow",
}


def _get_db_dsn() -> str | None:
    return (
        os.getenv("SUPABASE_DB_POOLER_URL")
        or os.getenv("SUPABASE_DB_URL")
        or os.getenv("DATABASE_URL")
    )


def _normalize_point(point) -> dict:
    if isinstance(point, dict):
        if not {"x", "y", "color"}.issubset(point):
            raise ValueError(f"Invalid point object: {point!r}")
        return {
            "x": point["x"],
            "y": point["y"],
            "color": str(point["color"]).lower(),
        }

    if isinstance(point, list) and len(point) >= 3:
        return {
            "x": point[0],
            "y": point[1],
            "color": str(point[2]).lower(),
        }

    raise ValueError(f"Invalid point format: {point!r}")


def _sanitize_backup_data(data: dict) -> tuple[dict[str, list], list[str]]:
    cleaned: dict[str, list] = {}
    rejected_keys: list[str] = []

    for village, points in data.items():
        if not isinstance(village, str) or not isinstance(points, list):
            rejected_keys.append(str(village))
            continue

        village_key = VILLAGE_ALIASES.get(village, village)
        if village_key not in CANONICAL_VILLAGES:
            rejected_keys.append(village)
            continue

        if not points:
            # Skip villages with no points to keep backups compact.
            continue

        if village_key not in cleaned:
            cleaned[village_key] = []
        cleaned[village_key].extend(points)

    return cleaned, rejected_keys


def _anonymize_backup_data(data: dict) -> dict[str, list[dict]]:
    normalized: dict[str, list[dict]] = {}
    for village, points in data.items():
        normalized[village] = [_normalize_point(point) for point in points]
    return normalized


def _upsert_backup_to_db(snapshot_date: str, data: dict, source: str = "discord-bot") -> None:
    dsn = _get_db_dsn()
    if not dsn:
        return

    backup_data = _anonymize_backup_data(data)

    with psycopg.connect(dsn) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                insert into backup_runs (snapshot_date, source)
                values (%s, %s)
                on conflict (snapshot_date)
                do update set source = excluded.source
                returning id
                """,
                (snapshot_date, source),
            )
            backup_run_id = cur.fetchone()[0]

            cur.execute(
                "delete from backup_village_snapshots where backup_run_id = %s",
                (backup_run_id,),
            )

            rows = [
                (
                    backup_run_id,
                    village,
                    json.dumps(points),
                    len(points),
                )
                for village, points in backup_data.items()
            ]

            if rows:
                cur.executemany(
                    """
                    insert into backup_village_snapshots (
                        backup_run_id,
                        village,
                        points_json,
                        point_count
                    ) values (%s, %s, %s::jsonb, %s)
                    """,
                    rows,
                )

        conn.commit()


def backup_points(data, backup_dir: str = "backups") -> None:
    os.makedirs(backup_dir, exist_ok=True)
    date_key = datetime.utcnow().strftime("%Y-%m-%d")
    path = os.path.join(backup_dir, f"{date_key}.json")

    cleaned_data, rejected_keys = _sanitize_backup_data(data)
    if rejected_keys:
        rejected_display = ", ".join(sorted(set(rejected_keys)))
        print(f"⚠️ Rejected non-canonical backup villages for {date_key}: {rejected_display}")

    with open(path, "w", encoding="utf-8") as file:
        json.dump(cleaned_data, file, indent=2)

    # Keep local JSON as source-of-truth while mirroring to Supabase for dashboard reads.
    try:
        _upsert_backup_to_db(date_key, cleaned_data)
    except Exception as exc:
        print(f"⚠️ Supabase backup mirror failed for {date_key}: {exc}")


def load_yesterdays_points(backup_dir: str = "backups") -> dict:
    yesterday = (datetime.utcnow() - timedelta(days=1)).strftime("%Y-%m-%d")
    path = os.path.join(backup_dir, f"{yesterday}.json")
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as file:
            return json.load(file)
    return {}

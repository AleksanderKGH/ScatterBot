from __future__ import annotations

import argparse
import json
import os
import socket
from datetime import date
from pathlib import Path
from typing import Any

import psycopg
from dotenv import load_dotenv


def _parse_snapshot_date(path: Path) -> date:
    try:
        return date.fromisoformat(path.stem)
    except ValueError as exc:
        raise ValueError(f"Backup file name must be YYYY-MM-DD.json: {path.name}") from exc


def _normalize_point(point: Any) -> dict[str, Any]:
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


def _load_backup_file(path: Path) -> dict[str, list[dict[str, Any]]]:
    with path.open("r", encoding="utf-8") as file:
        raw_data = json.load(file)

    if not isinstance(raw_data, dict):
        raise ValueError(f"Backup file must contain a JSON object: {path.name}")

    normalized: dict[str, list[dict[str, Any]]] = {}
    for village, points in raw_data.items():
        if not isinstance(village, str):
            raise ValueError(f"Invalid village key in {path.name}: {village!r}")
        if not isinstance(points, list):
            raise ValueError(f"Village data must be a list in {path.name}: {village}")
        normalized[village] = [_normalize_point(point) for point in points]

    return normalized


def _iter_backup_files(backups_dir: Path) -> list[Path]:
    return sorted(
        path for path in backups_dir.iterdir()
        if path.is_file() and path.suffix.lower() == ".json"
    )


def import_backups(dsn: str, backups_dir: Path, source: str) -> None:
    files = _iter_backup_files(backups_dir)
    if not files:
        print(f"No backup JSON files found in {backups_dir}")
        return

    try:
        with psycopg.connect(dsn) as conn:
            for path in files:
                snapshot_date = _parse_snapshot_date(path)
                backup_data = _load_backup_file(path)

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

                    snapshot_rows = [
                        (
                            backup_run_id,
                            village,
                            json.dumps(points),
                            len(points),
                        )
                        for village, points in backup_data.items()
                    ]

                    if snapshot_rows:
                        cur.executemany(
                            """
                            insert into backup_village_snapshots (
                                backup_run_id,
                                village,
                                points_json,
                                point_count
                            ) values (%s, %s, %s::jsonb, %s)
                            """,
                            snapshot_rows,
                        )

                conn.commit()
                print(f"Imported {path.name}: {len(backup_data)} villages")
    except (psycopg.OperationalError, socket.gaierror) as exc:
        raise SystemExit(
            "Database connection failed. If your URL uses db.<project-ref>.supabase.co "
            "and this machine has no IPv6 route, switch to the Supabase Session Pooler URL "
            "(port 5432 or 6543) and set it as SUPABASE_DB_POOLER_URL."
        ) from exc


def main() -> None:
    load_dotenv()

    parser = argparse.ArgumentParser(description="Import backup JSON files into Supabase.")
    parser.add_argument(
        "--backups-dir",
        default="backups",
        help="Directory containing YYYY-MM-DD.json backup files.",
    )
    parser.add_argument(
        "--dsn",
        default=(
            os.getenv("SUPABASE_DB_POOLER_URL")
            or os.getenv("SUPABASE_DB_URL")
            or os.getenv("DATABASE_URL")
        ),
        help="Postgres connection string for Supabase.",
    )
    parser.add_argument(
        "--source",
        default="discord-bot",
        help="Source label stored with each backup run.",
    )
    args = parser.parse_args()

    if not args.dsn:
        raise SystemExit(
            "Missing Supabase database connection string. "
            "Set SUPABASE_DB_POOLER_URL, SUPABASE_DB_URL, or DATABASE_URL."
        )

    backups_dir = Path(args.backups_dir)
    if not backups_dir.exists():
        raise SystemExit(f"Backups directory does not exist: {backups_dir}")

    import_backups(args.dsn, backups_dir, args.source)


if __name__ == "__main__":
    main()

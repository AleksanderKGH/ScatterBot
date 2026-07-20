from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path


CANONICAL_VILLAGES = [
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
]

ALIASES = {
    "Honey Wheat Hallow": "Honey Wheat Hollow",
    "capital": "An Bread Capital",
    "anc": "An Bread Capital",
    "cap": "An Bread Capital",
    "dogvile": "Dogville",
    "rosemary": "Rosemary Road",
}


def _normalize_village_key(village: str) -> str:
    # Trim common punctuation artifacts introduced by malformed keys.
    return village.strip().strip("'\"\\").strip().lower()


CANONICAL_BY_NORMALIZED = {
    _normalize_village_key(village): village
    for village in CANONICAL_VILLAGES
}

ALIASES_BY_NORMALIZED = {
    _normalize_village_key(source): target
    for source, target in ALIASES.items()
}


def _load_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as file:
        data = json.load(file)
    if not isinstance(data, dict):
        raise ValueError(f"Expected JSON object in {path.name}")
    return data


def _save_json(path: Path, data: dict) -> None:
    with path.open("w", encoding="utf-8") as file:
        json.dump(data, file, indent=2)


def clean_backups(backups_dir: Path, dry_run: bool = False) -> None:
    files = sorted(p for p in backups_dir.iterdir() if p.is_file() and p.suffix.lower() == ".json")

    changed_count = 0
    alias_moves: dict[str, int] = defaultdict(int)
    alias_targets: dict[str, str] = {}
    dropped_counts: dict[str, int] = defaultdict(int)
    empty_village_drops = 0

    for path in files:
        data = _load_json(path)

        cleaned: dict[str, list] = {}
        changed = False

        for village, points in data.items():
            points_list = points if isinstance(points, list) else []
            normalized_key = _normalize_village_key(village)
            canonical_target = CANONICAL_BY_NORMALIZED.get(normalized_key)

            if canonical_target:
                if not points_list:
                    empty_village_drops += 1
                    changed = True
                    continue
                if canonical_target not in cleaned:
                    cleaned[canonical_target] = []
                cleaned[canonical_target].extend(points_list)
                if canonical_target != village:
                    alias_moves[village] += 1
                    alias_targets[village] = canonical_target
                    changed = True
                continue

            alias_target = ALIASES_BY_NORMALIZED.get(normalized_key)
            if alias_target:
                if not points_list:
                    empty_village_drops += 1
                    changed = True
                    continue
                if alias_target not in cleaned:
                    cleaned[alias_target] = []
                cleaned[alias_target].extend(points_list)
                alias_moves[village] += 1
                alias_targets[village] = alias_target
                changed = True
                continue

            dropped_counts[village] += 1
            changed = True

        if set(cleaned.keys()) != set(data.keys()):
            changed = True

        if changed:
            changed_count += 1
            if not dry_run:
                _save_json(path, cleaned)

    print(f"Scanned files: {len(files)}")
    print(f"Changed files: {changed_count}")

    if alias_moves:
        print("Alias remaps (village key -> files affected):")
        for village, count in sorted(alias_moves.items()):
            print(f"  {village} -> {alias_targets[village]}: {count}")

    if dropped_counts:
        print("Dropped village keys (village key -> files affected):")
        for village, count in sorted(dropped_counts.items()):
            print(f"  {village}: {count}")
    else:
        print("No unknown village keys found.")

    print(f"Dropped empty village entries: {empty_village_drops}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Clean backup JSON files to canonical village list.")
    parser.add_argument("--backups-dir", default="backups", help="Path to backups directory.")
    parser.add_argument("--dry-run", action="store_true", help="Report changes without writing files.")
    args = parser.parse_args()

    backups_dir = Path(args.backups_dir)
    if not backups_dir.exists() or not backups_dir.is_dir():
        raise SystemExit(f"Backups directory not found: {backups_dir}")

    clean_backups(backups_dir, dry_run=args.dry_run)


if __name__ == "__main__":
    main()

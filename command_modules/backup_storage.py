from __future__ import annotations

from datetime import datetime, timedelta
import json
import os


def backup_points(data, backup_dir: str = "backups") -> None:
    os.makedirs(backup_dir, exist_ok=True)
    date_key = datetime.utcnow().strftime("%Y-%m-%d")
    path = os.path.join(backup_dir, f"{date_key}.json")
    with open(path, "w", encoding="utf-8") as file:
        json.dump(data, file, indent=2)


def load_yesterdays_points(backup_dir: str = "backups") -> dict:
    yesterday = (datetime.utcnow() - timedelta(days=1)).strftime("%Y-%m-%d")
    path = os.path.join(backup_dir, f"{yesterday}.json")
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as file:
            return json.load(file)
    return {}

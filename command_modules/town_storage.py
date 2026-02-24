from __future__ import annotations

import json
import os


def load_house_classes(house_classes_file: str = "house_classes.json") -> dict:
    if not os.path.exists(house_classes_file):
        raise FileNotFoundError(f"Missing {house_classes_file}")
    with open(house_classes_file, "r", encoding="utf-8") as file:
        return json.load(file)


def load_town_layout(village: str, towns_dir: str = "towns") -> dict:
    path = os.path.join(towns_dir, f"{village}.json")
    if not os.path.exists(path):
        raise FileNotFoundError(f"Missing town file: {path}")
    with open(path, "r", encoding="utf-8") as file:
        return json.load(file)


def save_town_layout(village: str, town_data: dict, towns_dir: str = "towns") -> None:
    path = os.path.join(towns_dir, f"{village}.json")
    with open(path, "w", encoding="utf-8") as file:
        json.dump(town_data, file, indent=2)


def list_town_layout_names(towns_dir: str = "towns") -> list[str]:
    villages = []
    for file_name in os.listdir(towns_dir):
        if file_name.lower().endswith(".json"):
            villages.append(os.path.splitext(file_name)[0])
    return sorted(villages)

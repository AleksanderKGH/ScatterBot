import argparse
import json
from pathlib import Path


def chunk_index_x(x: float, min_x: int, chunk_size: int, columns: int) -> int:
    idx = int((x - min_x) // chunk_size)
    return max(0, min(columns - 1, idx))


def chunk_index_y(y: float, max_y: int, chunk_size: int, rows: int) -> int:
    idx = int((max_y - y) // chunk_size)
    return max(0, min(rows - 1, idx))


def chunk_bounds(row: int, col: int, min_x: int, max_y: int, chunk_size: int) -> dict:
    x_min = min_x + (col * chunk_size)
    x_max = x_min + chunk_size
    y_max = max_y - (row * chunk_size)
    y_min = y_max - chunk_size
    return {
        "x": [x_min, x_max],
        "y": [y_min, y_max],
    }


def group_houses(town_data: dict, chunk_size: int = 80) -> dict:
    grid = town_data.get("grid", {})
    width = int(grid.get("width", 320))
    height = int(grid.get("height", 320))

    min_x = -width // 2
    max_x = width // 2
    min_y = -height // 2
    max_y = height // 2

    columns = width // chunk_size
    rows = height // chunk_size

    houses = town_data.get("houses", [])
    grouped = {}

    for house in houses:
        if not isinstance(house, dict):
            continue

        x = float(house.get("x", 0))
        y = float(house.get("y", 0))

        col = chunk_index_x(x, min_x, chunk_size, columns)
        row = chunk_index_y(y, max_y, chunk_size, rows)
        key = f"r{row}c{col}"

        if key not in grouped:
            grouped[key] = {
                "bounds": chunk_bounds(row, col, min_x, max_y, chunk_size),
                "houses": [],
            }

        grouped[key]["houses"].append(house)

    grouped = dict(sorted(grouped.items(), key=lambda item: item[0]))

    town_data["houses_by_chunk"] = grouped
    town_data.pop("houses", None)
    town_data.setdefault("chunking", {})
    town_data["chunking"].update(
        {
            "mode": "80x80",
            "chunk_size": chunk_size,
            "grid_chunks": {"rows": rows, "cols": columns},
            "chunk_key_format": "r{row}c{col}",
            "anchor": "top_left",
        }
    )
    return town_data


def main() -> None:
    parser = argparse.ArgumentParser(description="Group town houses into 80x80 chunks.")
    parser.add_argument("town_file", help="Path to towns/<name>.json")
    parser.add_argument("--chunk-size", type=int, default=80)
    args = parser.parse_args()

    path = Path(args.town_file)
    if not path.exists():
        raise FileNotFoundError(f"Town file not found: {path}")

    town_data = json.loads(path.read_text(encoding="utf-8"))
    grouped = group_houses(town_data, chunk_size=args.chunk_size)
    path.write_text(json.dumps(grouped, indent=2), encoding="utf-8")

    total = sum(len(value.get("houses", [])) for value in grouped.get("houses_by_chunk", {}).values())
    chunks = len(grouped.get("houses_by_chunk", {}))
    print(f"Grouped {total} houses into {chunks} chunks in {path}")


if __name__ == "__main__":
    main()

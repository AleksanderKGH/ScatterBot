import json
import re
from collections import defaultdict

INPUT = "points.json"
OUTPUT = "points2.json"

with open(INPUT, "r", encoding="utf-8") as f:
    data = json.load(f)

result = {}

for village, entries in data.items():
    grouped = defaultdict(lambda: defaultdict(list))

    for e in entries:
        uid = str(e["user_id"])
        color = e["color"]

        grouped[uid][color].append((e["x"], e["y"]))

    result[village] = {
        uid: dict(colors)
        for uid, colors in grouped.items()
    }

# -------- WRITE JSON FIRST --------
with open(OUTPUT, "w", encoding="utf-8") as f:
    json.dump(result, f, indent=2)

# -------- POST-PROCESS: COMPRESS COORD PAIRS --------
with open(OUTPUT, "r", encoding="utf-8") as f:
    text = f.read()

text = re.sub(
    r"\[\s*([-\d.]+)\s*,\s*([-\d.]+)\s*\]",
    r"[\1,\2]",
    text
)

with open(OUTPUT, "w", encoding="utf-8") as f:
    f.write(text)

print("done")
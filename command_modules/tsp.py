#tsp.py
#!/usr/bin/env python3

import json
import math
import random
import time
import os
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.image as mpimg
from matplotlib.patches import Rectangle

# =========================
# ⚙️ CONTROL PANEL (EQUIVALENT OF BASH VARS)
# =========================

GROUP = os.environ.get("GROUP", "Dogville")
GROUP_FILE = GROUP.replace(" ", "_")

INPUT = os.environ.get("INPUT", os.path.join(os.path.dirname(__file__), "..", "points.json"))
OUTDIR = os.environ.get("OUTDIR", os.path.dirname(__file__))

WORLD_SIZE = int(os.environ.get("WORLD_SIZE", 160))
CANVAS_SIZE = int(os.environ.get("CANVAS_SIZE", 1280))

TIME_LIMIT = int(os.environ.get("TIME_LIMIT", 5))

SA_ITER = 2000000
SA_COOLING = 0.99995
REFINE_PASSES = 2

SEED = 42

LINE_WIDTH = 1.3
NODE_SIZE = 8

X_OFFSET = 0
Y_OFFSET = 1

X_SQUEEZE = 1.0
Y_SQUEEZE = 1.0

MARGIN = 0

COLOR_FILTER = os.environ.get("COLOR_MODE", "")
if COLOR_FILTER == "all":
    COLOR_FILTER = ""

os.makedirs(OUTDIR, exist_ok=True)

PNG = os.path.join(OUTDIR, f"{GROUP_FILE}.png")
BENCH = os.path.join(OUTDIR, "benchmark.txt")

# optional background (was $BG in bash)
BG = os.environ.get("BG", "")

CACHE_FILE = os.path.join(OUTDIR, "cook_cache.json")

def load_cook_cache():
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, "r") as f:
                return json.load(f)
        except:
            return {}
    return {}

def save_cook_cache(cache):
    tmp = CACHE_FILE + ".tmp"
    with open(tmp, "w") as f:
        json.dump(cache, f)
    os.replace(tmp, CACHE_FILE)

# =========================
# 1/3 EXTRACT POINTS
# =========================

with open(INPUT) as f:
    data = json.load(f)

points = data.get(GROUP, [])

# =========================
# 2/3 OPTIMIZATION ENGINE
# =========================
COOK_CACHE = load_cook_cache()
random.seed(SEED)
start_time = time.perf_counter()

def time_up():
    return (time.perf_counter() - start_time) > TIME_LIMIT

RAW = [
    (float(p["x"]), float(p["y"]))
    for p in points
    if not (COLOR_FILTER and str(p.get("color", "")).lower() != COLOR_FILTER)
]

N = len(RAW)

cache_key = f"{GROUP}|{COLOR_FILTER}|{INPUT}"
cached = COOK_CACHE.get(cache_key)

if cached:
    best_route = cached["route"]
    best_cost = cached["cost"]

    print("CACHE HIT:", best_cost)
    print("DONE (cached)")
    exit(0)

def dist(a, b):
    return math.hypot(a[0] - b[0], a[1] - b[1])

def cost(route):
    if N == 0:
        return 0
    return sum(dist(RAW[route[i]], RAW[route[(i + 1) % N]]) for i in range(N))

def fallback():
    return list(range(N))

def nn(start):
    if N == 0:
        return []

    unused = set(range(N))
    unused.discard(start)
    route = [start]

    while unused and not time_up():
        last = route[-1]
        nxt = min(unused, key=lambda j: dist(RAW[last], RAW[j]))
        route.append(nxt)
        unused.remove(nxt)

    return route

def two_opt(route):
    improved = True

    while improved and not time_up():
        improved = False

        for i in range(N):
            if time_up():
                return route

            for j in range(i + 2, N):
                if time_up():
                    return route

                if i == 0 and j == N - 1:
                    continue

                a, b = route[i], route[i + 1]
                c, d = route[j], route[(j + 1) % N]

                if dist(RAW[a], RAW[b]) + dist(RAW[c], RAW[d]) > dist(RAW[a], RAW[c]) + dist(RAW[b], RAW[d]):
                    route[i + 1:j + 1] = reversed(route[i + 1:j + 1])
                    improved = True

    return route

def insertion():
    if N < 2:
        return fallback()

    unvisited = set(range(N))
    a = unvisited.pop()
    b = unvisited.pop() if unvisited else a

    route = [a, b]

    while unvisited and not time_up():
        best_city = None
        best_pos = 0
        best_delta = float("inf")

        for city in unvisited:
            for i in range(len(route)):
                j = (i + 1) % len(route)

                a = route[i]
                b = route[j]

                delta = (
                    dist(RAW[a], RAW[city]) +
                    dist(RAW[city], RAW[b]) -
                    dist(RAW[a], RAW[b])
                )

                if delta < best_delta:
                    best_delta = delta
                    best_city = city
                    best_pos = j

        if best_city is None:
            break

        route.insert(best_pos, best_city)
        unvisited.remove(best_city)

    return route

def SA(route):
    if N < 2:
        return route

    T = 1000.0
    cooling = SA_COOLING

    best = route[:]
    best_cost = cost(route)

    while not time_up():
        i, j = sorted(random.sample(range(N), 2))
        new = route[:]

        if random.random() < 0.5:
            new[i:j] = reversed(new[i:j])
        else:
            new[i], new[j] = new[j], new[i]

        delta = cost(new) - cost(route)

        if delta < 0 or random.random() < math.exp(-delta / T):
            route = new
            c = cost(new)

            if c < best_cost:
                best = new[:]
                best_cost = c

        T *= cooling
        if T < 1e-5:
            break

    return best

best_route = fallback()
best_cost = cost(best_route)

while not time_up():
    r1 = nn(random.randint(0, N - 1)) if N else []
    r1 = two_opt(r1)

    r2 = insertion()
    r2 = two_opt(r2)

    r3 = SA(r1)

    for r in (r1, r2, r3):
        if not r:
            continue
        c = cost(r)
        if c < best_cost:
            best_cost = c
            best_route = r

if not best_route:
    best_route = fallback()


with open(os.path.join(OUTDIR, "distance.txt"), "w") as f:
    f.write(str(best_cost))

print("BEST:", best_cost)

cache_key = f"{GROUP}|{COLOR_FILTER}|{INPUT}"

COOK_CACHE[cache_key] = {
    "route": best_route,
    "cost": best_cost,
    "time": time.time()
}

save_cook_cache(COOK_CACHE)

# =========================
# 3/3 RENDERING
# =========================

raw = RAW

route = best_route

if not route:
    route = list(range(len(raw)))

scale = (CANVAS_SIZE - 2 * MARGIN) / (WORLD_SIZE * 2)

CENTER_X = CANVAS_SIZE / 2
CENTER_Y = CANVAS_SIZE / 2

pts = []

for i in route:
    if i >= len(raw):
        continue

    x, y = raw[i]

    nx = (x + WORLD_SIZE) * scale + MARGIN
    ny = (y + WORLD_SIZE) * scale + MARGIN

    nx = CANVAS_SIZE - nx

    nx = CENTER_X + (nx - CENTER_X) * X_SQUEEZE
    ny = CENTER_Y + (ny - CENTER_Y) * Y_SQUEEZE

    nx += X_OFFSET
    ny += Y_OFFSET

    pts.append((nx, ny))

if not pts:
    pts = [(0, 0), (CANVAS_SIZE, CANVAS_SIZE)]

xs = [p[0] for p in pts] + [pts[0][0]]
ys = [p[1] for p in pts] + [pts[0][1]]

bg = mpimg.imread(BG) if BG and os.path.exists(BG) else None

fig, ax = plt.subplots(figsize=(12.8, 12.8), dpi=100)
fig.patch.set_alpha(0)
ax.set_facecolor((0, 0, 0, 0))

#if bg is not None:
#    ax.imshow(bg, extent=[0, CANVAS_SIZE, 0, CANVAS_SIZE])

ax.plot(xs, ys, linewidth=LINE_WIDTH, color="white")
ax.scatter(xs[:-1], ys[:-1], s=NODE_SIZE, color="white", edgecolors="black", linewidths=0.3)

ax.set_xlim(0, CANVAS_SIZE)
ax.set_ylim(0, CANVAS_SIZE)
ax.axis("off")

plt.savefig(PNG, bbox_inches=None, pad_inches=0, transparent=True)
plt.close(fig)

print("DONE")
print("Group:", GROUP, "| Color:", COLOR_FILTER)
print("Image:", PNG)
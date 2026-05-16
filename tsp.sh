#!/usr/bin/env bash

########################################
# ⚙️ CONTROL PANEL
########################################
# 🏘️ GROUP / VILLAGE SELECTOR
GROUP="${GROUP:-Dogville}"
GROUP_FILE="${GROUP// /_}"

INPUT="${INPUT:-$(dirname "$0")/points.json}"
OUTDIR="${OUTDIR:-$(dirname "$0")}"

WORLD_SIZE=160
CANVAS_SIZE=1280

TIME_LIMIT="${TIME_LIMIT:-5}"

SA_ITER=2000000
SA_COOLING=0.99995
REFINE_PASSES=2

SEED=42

LINE_WIDTH=1.3
NODE_SIZE=8

# 🎯 OFFSETS (UNCHANGED)
X_OFFSET=0
Y_OFFSET=1

# 🎯 CENTER SQUEEZE (UNCHANGED)
X_SQUEEZE=1.0 # 0.95
Y_SQUEEZE=1.0

# 🧱 VISUAL MARGIN
MARGIN=0 #104



# 🎨 OPTIONAL COLOR FILTER
# leave empty "" = ALL COLORS
COLOR_FILTER="${COLOR_MODE:-}"
if [ "$COLOR_FILTER" = "all" ]; then
    COLOR_FILTER=""
fi

########################################

mkdir -p "$OUTDIR"

CSV="$OUTDIR/points.csv"
ROUTE="$OUTDIR/route.txt"
PNG="$OUTDIR/route.png"
BENCH="$OUTDIR/benchmark.txt"

echo "[1/3] Extracting coordinates..."

# =========================
# SAFE GROUP + OPTIONAL COLOR FILTER
# =========================
python3 << EOF
import json

group = "$GROUP"
color = "$COLOR_FILTER".lower()

with open("$INPUT") as f:
    data = json.load(f)

points = data.get(group, [])

with open("$CSV", "w") as out:
    for p in points:
        pcolor = str(p.get("color", "")).lower()

        if color and color != "":
            if pcolor != color:
                continue

        out.write(f"{p['x']},{p['y']}\n")
EOF

echo "[2/3] Cooking (CRASH-PROOF $TIME_LIMIT sec)..."

python3 << EOF
import math, random, time, os

random.seed($SEED)

csv_path = "$CSV"
route_out = "$ROUTE"
bench_out = "$BENCH"

WORLD = $WORLD_SIZE
W = H = $CANVAS_SIZE
MARGIN = $MARGIN

X_OFFSET = $X_OFFSET
Y_OFFSET = $Y_OFFSET

X_SQUEEZE = $X_SQUEEZE
Y_SQUEEZE = $Y_SQUEEZE

start_time = time.perf_counter()
TIME_LIMIT = int(os.environ.get("TIME_LIMIT", $TIME_LIMIT))

def time_up():
    return (time.perf_counter() - start_time) > TIME_LIMIT

# =========================
# LOAD DATA (SAFE EMPTY)
# =========================
with open(csv_path) as f:
    RAW = [tuple(map(float, l.split(","))) for l in f if l.strip()]

N = len(RAW)

def dist(a,b):
    return math.hypot(a[0]-b[0], a[1]-b[1])

def cost(route):
    if N == 0:
        return 0
    return sum(dist(RAW[route[i]], RAW[route[(i+1)%N]]) for i in range(N))

def fallback():
    return list(range(N))

# =========================
# NEAREST NEIGHBOR
# =========================
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

# =========================
# 2-OPT
# =========================
def two_opt(route):
    improved = True

    while improved and not time_up():
        improved = False

        for i in range(N):
            if time_up(): return route

            for j in range(i+2, N):
                if time_up(): return route

                if i == 0 and j == N-1:
                    continue

                a,b = route[i], route[i+1]
                c,d = route[j], route[(j+1)%N]

                if dist(RAW[a],RAW[b]) + dist(RAW[c],RAW[d]) > dist(RAW[a],RAW[c]) + dist(RAW[b],RAW[d]):
                    route[i+1:j+1] = reversed(route[i+1:j+1])
                    improved = True

    return route

# =========================
# INSERTION
# =========================
def insertion():
    if N < 2:
        return fallback()

    unvisited = set(range(N))
    a = unvisited.pop()
    b = unvisited.pop() if unvisited else a

    route = [a,b]

    while unvisited and not time_up():
        best_city = None
        best_pos = 0
        best_delta = float("inf")

        for city in unvisited:
            for i in range(len(route)):
                j = (i+1) % len(route)

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

# =========================
# SA
# =========================
def SA(route):
    if N < 2:
        return route  # or fallback()

    T = 1000.0
    cooling = $SA_COOLING

    best = route[:]
    best_cost = cost(route)

    while not time_up():

        if N < 2:
            break

        i, j = sorted(random.sample(range(N), 2))
        new = route[:]

        if random.random() < 0.5:
            new[i:j] = reversed(new[i:j])
        else:
            new[i], new[j] = new[j], new[i]

        delta = cost(new) - cost(route)

        if delta < 0 or random.random() < math.exp(-delta/T):
            route = new

            c = cost(new)
            if c < best_cost:
                best = new[:]
                best_cost = c

        T *= cooling
        if T < 1e-5:
            break

    return best

# =========================
# MAIN LOOP
# =========================
best_route = fallback()
best_cost = cost(best_route)

while not time_up():

    r1 = nn(random.randint(0,N-1)) if N else []
    r1 = two_opt(r1)

    r2 = insertion()
    r2 = two_opt(r2)

    r3 = SA(r1)

    for r in (r1,r2,r3):
        if not r:
            continue
        c = cost(r)
        if c < best_cost:
            best_cost = c
            best_route = r

if not best_route:
    best_route = fallback()

with open(route_out,"w") as f:
    f.write("\n".join(str(i) for i in best_route))

with open(os.path.join("$OUTDIR", "distance.txt"), "w") as f:
    f.write(str(best_cost))

print("BEST:", best_cost)
EOF

echo "[3/3] Rendering HD overlay..."

python3 << EOF
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
plt.close("all")
import matplotlib.image as mpimg
from matplotlib.patches import Rectangle
import os

route_path = "$ROUTE"
bg_path = "$BG"
csv_path = "$CSV"

W = H = $CANVAS_SIZE
WORLD = $WORLD_SIZE
MARGIN = $MARGIN

X_OFFSET = $X_OFFSET
Y_OFFSET = $Y_OFFSET

X_SQUEEZE = $X_SQUEEZE
Y_SQUEEZE = $Y_SQUEEZE

raw = [tuple(map(float, l.split(","))) for l in open(csv_path) if l.strip()]

try:
    route = [int(l.strip()) for l in open(route_path) if l.strip()]
except:
    route = list(range(len(raw)))

if not route:
    route = list(range(len(raw)))

scale = (W - 2*MARGIN) / (WORLD * 2)

CENTER_X = W/2
CENTER_Y = H/2

pts = []

for i in route:
    if i >= len(raw):
        continue

    x,y = raw[i]

    nx = (x + WORLD) * scale + MARGIN
    ny = (y + WORLD) * scale + MARGIN

    nx = W - nx

    nx = CENTER_X + (nx - CENTER_X) * X_SQUEEZE
    ny = CENTER_Y + (ny - CENTER_Y) * Y_SQUEEZE

    nx += X_OFFSET
    ny += Y_OFFSET

    pts.append((nx,ny))

if not pts:
    pts = [(0,0),(W,H)]

xs = [p[0] for p in pts] + [pts[0][0]]
ys = [p[1] for p in pts] + [pts[0][1]]

bg = mpimg.imread(bg_path) if os.path.exists(bg_path) else None

fig, ax = plt.subplots(figsize=(12.8, 12.8), dpi=100)

fig.patch.set_alpha(0)
ax.set_facecolor((0,0,0,0))

#if bg is not None:
#    ax.imshow(bg, extent=[0,W,0,H])
#
#ax.add_patch(Rectangle((0,0),W,H,color="black",alpha=0.10))

ax.plot(xs,ys,linewidth=$LINE_WIDTH,color="white", alpha=1.0)
ax.scatter(xs[:-1],ys[:-1],s=$NODE_SIZE,color="white", edgecolors="black", linewidths=0.3)

ax.set_xlim(0,W)
ax.set_ylim(0,H)
ax.axis("off")

plt.savefig("$PNG", bbox_inches=None, pad_inches=0, transparent=True)
plt.close(fig)
EOF

echo
echo "DONE (GROUP + COLOR SYSTEM FIXED)"
echo "Group: $GROUP | Color: $COLOR_FILTER"
echo "Image: $PNG"

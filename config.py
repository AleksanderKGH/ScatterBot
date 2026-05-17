import os
from dotenv import load_dotenv



# Load environment variables


load_dotenv()

ENV = os.getenv("ENV", "DEV")


def _require_str(name: str) -> str:
    value = os.getenv(name)
    if value is None or not value.strip():
        raise ValueError(f"Missing required environment variable: {name}")
    return value.strip()


def _require_int(name: str) -> int:
    raw = _require_str(name)
    try:
        return int(raw)
    except ValueError as exc:
        raise ValueError(f"Environment variable {name} must be an integer, got: {raw!r}") from exc


TOKEN = _require_str("DISCORD_TOKEN")
LOG_CHANNEL_ID = _require_int("LOG_CHANNEL_ID")
POINT_CHANNEL_ID = _require_int("POINT_CHANNEL_ID")
PLOT_CHANNEL_ID = _require_int("PLOT_CHANNEL_ID")
GUILD_ID = _require_int("GUILD_ID")
RESIDENT_ROLE_ID = _require_int("RESIDENT_ROLE_ID")
PEARL_ROLE_ID = _require_int("PEARL_ROLE_ID")

DATA_FILE = "points.json"

# Village options - can be overridden via VILLAGES env var (comma-separated)
DEFAULT_VILLAGES = [
    "Dogville",
    "Wheat Street",
    "An Bread Capital",
    "Honey Wheat Hallow",
    "Yeastopia",
    "Harvesta",
    "Kitsune Ville"
]

# Load villages from environment or use defaults
villages_env = os.getenv("VILLAGES")
if villages_env:
    VILLAGE_OPTIONS = [v.strip() for v in villages_env.split(",") if v.strip()]
else:
    VILLAGE_OPTIONS = DEFAULT_VILLAGES

COLOR_OPTIONS = ["Black", "Blue", "Cyan", "Green", "Magenta", "Red", "White", "Yellow"]
PLOT_COLORS = {
    "green": "#26fa74"}
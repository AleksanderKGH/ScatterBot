import os
from dotenv import load_dotenv



# Load environment variables


load_dotenv()

ENV = os.getenv("ENV", "DEV")
TOKEN = os.getenv("DISCORD_TOKEN")
LOG_CHANNEL_ID = int(os.getenv("LOG_CHANNEL_ID"))
POINT_CHANNEL_ID = int(os.getenv("POINT_CHANNEL_ID"))
PLOT_CHANNEL_ID = int(os.getenv("PLOT_CHANNEL_ID"))
GUILD_ID = int(os.getenv("GUILD_ID"))
RESIDENT_ROLE_ID = int(os.getenv("RESIDENT_ROLE_ID"))
PEARL_ROLE_ID = int(os.getenv("PEARL_ROLE_ID"))

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
    VILLAGE_OPTIONS = [v.strip() for v in villages_env.split(",")]
else:
    VILLAGE_OPTIONS = DEFAULT_VILLAGES

COLOR_OPTIONS = ["Black", "Blue", "Cyan", "Green", "Magenta", "Red", "White", "Yellow"]
PLOT_COLORS = {
    "green": "#26fa74"}
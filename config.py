import os
from dotenv import load_dotenv

load_dotenv()

# Load environment variables
TOKEN = os.getenv("DISCORD_TOKEN")
LOG_CHANNEL_ID = int(os.getenv("LOG_CHANNEL_ID"))
POINT_CHANNEL_ID = int(os.getenv("POINT_CHANNEL_ID"))
PLOT_CHANNEL_ID = int(os.getenv("PLOT_CHANNEL_ID"))


DATA_FILE = "points.json"

COLOR_OPTIONS = ["Black", "Blue", "Cyan", "Green", "Magenta", "Red", "White", "Yellow"]
PLOT_COLORS = {
    "green": "#26fa74"}
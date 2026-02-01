# 🐚 PearlMapBot

A Discord bot that tracks and visualizes village map coordinates for a game world using colorful scatter plots. Perfect for managing spatial data submissions and visual insights from your Discord community.

---

## 🧩 Features

- Slash commands to add and plot points on a 2D map.
- Predefined color options with visual legends.
- Fake decoy point generated daily to deter map copying.
- Image overlays for maps with optional background images.
- Channel-based access control for logging and sensitive actions.
- JSON-based persistent storage (no database needed).
- Autocomplete support for villages and colors.
- Beautiful embed-based help and summaries.

---

## 🚀 Getting Started

### 1. Clone the Repo

```bash
git clone https://github.com/AleksanderKGH/ScatterBot.git
```

### 2. Set Up Environment

Create a .env file with the proper tokens
ENV=DEV/PROD
DISCORD_TOKEN=
LOG_CHANNEL_ID=
POINT_CHANNEL_ID=
PLOT_CHANNEL_ID=
GUILD_ID=
RESIDENT_ROLE_ID=
VILLAGES= (comma seperated)

🔒 Never commit this file! .env is in .gitignore for your safety.

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### Run the Bot

```bash
python main.py
```

## ⚙️ Bot Commands

| Command      | Description                                     |
| ------------ | ----------------------------------------------- |
| `/point`     | Add a colored point to a named village map.     |
| `/plot`      | Show a plot of a village’s data with fake dot.  |
| `/plotclean` | Plot map without the fake decoy point.          |
| `/villages`  | Show a summary of each village’s point stats.   |
| `/help`      | Display all commands in a cute embed.           |
| `/clearmaps` | 🔒 Clear all data in all villages (admin only). |

## 📁 Project Structure

pearlmapbot/
│
├── main.py # Entry point
├── commands.py # Slash command logic
├── data.py # Data loading/saving helpers
├── utils.py # Logging, role checks, etc.
├── config.py # Channel/role/color settings
├── points.json # Stored point data (created at runtime)
├── .env # Discord token (ignored)
├── .gitignore # Files to exclude from Git
└── README.md

## 💡 Suggestions or Contributions?

Feel free to open issues or pull requests! This bot was built for managing tight-knit game communities and is open to expansion.

# ScatterBot

![CI](https://github.com/AleksanderKGH/ScatterBot/actions/workflows/ci.yml/badge.svg)
![Dependency Review](https://github.com/AleksanderKGH/ScatterBot/actions/workflows/dependency-review.yml/badge.svg)

A Discord bot for collecting, managing, and visualizing village map data with scatter plots and town-layout tools.

## Status

- CI workflow: [ci.yml](https://github.com/AleksanderKGH/ScatterBot/actions/workflows/ci.yml)
- Dependency review workflow: [dependency-review.yml](https://github.com/AleksanderKGH/ScatterBot/actions/workflows/dependency-review.yml)
- Pull requests list: [Open PRs](https://github.com/AleksanderKGH/ScatterBot/pulls)

## Features

- Slash commands for point submission, plotting, and village summaries.
- Daily reset cycle with optional reset announcements and GOAT stat callouts.
- JSON-based persistence for points, XP, backups, and town layouts.
- Optional Supabase Postgres mirror for read-only backup dashboards.
- Town rendering and chunk-based town editing workflows.
- Role/channel guards for sensitive/admin operations.
- Autocomplete for villages, colors, and town names.

## Requirements

- Python 3.10+
- A Discord application and bot token

## Getting Started

### 1. Clone the repository

```bash
git clone https://github.com/AleksanderKGH/ScatterBot.git
cd ScatterBot
```

### 2. Create your environment file

Create a `.env` file in the project root:

```env
ENV=DEV
DISCORD_TOKEN=your_token_here
LOG_CHANNEL_ID=123456789012345678
POINT_CHANNEL_ID=123456789012345678
PLOT_CHANNEL_ID=123456789012345678
GUILD_ID=123456789012345678
RESIDENT_ROLE_ID=123456789012345678
PEARL_ROLE_ID=123456789012345678
VILLAGES=Dogville,An Bread Capital,Wheat Street,Kitsune Ville,Yeastopia,Rosemary Road,Samurai Village,Little Lamb Loaves,Croissant Creek,Honey Wheat Hollow
SUPABASE_DB_POOLER_URL=postgresql://postgres.<project-ref>:<password>@aws-0-<region>.pooler.supabase.com:5432/postgres
```

Notes:
- `VILLAGES` is optional. If omitted, built-in defaults are used.
- `SUPABASE_DB_POOLER_URL` is optional, but required for backup mirroring/import to Supabase.
- Never commit `.env`.

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Run the bot

```bash
python main.py
```

## Supabase Backup Setup (Read-Only Dashboard)

Use this if your website only reads backups from Postgres and never modifies bot state.

### 1. Apply backup schema migration

```bash
python -c "import os; from pathlib import Path; from dotenv import load_dotenv; import psycopg; load_dotenv(); dsn=os.getenv('SUPABASE_DB_POOLER_URL') or os.getenv('SUPABASE_DB_URL') or os.getenv('DATABASE_URL'); sql=Path('supabase/migrations/20260719_backup_snapshots.sql').read_text(encoding='utf-8');
with psycopg.connect(dsn) as conn:
	with conn.cursor() as cur:
		cur.execute(sql)
	conn.commit(); print('Migration applied.')"
```

### 2. (Recommended) Clean village keys in historical backups

This keeps only canonical villages and removes junk keys from malformed historical data.

```bash
python scripts/clean_backup_villages.py --backups-dir backups --dry-run
python scripts/clean_backup_villages.py --backups-dir backups
```

### 3. Import backups into Supabase

```bash
python scripts/import_backups_to_supabase.py --backups-dir backups --source discord-bot
```

### 4. Validate imported backups

```bash
python -c "import os; from pathlib import Path; from dotenv import load_dotenv; import psycopg; load_dotenv(); dsn=os.getenv('SUPABASE_DB_POOLER_URL') or os.getenv('SUPABASE_DB_URL') or os.getenv('DATABASE_URL'); sql=Path('supabase/queries/validate_backups.sql').read_text(encoding='utf-8');
with psycopg.connect(dsn) as conn:
	with conn.cursor() as cur:
		cur.execute(sql)
		while True:
			rows = cur.fetchall() if cur.description else []
			if cur.description:
				cols = [d.name for d in cur.description]
				print('--- result set ---')
				print(', '.join(cols))
				for r in rows:
					print(r)
			if not cur.nextset():
				break"
```

### 5. Ongoing backup behavior

- Local JSON backups remain the source-of-truth (`backups/YYYY-MM-DD.json`).
- If `SUPABASE_DB_POOLER_URL` is set, `backup_points()` mirrors each daily backup to Supabase.
- Non-canonical village keys are rejected during backup creation.

## Bot Commands

| Command | Description |
| --- | --- |
| `/point` | Add a point to a village map. |
| `/undo` | Remove your most recent point from a village. |
| `/plot` | Plot village points (with fake decoy point). |
| `/plotdetailed` | Plot village points without fake decoy point. |
| `/villages` | Show point totals by village. |
| `/townplot` | Render a town layout from `towns/<village>.json`. |
| `/townedit` | Open chunk-based town editing tools. |
| `/xp` | Show XP for yourself or another user. |
| `/leaderboard` | Show XP leaderboard. |
| `/incognito` | Opt in/out of appearing in the XP leaderboard. |
| `/residentjson` | Export users with configured roles as JSON. |
| `/residentcsv` | Export users with configured roles as CSV. |
| `/sync` | Sync slash commands to guild (admin only). |
| `/clearmaps` | Clear all village point data (admin only). |
| `/noob` | Show command help embed. |

## GitHub Actions

This repository now includes two workflows:

- `CI` ([.github/workflows/ci.yml](.github/workflows/ci.yml))
	- Runs on pushes to `main`/`master`, pull requests, and manual dispatch.
	- Tests Python 3.10, 3.11, and 3.12.
	- Installs dependencies.
	- Runs `ruff check .` with the starter config in `pyproject.toml`.
	- Validates syntax/importability with `python -m compileall .`.

- `Dependency Review` ([.github/workflows/dependency-review.yml](.github/workflows/dependency-review.yml))
	- Runs on pull requests.
	- Flags risky dependency changes using GitHub's dependency review action.

## Recommended Branch Protection

For your default branch (`main`), enable these GitHub settings:

1. Require a pull request before merging.
2. Require approvals (at least 1).
3. Require status checks to pass before merging:
	- `Python 3.10`
	- `Python 3.11`
	- `Python 3.12`
	- `dependency-review`
4. Require branches to be up to date before merging.
5. Dismiss stale approvals when new commits are pushed.
6. Restrict force pushes and deletions.

## Project Structure

```text
ScatterBot/
|-- main.py
|-- commands.py
|-- config.py
|-- data.py
|-- utils.py
|-- views.py
|-- xp.py
|-- command_modules/
|-- .github/workflows/
|-- requirements.txt
`-- readme.md
```

## Contributing

Issues and pull requests are welcome.

- Coding standards: [CODING_STANDARDS.md](CODING_STANDARDS.md)
- Pull request template: [.github/pull_request_template.md](.github/pull_request_template.md)
- Bug report template: [.github/ISSUE_TEMPLATE/bug_report.yml](.github/ISSUE_TEMPLATE/bug_report.yml)
- Feature request template: [.github/ISSUE_TEMPLATE/feature_request.yml](.github/ISSUE_TEMPLATE/feature_request.yml)

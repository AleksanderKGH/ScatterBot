#ledger.py
import json
import os
from xp import get_user_stat
FILE = "pearldebt.json"
# ─────────────────────────────────────────
# IO
# ─────────────────────────────────────────
def load_debt_data():
    if not os.path.exists(FILE):
        return {"optout": [], "optin": {}}
    with open(FILE, "r") as f:
        return json.load(f)
def save_debt_data(data):
    tmp = FILE + ".tmp"
    with open(tmp, "w") as f:
        json.dump(data, f, indent=2)
    os.replace(tmp, FILE)
# ─────────────────────────────────────────
# OPT RULES
# ─────────────────────────────────────────
def is_user_opted_out(user_id: int, data: dict) -> bool:
    return (
        str(user_id) in data.get("optout", [])
        or get_user_stat(user_id, "incognito") == 1
    )
# ─────────────────────────────────────────
# CORE LEDGER
# ─────────────────────────────────────────
def add_pearls_owed(user_id: int, amount: int = 1):
    data = load_debt_data()
    uid = str(user_id)

    if is_user_opted_out(user_id, data):
        return

    data["optin"][uid] = data["optin"].get(uid, 0) + amount
    save_debt_data(data)
def reduce_pearls_owed(user_id: int, amount: int):
    data = load_debt_data()
    uid = str(user_id)

    if uid not in data["optin"]:
        return

    data["optin"][uid] = max(0, data["optin"][uid] - amount)
    save_debt_data(data)
def get_all_pearls_owed():
    return load_debt_data()
# ─────────────────────────────────────────
# OPTIONAL HELPERS
# ─────────────────────────────────────────
def get_user_owed(user_id: int) -> int:
    data = load_debt_data()
    return data.get("optin", {}).get(str(user_id), 0)
def snapshot_pearldebt_before_reset():
    data = load_debt_data()
    save_debt_data(data)
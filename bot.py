# bot.py
import discord
from discord import app_commands
from discord.ext import commands
import json
import os
import math
from datetime import datetime
from flask import Flask
import threading
import os

# ---------------- CONFIG ----------------
PYTHON_VERSION = "3.11"
GUILD_ID = 1361851093004320908  # replace with your server ID
DATA_FILE = "leaderboard.json"
TOKEN = os.getenv("BOTTOKEN")

# Add your authorized Discord IDs here (for backend commands)
AUTHORIZED_USERS = [1035911200237699072, 1252375690242818121]  # replace with actual IDs

# ---------------- HELPER FUNCTIONS ----------------
def load_data():
    try:
        with open(DATA_FILE, "r") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}

def save_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=4)

def get_month_key(month: str = None):
    if month:
        return month
    return datetime.now().strftime("%Y-%m")  # current month e.g., "2026-02"

def is_authorized(user_id):
    return user_id in AUTHORIZED_USERS

# ---------------- BOT SETUP ----------------
intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)
guild = discord.Object(id=GUILD_ID)

# ---------------- COMMANDS ----------------
@bot.event
async def on_ready():
    print(f"Logged in as {bot.user} (ID: {bot.user.id})")
    try:
        synced = await bot.tree.sync(guild=guild)
        print(f"Synced {len(synced)} commands.")
    except Exception as e:
        print(f"Failed to sync commands: {e}")

@bot.tree.command(name="ping", description="Check bot latency and hype!", guild=guild)
async def ping(interaction: discord.Interaction):
    latency_ms = round(bot.latency * 1000)  # convert to milliseconds
    hype_messages = [
        "PNGGGG🗣️🗣️🔥🔥",
        "LET'S GO PNGGGG 🚀🗣️🔥",
        "PNGG MODE ACTIVATED 🏆💥🗣️",
        "KILLS TRACKED! PNGGGG 💯🔥🗣️"
    ]
    import random
    hype = random.choice(hype_messages)

    await interaction.response.send_message(f"🏓 Pong! {latency_ms}ms\n{hype}")
@bot.tree.command(name="help", description="Show bot commands and info", guild=guild)
async def help_command(interaction: discord.Interaction):
    help_text = (
        "📜 **PNG Leaderboard Bot Commands** 📜\n\n"
        "🔹 `/addkills player:<name> regular:<num> team:<num> month:<YYYY-MM>` — Add kills for a player (Authorized only)\n"
        "🔹 `/leaderboard month:<YYYY-MM>` — Show top players for a month (default = current month)\n"
        "🔹 `/player player:<name> month:<YYYY-MM>` — Show kills for a specific player\n"
        "🔹 `/resetmonth month:<YYYY-MM>` — Reset all kills for a month (Authorized only)\n"
        "🔹 `/ping` — Check bot latency and hype!\n"
        "🔹 `/help` — Show this help message\n\n"
        "⚠️ **Note:** Only authorized users can add or reset kills.\n"
        "Current month defaults to your server's time if not specified."
    )

    await interaction.response.send_message(help_text)

# Add kills (backend only)
@bot.tree.command(name="addkills", description="Add kills for a player (Authorized only)", guild=guild)
@app_commands.describe(player="Player ID or name", regular="Regular kills", team="Team kills", month="Month YYYY-MM")
async def addkills(interaction: discord.Interaction, player: str, regular: int = 0, team: int = 0, month: str = None):
    if not is_authorized(interaction.user.id):
        await interaction.response.send_message("❌ You are not authorized to add kills.", ephemeral=True)
        return

    data = load_data()
    month_key = get_month_key(month)

    if month_key not in data:
        data[month_key] = {}

    if player not in data[month_key]:
        data[month_key][player] = {"regular": 0, "team": 0}

    # Team kills: divide total team kills by 2 before adding
    total_team = math.ceil(team / 2)
    data[month_key][player]["regular"] += regular
    data[month_key][player]["team"] += total_team
    save_data(data)

    await interaction.response.send_message(
        f"✅ Added **{regular} regular** and **{total_team} team** kills for **{player}** in **{month_key}**."
    )

# Show leaderboard (anyone)
@bot.tree.command(name="leaderboard", description="Show leaderboard for a month", guild=guild)
@app_commands.describe(month="Month YYYY-MM")
async def leaderboard(interaction: discord.Interaction, month: str = None):
    data = load_data()
    month_key = get_month_key(month)

    if month_key not in data or not data[month_key]:
        await interaction.response.send_message(f"No data for {month_key}.")
        return

    leaderboard_list = []
    for player, stats in data[month_key].items():
        total = stats.get("regular", 0) + stats.get("team", 0)
        leaderboard_list.append((player, total))

    leaderboard_list.sort(key=lambda x: x[1], reverse=True)

    msg = f"🏆 **Leaderboard for {month_key}** 🏆\n"
    for i, (player, score) in enumerate(leaderboard_list[:10], start=1):
        msg += f"{i}. {player} — {score} kills\n"

    await interaction.response.send_message(msg)

# Show player stats (anyone)
@bot.tree.command(name="player", description="Show a player's kills for a month", guild=guild)
@app_commands.describe(player="Player ID or name", month="Month YYYY-MM")
async def player(interaction: discord.Interaction, player: str, month: str = None):
    data = load_data()
    month_key = get_month_key(month)

    if month_key not in data or player not in data[month_key]:
        await interaction.response.send_message(f"No data for {player} in {month_key}.")
        return

    stats = data[month_key][player]
    total = stats.get("regular", 0) + stats.get("team", 0)
    await interaction.response.send_message(
        f"📊 **{player} — {month_key}**\nRegular kills: {stats.get('regular',0)}\n"
        f"Team kills (divided by 2): {stats.get('team',0)}\n**Total: {total} kills**"
    )

# Reset a month (backend only)
@bot.tree.command(name="resetmonth", description="Reset all kills for a month (Authorized only)", guild=guild)
@app_commands.describe(month="Month YYYY-MM")
async def resetmonth(interaction: discord.Interaction, month: str = None):
    if not is_authorized(interaction.user.id):
        await interaction.response.send_message("❌ You are not authorized to reset months.", ephemeral=True)
        return

    data = load_data()
    month_key = get_month_key(month)

    if month_key in data:
        data[month_key] = {}
        save_data(data)
        await interaction.response.send_message(f"⚠️ Reset all data for {month_key}.")
    else:
        await interaction.response.send_message(f"No data found for {month_key}.")


app = Flask("")

@app.route("/")
def home():
    return "PNG Leaderboard Bot is alive!"

def run_flask():
    port = int(os.environ.get("PORT", 3000))  # Render sets PORT automatically
    app.run(host="0.0.0.0", port=port)

# Start Flask server in a separate thread so bot can run simultaneously
threading.Thread(target=run_flask).start()

# ---------------- RUN BOT ----------------
bot.run(TOKEN)


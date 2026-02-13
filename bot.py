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
import time
import random


ECON_FILE = "economy.json"
START_BALANCE = 500
MIN_BET = 10
MAX_BET = 1000
DAILY_REWARD = 200
DAILY_COOLDOWN = 86400  # 24 hours


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

# ================= PNG CASINO SYSTEM =================

def load_economy():
    try:
        with open(ECON_FILE, "r") as f:
            return json.load(f)
    except FileNotFoundError:
        return {"users": {}}

def save_economy(data):
    with open(ECON_FILE, "w") as f:
        json.dump(data, f, indent=4)

def get_account(user_id):
    data = load_economy()
    user_id = str(user_id)

    if user_id not in data["users"]:
        data["users"][user_id] = {
            "balance": START_BALANCE,
            "total_won": 0,
            "total_lost": 0,
            "last_daily": 0
        }
        save_economy(data)

    return data, data["users"][user_id]

# ---------------- BOT SETUP ----------------
intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)
guild = discord.Object(id=GUILD_ID)

# ================= BALANCE =================

@bot.tree.command(name="balance", description="Check your PNG balance", guild=guild)
async def balance(interaction: discord.Interaction):
    data, account = get_account(interaction.user.id)

    embed = discord.Embed(title="🪙 PNG Balance", color=discord.Color.gold())
    embed.add_field(name="User", value=interaction.user.mention)
    embed.add_field(name="Balance", value=f"{account['balance']} PNG")

    await interaction.response.send_message(embed=embed)

# ================= DAILY =================

@bot.tree.command(name="daily", description="Claim daily PNG coins", guild=guild)
async def daily(interaction: discord.Interaction):
    data, account = get_account(interaction.user.id)
    now = int(time.time())

    if now - account["last_daily"] < DAILY_COOLDOWN:
        remaining = DAILY_COOLDOWN - (now - account["last_daily"])
        hours = remaining // 3600
        await interaction.response.send_message(
            f"⏳ Come back in {hours}h.",
            ephemeral=True
        )
        return

    account["balance"] += DAILY_REWARD
    account["last_daily"] = now
    save_economy(data)

    await interaction.response.send_message(
        f"🎁 You received {DAILY_REWARD} PNG!"
    )

# ================= COINFLIP =================

@bot.tree.command(name="coinflip", description="Bet on heads or tails", guild=guild)
@app_commands.describe(bet="Amount to bet", choice="heads or tails")
async def coinflip(interaction: discord.Interaction, bet: int, choice: str):
    choice = choice.lower()

    if choice not in ["heads", "tails"]:
        await interaction.response.send_message("Choose heads or tails.", ephemeral=True)
        return

    if bet < MIN_BET or bet > MAX_BET:
        await interaction.response.send_message("Invalid bet amount.", ephemeral=True)
        return

    data, account = get_account(interaction.user.id)

    if account["balance"] < bet:
        await interaction.response.send_message("Not enough balance.", ephemeral=True)
        return

    result = random.choice(["heads", "tails"])

    embed = discord.Embed(title="🪙 Coinflip", color=discord.Color.blue())
    embed.add_field(name="Your Choice", value=choice)
    embed.add_field(name="Result", value=result)

    if choice == result:
        account["balance"] += bet
        account["total_won"] += bet
        embed.add_field(name="Outcome", value=f"You won {bet} PNG!")
    else:
        account["balance"] -= bet
        account["total_lost"] += bet
        embed.add_field(name="Outcome", value=f"You lost {bet} PNG.")

    save_economy(data)
    await interaction.response.send_message(embed=embed)

# ================= DICE (VS BOT) =================

@bot.tree.command(name="dice", description="Roll against the bot", guild=guild)
@app_commands.describe(bet="Amount to bet")
async def dice(interaction: discord.Interaction, bet: int):
    if bet < MIN_BET or bet > MAX_BET:
        await interaction.response.send_message("Invalid bet.", ephemeral=True)
        return

    data, account = get_account(interaction.user.id)

    if account["balance"] < bet:
        await interaction.response.send_message("Not enough balance.", ephemeral=True)
        return

    user_roll = random.randint(1, 6)
    bot_roll = random.randint(1, 6)

    embed = discord.Embed(title="🎲 Dice Game", color=discord.Color.purple())
    embed.add_field(name="You rolled", value=user_roll)
    embed.add_field(name="Bot rolled", value=bot_roll)

    if user_roll > bot_roll:
        account["balance"] += bet
        account["total_won"] += bet
        embed.add_field(name="Outcome", value=f"You won {bet} PNG!")
    elif user_roll < bot_roll:
        account["balance"] -= bet
        account["total_lost"] += bet
        embed.add_field(name="Outcome", value=f"You lost {bet} PNG.")
    else:
        embed.add_field(name="Outcome", value="Tie! No coins lost.")

    save_economy(data)
    await interaction.response.send_message(embed=embed)

# ================= DICE VS PLAYER =================

@bot.tree.command(name="dicevs", description="Challenge another user to a dice duel", guild=guild)
@app_commands.describe(
    opponent="User to challenge",
    bet="Amount each player bets"
)
async def dicevs(interaction: discord.Interaction, opponent: discord.Member, bet: int):

    if opponent.bot:
        await interaction.response.send_message("You cannot challenge a bot.", ephemeral=True)
        return

    if opponent.id == interaction.user.id:
        await interaction.response.send_message("You cannot challenge yourself.", ephemeral=True)
        return

    if bet < MIN_BET or bet > MAX_BET:
        await interaction.response.send_message("Invalid bet amount.", ephemeral=True)
        return

    data = load_economy()
    challenger_data, challenger_account = get_account(interaction.user.id)
    opponent_data, opponent_account = get_account(opponent.id)

    if challenger_account["balance"] < bet:
        await interaction.response.send_message("You don't have enough balance.", ephemeral=True)
        return

    if opponent_account["balance"] < bet:
        await interaction.response.send_message("Opponent doesn't have enough balance.", ephemeral=True)
        return

    # Roll dice
    challenger_roll = random.randint(1, 6)
    opponent_roll = random.randint(1, 6)

    embed = discord.Embed(title="🎲 Dice Duel", color=discord.Color.dark_gold())
    embed.add_field(name=interaction.user.display_name, value=f"Rolled: {challenger_roll}", inline=False)
    embed.add_field(name=opponent.display_name, value=f"Rolled: {opponent_roll}", inline=False)

    if challenger_roll > opponent_roll:
        challenger_account["balance"] += bet
        opponent_account["balance"] -= bet
        challenger_account["total_won"] += bet
        opponent_account["total_lost"] += bet
        embed.add_field(name="Winner", value=interaction.user.mention)
    elif opponent_roll > challenger_roll:
        opponent_account["balance"] += bet
        challenger_account["balance"] -= bet
        opponent_account["total_won"] += bet
        challenger_account["total_lost"] += bet
        embed.add_field(name="Winner", value=opponent.mention)
    else:
        embed.add_field(name="Result", value="Tie! No coins exchanged.")

    # SAVE BOTH ACCOUNTS PROPERLY
    data = load_economy()
    data["users"][str(interaction.user.id)] = challenger_account
    data["users"][str(opponent.id)] = opponent_account
    save_economy(data)

    await interaction.response.send_message(embed=embed)

# ================= SLOTS =================

@bot.tree.command(name="slots", description="Play PNG slots", guild=guild)
@app_commands.describe(bet="Amount to bet")
async def slots(interaction: discord.Interaction, bet: int):
    if bet < MIN_BET or bet > MAX_BET:
        await interaction.response.send_message("Invalid bet.", ephemeral=True)
        return

    data, account = get_account(interaction.user.id)

    if account["balance"] < bet:
        await interaction.response.send_message("Not enough balance.", ephemeral=True)
        return

    symbols = ["🍒", "🍋", "🔔", "💎", "7️⃣"]
    result = [random.choice(symbols) for _ in range(3)]

    embed = discord.Embed(title="🎰 PNG Slots", color=discord.Color.orange())
    embed.add_field(name="Result", value=" | ".join(result))

    if result.count(result[0]) == 3:
        winnings = bet * 5
        account["balance"] += winnings
        account["total_won"] += winnings
        embed.add_field(name="JACKPOT!", value=f"You won {winnings} PNG!")
    elif len(set(result)) == 2:
        winnings = bet * 2
        account["balance"] += winnings
        account["total_won"] += winnings
        embed.add_field(name="Nice!", value=f"You won {winnings} PNG!")
    else:
        account["balance"] -= bet
        account["total_lost"] += bet
        embed.add_field(name="Outcome", value=f"You lost {bet} PNG.")

    save_economy(data)
    await interaction.response.send_message(embed=embed)

# ================= ROULETTE =================

@bot.tree.command(name="roulette", description="Play roulette", guild=guild)
@app_commands.describe(bet="Amount to bet", choice="red, black, or number 0-36")
async def roulette(interaction: discord.Interaction, bet: int, choice: str):
    if bet < MIN_BET or bet > MAX_BET:
        await interaction.response.send_message("Invalid bet.", ephemeral=True)
        return

    data, account = get_account(interaction.user.id)

    if account["balance"] < bet:
        await interaction.response.send_message("Not enough balance.", ephemeral=True)
        return

    number = random.randint(0, 36)
    red_numbers = {1,3,5,7,9,12,14,16,18,19,21,23,25,27,30,32,34,36}
    color = "red" if number in red_numbers else "black"
    if number == 0:
        color = "green"

    embed = discord.Embed(title="🎡 PNG Roulette", color=discord.Color.red())
    embed.add_field(name="Number", value=number)
    embed.add_field(name="Color", value=color)

    win = False
    payout = 0

    if choice.lower() in ["red", "black"] and choice.lower() == color:
        win = True
        payout = bet
    elif choice.isdigit() and int(choice) == number:
        win = True
        payout = bet * 35

    if win:
        account["balance"] += payout
        account["total_won"] += payout
        embed.add_field(name="Outcome", value=f"You won {payout} PNG!")
    else:
        account["balance"] -= bet
        account["total_lost"] += bet
        embed.add_field(name="Outcome", value=f"You lost {bet} PNG.")

    save_economy(data)
    await interaction.response.send_message(embed=embed)

# ================= LEADERBOARD =================

@bot.tree.command(name="leaderboardcoins", description="Top richest players", guild=guild)
async def leaderboardcoins(interaction: discord.Interaction):
    data = load_economy()

    if not data["users"]:
        await interaction.response.send_message("No data yet.")
        return

    sorted_users = sorted(
        data["users"].items(),
        key=lambda x: x[1]["balance"],
        reverse=True
    )

    embed = discord.Embed(title="🏆 PNG Rich List", color=discord.Color.gold())

    for i, (user_id, info) in enumerate(sorted_users[:10], start=1):
        embed.add_field(
            name=f"{i}. <@{user_id}>",
            value=f"{info['balance']} PNG",
            inline=False
        )

    await interaction.response.send_message(embed=embed)

# ================= END CASINO SYSTEM =================

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


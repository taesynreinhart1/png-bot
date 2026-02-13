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
from discord.ui import View, Button, Modal, TextInput
from discord.ext import tasks


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

bot.event
async def on_ready():
    print(f"Logged in as {bot.user} (ID: {bot.user.id})")
    try:
        synced = await bot.tree.sync(guild=guild)
        print(f"Synced {len(synced)} commands.")
    except Exception as e:
        print(f"Failed to sync commands: {e}")

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

    # House edge: 52% chance for house result
    result = "heads" if random.random() < 0.48 else "tails"

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

    # House advantage: bot wins ties
    if user_roll == bot_roll:
        bot_roll = random.randint(1, 6)

    embed = discord.Embed(title="🎲 Dice Game", color=discord.Color.purple())
    embed.add_field(name="You rolled", value=user_roll)
    embed.add_field(name="Bot rolled", value=bot_roll)

    if user_roll > bot_roll:
        account["balance"] += bet
        account["total_won"] += bet
        embed.add_field(name="Outcome", value=f"You won {bet} PNG!")
    else:
        account["balance"] -= bet
        account["total_lost"] += bet
        embed.add_field(name="Outcome", value=f"You lost {bet} PNG.")

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

# --- Configuration ---
MIN_BET = 0
MAX_BET = 10000

RED_NUMBERS = {1,3,5,7,9,12,14,16,18,19,21,23,25,27,30,32,34,36}
ACTIVE_SESSIONS = {}  # {user_id: {"inactive_rounds": int, "last_bet": dict}}

BET_TYPES = {
    "single": 35,
    "split": 17,
    "street": 11,
    "corner": 8,
    "six_line": 5,
    "column": 2,
    "dozen": 2,
    "red_black": 1,
    "even_odd": 1,
    "low_high": 1
}

# --- Helpers ---
def check_color(number):
    if number in RED_NUMBERS:
        return "red"
    elif number in [0, "00"]:
        return "green"
    else:
        return "black"

# --- Multi-number button grid for complex bets ---
class MultiNumberButtonView(View):
    def __init__(self, parent_view, bet_type, required_count, bet_amount):
        super().__init__(timeout=60)
        self.parent_view = parent_view
        self.bet_type = bet_type
        self.required_count = required_count
        self.bet_amount = bet_amount
        self.selected_numbers = []

        for n in list(range(37)) + ["00"]:
            style = discord.ButtonStyle.danger if n in RED_NUMBERS else discord.ButtonStyle.secondary
            btn = Button(label=str(n), style=style)
            btn.callback = self.make_callback(str(n))
            self.add_item(btn)

    def make_callback(self, number):
        async def callback(interaction: discord.Interaction):
            if number in self.selected_numbers:
                self.selected_numbers.remove(number)
            else:
                self.selected_numbers.append(number)
            await interaction.response.send_message(
                f"Selected numbers: {', '.join(self.selected_numbers)}", ephemeral=True
            )
            if len(self.selected_numbers) == self.required_count:
                await self.parent_view.spin(
                    interaction, self.bet_type, self.selected_numbers, self.bet_amount
                )
                self.stop()
        return callback

# --- Main Roulette View ---
class RouletteView(View):
    def __init__(self, user_id):
        super().__init__(timeout=None)
        self.user_id = str(user_id)

    async def spin(self, interaction: discord.Interaction, bet_type=None, bet_choice=None, bet_amount=MIN_BET):
        data, account = get_account(interaction.user.id)

        if bet_type:  # Deduct balance
            if account["balance"] < bet_amount:
                await interaction.response.send_message("Not enough balance!", ephemeral=True)
                return
            account["balance"] -= bet_amount

        numbers = list(range(37)) + ["00"]
        result = random.choice(numbers)
        color = check_color(result)

        win = False
        payout = 0
        outcome_text = "No bet placed. Round ended."

        if bet_type:
            # Handle single number or multi-number bets
            if bet_type in ["single", "split", "street", "corner", "six_line"]:
                if str(result) in bet_choice:
                    win = True
                multiplier = BET_TYPES[bet_type]
            elif bet_type == "red_black" and bet_choice.lower() == color:
                win = True
                multiplier = 1
            elif bet_type == "even_odd" and result not in ["0","00"]:
                if bet_choice.lower() == "even" and int(result) % 2 == 0:
                    win = True
                elif bet_choice.lower() == "odd" and int(result) % 2 == 1:
                    win = True
                multiplier = 1
            elif bet_type == "low_high" and result not in ["0","00"]:
                if bet_choice.lower() == "low" and 1 <= int(result) <= 18:
                    win = True
                elif bet_choice.lower() == "high" and 19 <= int(result) <= 36:
                    win = True
                multiplier = 1
            elif bet_type == "dozen" and result not in ["0","00"]:
                dozens = {"1st": range(1,13), "2nd": range(13,25), "3rd": range(25,37)}
                if int(result) in dozens[bet_choice]:
                    win = True
                multiplier = 2
            elif bet_type == "column" and result not in ["0","00"]:
                columns = {
                    "1st": {1,4,7,10,13,16,19,22,25,28,31,34},
                    "2nd": {2,5,8,11,14,17,20,23,26,29,32,35},
                    "3rd": {3,6,9,12,15,18,21,24,27,30,33,36}
                }
                if int(result) in columns[bet_choice]:
                    win = True
                multiplier = 2

            if win:
                payout = bet_amount * multiplier
                account["balance"] += payout
                account["total_won"] += payout
                outcome_text = f"🎉 You won {payout} PNG!"
            else:
                account["total_lost"] += bet_amount
                outcome_text = f"💀 You lost {bet_amount} PNG."

        save_economy(data)

        embed = discord.Embed(title="🎡 PNG Roulette Spin", color=discord.Color.random())
        embed.add_field(name="Result", value=f"{result} ({color})")
        embed.add_field(name="Outcome", value=outcome_text)
        embed.set_footer(text="Bet again or leave the table.")
        await interaction.response.send_message(embed=embed, view=self)

    # --- Classic bet buttons ---
    @discord.ui.button(label="Red", style=discord.ButtonStyle.danger)
    async def red(self, interaction, button: Button):
        await self.spin(interaction, "red_black", "red")

    @discord.ui.button(label="Black", style=discord.ButtonStyle.secondary)
    async def black(self, interaction, button: Button):
        await self.spin(interaction, "red_black", "black")

    @discord.ui.button(label="Even", style=discord.ButtonStyle.primary)
    async def even(self, interaction, button: Button):
        await self.spin(interaction, "even_odd", "even")

    @discord.ui.button(label="Odd", style=discord.ButtonStyle.primary)
    async def odd(self, interaction, button: Button):
        await self.spin(interaction, "even_odd", "odd")

    @discord.ui.button(label="Low 1-18", style=discord.ButtonStyle.success)
    async def low(self, interaction, button: Button):
        await self.spin(interaction, "low_high", "low")

    @discord.ui.button(label="High 19-36", style=discord.ButtonStyle.success)
    async def high(self, interaction, button: Button):
        await self.spin(interaction, "low_high", "high")

    @discord.ui.button(label="1st Dozen", style=discord.ButtonStyle.secondary)
    async def first_dozen(self, interaction, button: Button):
        await self.spin(interaction, "dozen", "1st")

    @discord.ui.button(label="2nd Dozen", style=discord.ButtonStyle.secondary)
    async def second_dozen(self, interaction, button: Button):
        await self.spin(interaction, "dozen", "2nd")

    @discord.ui.button(label="3rd Dozen", style=discord.ButtonStyle.secondary)
    async def third_dozen(self, interaction, button: Button):
        await self.spin(interaction, "dozen", "3rd")

    @discord.ui.button(label="1st Column", style=discord.ButtonStyle.primary)
    async def col1(self, interaction, button: Button):
        await self.spin(interaction, "column", "1st")

    @discord.ui.button(label="2nd Column", style=discord.ButtonStyle.primary)
    async def col2(self, interaction, button: Button):
        await self.spin(interaction, "column", "2nd")

    @discord.ui.button(label="3rd Column", style=discord.ButtonStyle.primary)
    async def col3(self, interaction, button: Button):
        await self.spin(interaction, "column", "3rd")

    # Multi-number bets
    @discord.ui.button(label="Split", style=discord.ButtonStyle.secondary)
    async def split(self, interaction, button: Button):
        await interaction.response.send_message("Select 2 numbers for Split:", ephemeral=True,
                                                view=MultiNumberButtonView(self, "split", 2, MIN_BET))

    @discord.ui.button(label="Street", style=discord.ButtonStyle.secondary)
    async def street(self, interaction, button: Button):
        await interaction.response.send_message("Select 3 numbers for Street:", ephemeral=True,
                                                view=MultiNumberButtonView(self, "street", 3, MIN_BET))

    @discord.ui.button(label="Corner", style=discord.ButtonStyle.secondary)
    async def corner(self, interaction, button: Button):
        await interaction.response.send_message("Select 4 numbers for Corner:", ephemeral=True,
                                                view=MultiNumberButtonView(self, "corner", 4, MIN_BET))

    @discord.ui.button(label="Six-line", style=discord.ButtonStyle.secondary)
    async def six_line(self, interaction, button: Button):
        await interaction.response.send_message("Select 6 numbers for Six-line:", ephemeral=True,
                                                view=MultiNumberButtonView(self, "six_line", 6, MIN_BET))

    # Stay/Leave
    @discord.ui.button(label="Stay", style=discord.ButtonStyle.primary)
    async def stay(self, interaction, button: Button):
        ACTIVE_SESSIONS[self.user_id]["inactive_rounds"] = 0
        await interaction.response.send_message("👍 Staying at table. Next round auto-spins if no bet.", ephemeral=True)

    @discord.ui.button(label="Leave", style=discord.ButtonStyle.danger)
    async def leave(self, interaction, button: Button):
        ACTIVE_SESSIONS.pop(self.user_id, None)
        await interaction.response.send_message("👋 You left the roulette table.", ephemeral=True)

# --- Command ---
@bot.tree.command(name="roulette", description="Join the roulette table!", guild=guild)
async def roulette_cmd(interaction: discord.Interaction):
    user_id = str(interaction.user.id)
    if user_id not in ACTIVE_SESSIONS:
        ACTIVE_SESSIONS[user_id] = {"inactive_rounds": 0}
    embed = discord.Embed(title="🎡 PNG Roulette Table", color=discord.Color.green())
    embed.add_field(name="Instructions", value="Click buttons to bet! Stay/Leave to continue or exit.")
    await interaction.response.send_message(embed=embed, view=RouletteView(user_id))

# --- Auto-kick inactive players ---
@tasks.loop(minutes=1)
async def check_inactive_sessions():
    to_remove = []
    for user_id, sess in ACTIVE_SESSIONS.items():
        sess["inactive_rounds"] += 1
        if sess["inactive_rounds"] >= 3:
            to_remove.append(user_id)
    for user_id in to_remove:
        ACTIVE_SESSIONS.pop(user_id, None)
        try:
            user = await bot.fetch_user(int(user_id))
            await user.send("You were removed from the roulette table due to inactivity.")
        except:
            pass

check_inactive_sessions.start()

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
        "📜 **PNG Leaderboard & Casino Bot Commands** 📜\n\n"

        "🎯 **Leaderboard & Player Stats** 🎯\n"
        "🔹 `/addkills player:<name> regular:<num> team:<num> month:<YYYY-MM>` — Add kills for a player (Authorized only)\n"
        "🔹 `/leaderboard month:<YYYY-MM>` — Show top players for a month (default = current month)\n"
        "🔹 `/player player:<name> month:<YYYY-MM>` — Show kills for a specific player\n"
        "🔹 `/resetmonth month:<YYYY-MM>` — Reset all kills for a month (Authorized only)\n"
        "🔹 `/ping` — Check bot latency\n\n"

        "🎰 **Casino / PNG Economy Commands** 🎰\n"
        "🔹 `/dice <amount>` — Roll dice against the bot\n"
        "🔹 `/coinflip <amount>` — Flip a coin against the bot\n"
        "🔹 `/roulette` — Join the roulette table and place bets\n\n"

        "⚠️ **Notes:**\n"
        "- Only authorized users can add or reset kills.\n"
        "- Economy commands will use your PNG balance.\n"
        "- Current month defaults to your server's time if not specified."
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


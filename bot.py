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
import time
import random
from discord.ui import View, Button, Modal, TextInput
from discord.ext import tasks
import base64
import requests
import traceback

# ================= GITHUB STORAGE =================
class GitHubStorage:
    def __init__(self):
        self.token = os.getenv("GITHUBTOKEN")
        self.repo = "taesynreinhart1/png-bot"
        self.branch = "main"
        
        self.is_production = bool(os.environ.get('RENDER') or os.environ.get('RAILWAY') or os.environ.get('DYNO'))
        
        self.economy_cache = {"users": {}}
        self.leaderboard_cache = {}
        self.economy_sha = None
        self.leaderboard_sha = None
        self.pending_saves = False
        
        print(f"🔧 Storage Mode: {'GitHub (Production)' if self.is_production and self.token else 'Local (Development)'}")
        
        if self.is_production and self.token:
            self.load_all()
            self.ensure_files_exist()
    
    def load_from_github(self, path):
        """Load JSON directly from GitHub repo"""
        url = f"https://api.github.com/repos/{self.repo}/contents/{path}?ref={self.branch}"
        headers = {"Authorization": f"token {self.token}", "Accept": "application/vnd.github.v3+json"}
        
        try:
            response = requests.get(url, headers=headers)
            if response.status_code == 200:
                content = response.json()
                decoded = base64.b64decode(content['content']).decode('utf-8')
                return json.loads(decoded), content['sha']
            else:
                print(f"⚠️ GitHub file not found: {path}")
                return None, None
        except Exception as e:
            print(f"❌ Error loading from GitHub: {e}")
            return None, None
    
    def save_to_github(self, path, data, sha=None):
        """Save JSON directly to GitHub repo"""
        url = f"https://api.github.com/repos/{self.repo}/contents/{path}"
        headers = {"Authorization": f"token {self.token}", "Accept": "application/vnd.github.v3+json"}
        
        content = json.dumps(data, indent=4)
        encoded = base64.b64encode(content.encode('utf-8')).decode('utf-8')
        
        payload = {
            "message": f"Update {path} - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            "content": encoded,
            "branch": self.branch
        }
        if sha:
            payload["sha"] = sha
        
        try:
            response = requests.put(url, headers=headers, json=payload)
            if response.status_code in [200, 201]:
                print(f"✅ Saved to GitHub: {path}")
                return True
            else:
                print(f"❌ GitHub save failed: {response.status_code}")
                return False
        except Exception as e:
            print(f"❌ Error saving to GitHub: {e}")
            return False
    
    def ensure_files_exist(self):
        """Create economy.json and leaderboard.json on GitHub if they don't exist"""
        if not self.is_production or not self.token:
            return
        
        print("📝 Checking if GitHub files exist...")
        
        # Check/create economy.json
        econ_data, econ_sha = self.load_from_github("economy.json")
        if econ_data is None:
            print("📝 Creating economy.json on GitHub...")
            initial_econ = {"users": {}}
            success = self.save_to_github("economy.json", initial_econ, None)
            if success:
                print("✅ Created economy.json")
                _, self.economy_sha = self.load_from_github("economy.json")
                self.economy_cache = initial_econ
        else:
            print("✅ economy.json already exists")
            self.economy_cache = econ_data
            self.economy_sha = econ_sha
        
        # Check/create leaderboard.json
        lb_data, lb_sha = self.load_from_github("leaderboard.json")
        if lb_data is None:
            print("📝 Creating leaderboard.json on GitHub...")
            initial_lb = {}
            success = self.save_to_github("leaderboard.json", initial_lb, None)
            if success:
                print("✅ Created leaderboard.json")
                _, self.leaderboard_sha = self.load_from_github("leaderboard.json")
                self.leaderboard_cache = initial_lb
        else:
            print("✅ leaderboard.json already exists")
            self.leaderboard_cache = lb_data
            self.leaderboard_sha = lb_sha
    
    def load_all(self):
        """Load both economy and leaderboard data from GitHub"""
        if not self.is_production or not self.token:
            return
        
        econ_data, self.economy_sha = self.load_from_github("economy.json")
        if econ_data:
            self.economy_cache = econ_data
            print(f"💰 Loaded economy data: {len(econ_data.get('users', {}))} accounts")
        
        lb_data, self.leaderboard_sha = self.load_from_github("leaderboard.json")
        if lb_data:
            self.leaderboard_cache = lb_data
            print(f"📊 Loaded leaderboard data: {len(lb_data)} months")
    
    def get_economy(self):
        if self.is_production and self.token:
            return self.economy_cache
        else:
            try:
                with open(ECON_FILE, "r") as f:
                    return json.load(f)
            except FileNotFoundError:
                return {"users": {}}
    
    def save_economy(self, data):
        if self.is_production and self.token:
            self.economy_cache = data
            self.pending_saves = True
        else:
            os.makedirs(os.path.dirname(ECON_FILE), exist_ok=True)
            with open(ECON_FILE, "w") as f:
                json.dump(data, f, indent=4)
    
    def get_leaderboard(self):
        if self.is_production and self.token:
            return self.leaderboard_cache
        else:
            try:
                with open(DATA_FILE, "r") as f:
                    return json.load(f)
            except FileNotFoundError:
                return {}
    
    def save_leaderboard(self, data):
        if self.is_production and self.token:
            self.leaderboard_cache = data
            self.pending_saves = True
        else:
            os.makedirs(os.path.dirname(DATA_FILE), exist_ok=True)
            with open(DATA_FILE, "w") as f:
                json.dump(data, f, indent=4)
    
    @tasks.loop(seconds=30)
    async def auto_save(self):
        if not self.is_production or not self.token:
            return
        
        if self.pending_saves:
            print("💾 Auto-saving to GitHub...")
            
            if self.economy_cache:
                success = self.save_to_github("economy.json", self.economy_cache, self.economy_sha)
                if success:
                    _, self.economy_sha = self.load_from_github("economy.json")
            
            if self.leaderboard_cache:
                success = self.save_to_github("leaderboard.json", self.leaderboard_cache, self.leaderboard_sha)
                if success:
                    _, self.leaderboard_sha = self.load_from_github("leaderboard.json")
            
            self.pending_saves = False
            print("✅ Auto-save complete")

# ================= CONFIG =================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ECON_FILE = os.path.join(BASE_DIR, "economy.json")
DATA_FILE = os.path.join(BASE_DIR, "leaderboard.json")

START_BALANCE = 500
MIN_BET = 10
MAX_BET = 1000
DAILY_REWARD = 200
DAILY_COOLDOWN = 86400

GUILD_ID = 1361851093004320908
TOKEN = os.getenv("BOTTOKEN")
AUTHORIZED_USERS = [1035911200237699072, 1252375690242818121]

storage = GitHubStorage()

# ================= HELPER FUNCTIONS =================
def load_data():
    return storage.get_leaderboard()

def save_data(data):
    storage.save_leaderboard(data)

def get_month_key(month: str = None):
    return month if month else datetime.now().strftime("%Y-%m")

def is_authorized(user_id):
    return user_id in AUTHORIZED_USERS

def load_economy():
    return storage.get_economy()

def save_economy(data):
    storage.save_economy(data)

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
        print(f"🆕 Created account for {user_id}")

    return data, data["users"][user_id]

# ================= BOT SETUP =================
intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)
guild = discord.Object(id=GUILD_ID)

# ================= EVENTS =================
@bot.event
async def on_ready():
    print(f"✅ Logged in as {bot.user}")
    
    if storage.is_production and storage.token:
        storage.auto_save.start()
        print("🔄 Auto-save started (30s)")
    
    try:
        synced = await bot.tree.sync(guild=guild)
        print(f"🔄 Synced {len(synced)} commands")
    except Exception as e:
        print(f"❌ Sync failed: {e}")

# ================= BALANCE =================
@bot.tree.command(name="balance", description="Check your PNG balance", guild=guild)
async def balance(interaction: discord.Interaction):
    await interaction.response.defer()
    data, account = get_account(interaction.user.id)

    embed = discord.Embed(title="🪙 PNG Balance", color=discord.Color.gold())
    embed.add_field(name="User", value=interaction.user.mention)
    embed.add_field(name="Balance", value=f"{account['balance']} PNG")

    await interaction.followup.send(embed=embed)

# ================= DAILY =================
@bot.tree.command(name="daily", description="Claim daily PNG coins", guild=guild)
async def daily(interaction: discord.Interaction):
    await interaction.response.defer()
    data, account = get_account(interaction.user.id)
    now = int(time.time())

    if now - account["last_daily"] < DAILY_COOLDOWN:
        remaining = DAILY_COOLDOWN - (now - account["last_daily"])
        hours = remaining // 3600
        await interaction.followup.send(f"⏳ {interaction.user.mention} Come back in {hours}h.", ephemeral=True)
        return

    account["balance"] += DAILY_REWARD
    account["last_daily"] = now
    save_economy(data)

    await interaction.followup.send(f"🎁 {interaction.user.mention} received {DAILY_REWARD} PNG!")

# ================= COINFLIP =================
@bot.tree.command(name="coinflip", description="Bet on heads or tails", guild=guild)
@app_commands.describe(bet="Amount to bet", choice="heads or tails")
async def coinflip(interaction: discord.Interaction, bet: int, choice: str):
    await interaction.response.defer()
    choice = choice.lower()

    if choice not in ["heads", "tails"]:
        await interaction.followup.send("Choose heads or tails.", ephemeral=True)
        return

    if bet < MIN_BET or bet > MAX_BET:
        await interaction.followup.send("Invalid bet amount.", ephemeral=True)
        return

    data, account = get_account(interaction.user.id)

    if account["balance"] < bet:
        await interaction.followup.send("Not enough balance.", ephemeral=True)
        return

    result = "heads" if random.random() < 0.48 else "tails"

    embed = discord.Embed(title="🪙 Coinflip", color=discord.Color.blue())
    embed.add_field(name="Player", value=interaction.user.mention)
    embed.add_field(name="Choice", value=choice)
    embed.add_field(name="Result", value=result)

    if choice == result:
        account["balance"] += bet
        account["total_won"] += bet
        embed.add_field(name="Outcome", value=f"💰 Won {bet} PNG!")
    else:
        account["balance"] -= bet
        account["total_lost"] += bet
        embed.add_field(name="Outcome", value=f"💸 Lost {bet} PNG.")

    save_economy(data)
    await interaction.followup.send(embed=embed)

# ================= DICE =================
@bot.tree.command(name="dice", description="Roll against the bot", guild=guild)
@app_commands.describe(bet="Amount to bet")
async def dice(interaction: discord.Interaction, bet: int):
    await interaction.response.defer()
    if bet < MIN_BET or bet > MAX_BET:
        await interaction.followup.send("Invalid bet.", ephemeral=True)
        return

    data, account = get_account(interaction.user.id)

    if account["balance"] < bet:
        await interaction.followup.send("Not enough balance.", ephemeral=True)
        return

    user_roll = random.randint(1, 6)
    bot_roll = random.randint(1, 6)

    if user_roll == bot_roll:
        bot_roll = random.randint(1, 6)

    embed = discord.Embed(title="🎲 Dice", color=discord.Color.purple())
    embed.add_field(name="Player", value=interaction.user.mention)
    embed.add_field(name="Your Roll", value=user_roll)
    embed.add_field(name="Bot Roll", value=bot_roll)

    if user_roll > bot_roll:
        account["balance"] += bet
        account["total_won"] += bet
        embed.add_field(name="Outcome", value=f"💰 Won {bet} PNG!")
    else:
        account["balance"] -= bet
        account["total_lost"] += bet
        embed.add_field(name="Outcome", value=f"💸 Lost {bet} PNG.")

    save_economy(data)
    await interaction.followup.send(embed=embed)

# ================= DICE VS PLAYER =================
@bot.tree.command(name="dicevs", description="Challenge another user", guild=guild)
@app_commands.describe(opponent="User to challenge", bet="Amount each bets")
async def dicevs(interaction: discord.Interaction, opponent: discord.Member, bet: int):
    await interaction.response.defer()
    if opponent.bot:
        await interaction.followup.send("Can't challenge bots.", ephemeral=True)
        return

    if opponent.id == interaction.user.id:
        await interaction.followup.send("Can't challenge yourself.", ephemeral=True)
        return

    if bet < MIN_BET or bet > MAX_BET:
        await interaction.followup.send("Invalid bet.", ephemeral=True)
        return

    challenger_data, challenger_account = get_account(interaction.user.id)
    opponent_data, opponent_account = get_account(opponent.id)

    if challenger_account["balance"] < bet:
        await interaction.followup.send("You don't have enough.", ephemeral=True)
        return

    if opponent_account["balance"] < bet:
        await interaction.followup.send(f"{opponent.mention} doesn't have enough.", ephemeral=True)
        return

    challenger_roll = random.randint(1, 6)
    opponent_roll = random.randint(1, 6)

    embed = discord.Embed(title="🎲 Dice Duel", color=discord.Color.dark_gold())
    embed.add_field(name=interaction.user.display_name, value=f"Rolled: {challenger_roll}", inline=True)
    embed.add_field(name=opponent.display_name, value=f"Rolled: {opponent_roll}", inline=True)

    if challenger_roll > opponent_roll:
        challenger_account["balance"] += bet
        opponent_account["balance"] -= bet
        challenger_account["total_won"] += bet
        opponent_account["total_lost"] += bet
        embed.add_field(name="Winner", value=f"🏆 {interaction.user.mention}", inline=False)
    elif opponent_roll > challenger_roll:
        opponent_account["balance"] += bet
        challenger_account["balance"] -= bet
        opponent_account["total_won"] += bet
        challenger_account["total_lost"] += bet
        embed.add_field(name="Winner", value=f"🏆 {opponent.mention}", inline=False)
    else:
        embed.add_field(name="Result", value="🤝 Tie! No coins exchanged.", inline=False)

    data = load_economy()
    data["users"][str(interaction.user.id)] = challenger_account
    data["users"][str(opponent.id)] = opponent_account
    save_economy(data)

    await interaction.followup.send(embed=embed)

# ================= SLOTS =================
@bot.tree.command(name="slots", description="Play PNG slots", guild=guild)
@app_commands.describe(bet="Amount to bet")
async def slots(interaction: discord.Interaction, bet: int):
    await interaction.response.defer()
    if bet < MIN_BET or bet > MAX_BET:
        await interaction.followup.send("Invalid bet.", ephemeral=True)
        return

    data, account = get_account(interaction.user.id)

    if account["balance"] < bet:
        await interaction.followup.send("Not enough balance.", ephemeral=True)
        return

    symbols = ["🍒", "🍋", "🔔", "💎", "7️⃣"]
    result = [random.choice(symbols) for _ in range(3)]

    embed = discord.Embed(title="🎰 PNG Slots", color=discord.Color.orange())
    embed.add_field(name="Player", value=interaction.user.mention)
    embed.add_field(name="Result", value=" | ".join(result))

    if result.count(result[0]) == 3:
        winnings = bet * 5
        account["balance"] += winnings
        account["total_won"] += winnings
        embed.add_field(name="JACKPOT!", value=f"💰 Won {winnings} PNG!")
    elif len(set(result)) == 2:
        winnings = bet * 2
        account["balance"] += winnings
        account["total_won"] += winnings
        embed.add_field(name="Nice!", value=f"💰 Won {winnings} PNG!")
    else:
        account["balance"] -= bet
        account["total_lost"] += bet
        embed.add_field(name="Outcome", value=f"💸 Lost {bet} PNG.")

    save_economy(data)
    await interaction.followup.send(embed=embed)

# ================= ROULETTE =================
MIN_BET_ROULETTE = 10
MAX_BET_ROULETTE = 10000
RED_NUMBERS = {1,3,5,7,9,12,14,16,18,19,21,23,25,27,30,32,34,36}
ACTIVE_SESSIONS = {}

BET_TYPES = {
    "single": 35, "split": 17, "street": 11, "corner": 8, "six_line": 5,
    "column": 2, "dozen": 2, "red_black": 1, "even_odd": 1, "low_high": 1
}

def check_color(number):
    if number in RED_NUMBERS:
        return "red"
    elif number in [0, "00"]:
        return "green"
    else:
        return "black"

class BetAmountModal(Modal, title="Enter Bet Amount"):
    def __init__(self, parent_view, bet_type, bet_choice=None):
        super().__init__()
        self.parent_view = parent_view
        self.bet_type = bet_type
        self.bet_choice = bet_choice
        self.amount = TextInput(label="Amount (PNG)", placeholder=f"Min: {MIN_BET_ROULETTE}")
        self.add_item(self.amount)
    
    async def on_submit(self, interaction: discord.Interaction):
        try:
            bet_amount = int(self.amount.value)
            if bet_amount < MIN_BET_ROULETTE or bet_amount > MAX_BET_ROULETTE:
                await interaction.response.send_message("Invalid bet amount!", ephemeral=True)
                return
            await self.parent_view.spin(interaction, self.bet_type, self.bet_choice, bet_amount)
        except ValueError:
            await interaction.response.send_message("Enter a valid number!", ephemeral=True)

class MultiNumberButtonView(View):
    def __init__(self, parent_view, bet_type, required_count):
        super().__init__(timeout=60)
        self.parent_view = parent_view
        self.bet_type = bet_type
        self.required_count = required_count
        self.selected_numbers = []

        for row in range(0, 37, 6):
            for n in range(row, min(row + 6, 37)):
                style = discord.ButtonStyle.danger if n in RED_NUMBERS else discord.ButtonStyle.secondary
                btn = Button(label=str(n), style=style)
                btn.callback = self.make_callback(str(n))
                self.add_item(btn)
        
        btn_00 = Button(label="00", style=discord.ButtonStyle.secondary)
        btn_00.callback = self.make_callback("00")
        self.add_item(btn_00)
        
        confirm_btn = Button(label="✅ Confirm", style=discord.ButtonStyle.success)
        confirm_btn.callback = self.confirm_bet
        self.add_item(confirm_btn)

    def make_callback(self, number):
        async def callback(interaction: discord.Interaction):
            if number in self.selected_numbers:
                self.selected_numbers.remove(number)
            else:
                self.selected_numbers.append(number)
            await interaction.response.edit_message(
                content=f"Selected: {', '.join(self.selected_numbers)}\nNeed {self.required_count - len(self.selected_numbers)} more...",
                view=self
            )
        return callback
    
    async def confirm_bet(self, interaction: discord.Interaction):
        if len(self.selected_numbers) != self.required_count:
            await interaction.response.send_message(f"Select exactly {self.required_count} numbers!", ephemeral=True)
            return
        modal = BetAmountModal(self.parent_view, self.bet_type, self.selected_numbers)
        await interaction.response.send_modal(modal)

class RouletteView(View):
    def __init__(self, user_id):
        super().__init__(timeout=300)
        self.user_id = str(user_id)

    async def spin(self, interaction: discord.Interaction, bet_type=None, bet_choice=None, bet_amount=None):
        await interaction.response.defer()
        data, account = get_account(interaction.user.id)

        if bet_type and bet_amount:
            if account["balance"] < bet_amount:
                await interaction.followup.send("Not enough balance!", ephemeral=True)
                return
            account["balance"] -= bet_amount
            save_economy(data)

        numbers = list(range(37)) + ["00"]
        result = random.choice(numbers)
        color = check_color(result)

        win = False
        payout = 0
        outcome_text = "No bet placed."

        if bet_type and bet_amount:
            if bet_type in ["single", "split", "street", "corner", "six_line"]:
                if str(result) in bet_choice:
                    win = True
                multiplier = BET_TYPES[bet_type]
            elif bet_type == "red_black" and bet_choice.lower() == color:
                win = True
                multiplier = 1
            elif bet_type == "even_odd" and result not in ["0","00"]:
                if (bet_choice.lower() == "even" and int(result) % 2 == 0) or (bet_choice.lower() == "odd" and int(result) % 2 == 1):
                    win = True
                multiplier = 1
            elif bet_type == "low_high" and result not in ["0","00"]:
                if (bet_choice.lower() == "low" and 1 <= int(result) <= 18) or (bet_choice.lower() == "high" and 19 <= int(result) <= 36):
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
                outcome_text = f"🎉 Won {payout} PNG!"
                save_economy(data)
            else:
                account["total_lost"] += bet_amount
                outcome_text = f"💀 Lost {bet_amount} PNG."
                save_economy(data)

        if self.user_id in ACTIVE_SESSIONS:
            ACTIVE_SESSIONS[self.user_id]["inactive_rounds"] = 0

        embed = discord.Embed(title="🎡 Roulette", color=discord.Color.random())
        embed.add_field(name="Player", value=interaction.user.mention)
        embed.add_field(name="Result", value=f"{result} ({color})")
        embed.add_field(name="Outcome", value=outcome_text)
        embed.set_footer(text=f"Balance: {account['balance']} PNG")
        
        await interaction.followup.send(embed=embed, view=self)

    @discord.ui.button(label="Red", style=discord.ButtonStyle.danger, row=0)
    async def red(self, interaction, button: Button):
        modal = BetAmountModal(self, "red_black", "red")
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="Black", style=discord.ButtonStyle.secondary, row=0)
    async def black(self, interaction, button: Button):
        modal = BetAmountModal(self, "red_black", "black")
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="Even", style=discord.ButtonStyle.primary, row=0)
    async def even(self, interaction, button: Button):
        modal = BetAmountModal(self, "even_odd", "even")
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="Odd", style=discord.ButtonStyle.primary, row=0)
    async def odd(self, interaction, button: Button):
        modal = BetAmountModal(self, "even_odd", "odd")
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="Low 1-18", style=discord.ButtonStyle.success, row=1)
    async def low(self, interaction, button: Button):
        modal = BetAmountModal(self, "low_high", "low")
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="High 19-36", style=discord.ButtonStyle.success, row=1)
    async def high(self, interaction, button: Button):
        modal = BetAmountModal(self, "low_high", "high")
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="1st Dozen", style=discord.ButtonStyle.secondary, row=1)
    async def first_dozen(self, interaction, button: Button):
        modal = BetAmountModal(self, "dozen", "1st")
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="2nd Dozen", style=discord.ButtonStyle.secondary, row=1)
    async def second_dozen(self, interaction, button: Button):
        modal = BetAmountModal(self, "dozen", "2nd")
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="3rd Dozen", style=discord.ButtonStyle.secondary, row=2)
    async def third_dozen(self, interaction, button: Button):
        modal = BetAmountModal(self, "dozen", "3rd")
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="1st Column", style=discord.ButtonStyle.primary, row=2)
    async def col1(self, interaction, button: Button):
        modal = BetAmountModal(self, "column", "1st")
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="2nd Column", style=discord.ButtonStyle.primary, row=2)
    async def col2(self, interaction, button: Button):
        modal = BetAmountModal(self, "column", "2nd")
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="3rd Column", style=discord.ButtonStyle.primary, row=2)
    async def col3(self, interaction, button: Button):
        modal = BetAmountModal(self, "column", "3rd")
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="Single", style=discord.ButtonStyle.danger, row=3)
    async def single(self, interaction, button: Button):
        await interaction.response.send_message("Select 1 number:", ephemeral=True, view=MultiNumberButtonView(self, "single", 1))

    @discord.ui.button(label="Split", style=discord.ButtonStyle.secondary, row=3)
    async def split(self, interaction, button: Button):
        await interaction.response.send_message("Select 2 numbers:", ephemeral=True, view=MultiNumberButtonView(self, "split", 2))

    @discord.ui.button(label="Street", style=discord.ButtonStyle.secondary, row=3)
    async def street(self, interaction, button: Button):
        await interaction.response.send_message("Select 3 numbers:", ephemeral=True, view=MultiNumberButtonView(self, "street", 3))

    @discord.ui.button(label="Corner", style=discord.ButtonStyle.secondary, row=4)
    async def corner(self, interaction, button: Button):
        await interaction.response.send_message("Select 4 numbers:", ephemeral=True, view=MultiNumberButtonView(self, "corner", 4))

    @discord.ui.button(label="Six-line", style=discord.ButtonStyle.secondary, row=4)
    async def six_line(self, interaction, button: Button):
        await interaction.response.send_message("Select 6 numbers:", ephemeral=True, view=MultiNumberButtonView(self, "six_line", 6))

    @discord.ui.button(label="Stay", style=discord.ButtonStyle.primary, row=4)
    async def stay(self, interaction, button: Button):
        if self.user_id in ACTIVE_SESSIONS:
            ACTIVE_SESSIONS[self.user_id]["inactive_rounds"] = 0
        await interaction.response.send_message("👍 Staying at table.", ephemeral=True)

    @discord.ui.button(label="Leave", style=discord.ButtonStyle.danger, row=4)
    async def leave(self, interaction, button: Button):
        ACTIVE_SESSIONS.pop(self.user_id, None)
        await interaction.response.send_message("👋 Left table.", ephemeral=True)
        self.stop()

@bot.tree.command(name="roulette", description="Join the roulette table!", guild=guild)
async def roulette_cmd(interaction: discord.Interaction):
    await interaction.response.defer()
    user_id = str(interaction.user.id)
    if user_id not in ACTIVE_SESSIONS:
        ACTIVE_SESSIONS[user_id] = {"inactive_rounds": 0}
    
    data, account = get_account(interaction.user.id)
    embed = discord.Embed(title="🎡 PNG Roulette", color=discord.Color.green())
    embed.add_field(name="Player", value=interaction.user.mention)
    embed.add_field(name="Balance", value=f"{account['balance']} PNG")
    embed.add_field(name="Payouts", value="Single: 35x\nSplit: 17x\nStreet: 11x\nCorner: 8x\nSix-line: 5x\nColumn/Dozen: 2x\nOthers: 1x", inline=False)
    
    await interaction.followup.send(embed=embed, view=RouletteView(user_id))

@tasks.loop(minutes=1)
async def check_inactive_sessions():
    to_remove = []
    for user_id, sess in ACTIVE_SESSIONS.items():
        sess["inactive_rounds"] += 1
        if sess["inactive_rounds"] >= 3:
            to_remove.append(user_id)
    for user_id in to_remove:
        ACTIVE_SESSIONS.pop(user_id, None)

# ================= LEADERBOARD COINS =================
@bot.tree.command(name="leaderboardcoins", description="Top richest players", guild=guild)
async def leaderboardcoins(interaction: discord.Interaction):
    await interaction.response.defer()
    data = load_economy()

    if not data["users"]:
        await interaction.followup.send("No data yet.")
        return

    sorted_users = sorted(data["users"].items(), key=lambda x: x[1]["balance"], reverse=True)

    embed = discord.Embed(title="🏆 PNG Rich List", color=discord.Color.gold())
    for i, (user_id, info) in enumerate(sorted_users[:10], start=1):
        embed.add_field(name=f"{i}. <@{user_id}>", value=f"{info['balance']} PNG", inline=False)

    await interaction.followup.send(embed=embed)

# ================= KILLS COMMANDS =================
@bot.tree.command(name="ping", description="Check bot latency and hype!", guild=guild)
async def ping(interaction: discord.Interaction):
    await interaction.response.defer()
    latency_ms = round(bot.latency * 1000)
    hype = random.choice(["PNGGGG🗣️🗣️🔥🔥", "LET'S GO PNGGGG 🚀🗣️🔥", "PNGG MODE ACTIVATED 🏆💥🗣️", "KILLS TRACKED! PNGGGG 💯🔥🗣️"])
    await interaction.followup.send(f"🏓 Pong! {latency_ms}ms\n{hype}")
    
@bot.tree.command(name="help", description="Show bot commands and info", guild=guild)
async def help_command(interaction: discord.Interaction):
    await interaction.response.defer()
    help_text = (
        "📜 **PNG Bot Commands** 📜\n\n"
        "🎯 **Kills Leaderboard** 🎯\n"
        "🔹 `/addkills player:<name> regular:<num> team:<num> month:<YYYY-MM>` — Add kills (Auth only)\n"
        "🔹 `/leaderboard month:<YYYY-MM>` — Show top players\n"
        "🔹 `/player player:<name> month:<YYYY-MM>` — Show player stats\n"
        "🔹 `/resetmonth month:<YYYY-MM>` — Reset month (Auth only)\n"
        "🔹 `/leaderboardcoins` — Top richest players\n"
        "🔹 `/ping` — Bot latency\n\n"
        "🎰 **Casino** 🎰\n"
        "🔹 `/balance` — Check PNG balance\n"
        "🔹 `/daily` — Claim 200 PNG\n"
        "🔹 `/coinflip bet:<amount> choice:<heads/tails>`\n"
        "🔹 `/dice bet:<amount>` — Roll vs bot\n"
        "🔹 `/dicevs opponent:<user> bet:<amount>` — Duel\n"
        "🔹 `/slots bet:<amount>` — Play slots\n"
        "🔹 `/roulette` — Join roulette table\n\n"
        "⚠️ **All commands are public unless it's an error!**"
    )
    await interaction.followup.send(help_text)

@bot.tree.command(name="addkills", description="Add kills for a player (Authorized only)", guild=guild)
@app_commands.describe(player="Player ID or name", regular="Regular kills", team="Team kills", month="Month YYYY-MM")
async def addkills(interaction: discord.Interaction, player: str, regular: int = 0, team: int = 0, month: str = None):
    if not is_authorized(interaction.user.id):
        await interaction.response.send_message("❌ Not authorized.", ephemeral=True)
        return

    await interaction.response.defer()
    
    data = load_data()
    month_key = get_month_key(month)

    if month_key not in data:
        data[month_key] = {}
    if player not in data[month_key]:
        data[month_key][player] = {"regular": 0, "team": 0}

    total_team = math.ceil(team / 2)
    data[month_key][player]["regular"] += regular
    data[month_key][player]["team"] += total_team
    save_data(data)

    await interaction.followup.send(
        f"✅ {interaction.user.mention} added **{regular} regular** + **{total_team} team** kills for **{player}** in **{month_key}**."
    )

@bot.tree.command(name="leaderboard", description="Show leaderboard for a month", guild=guild)
@app_commands.describe(month="Month YYYY-MM")
async def leaderboard(interaction: discord.Interaction, month: str = None):
    await interaction.response.defer()
    data = load_data()
    month_key = get_month_key(month)

    if month_key not in data or not data[month_key]:
        await interaction.followup.send(f"No data for {month_key}.")
        return

    leaderboard_list = []
    for player, stats in data[month_key].items():
        total = stats.get("regular", 0) + stats.get("team", 0)
        leaderboard_list.append((player, total))

    leaderboard_list.sort(key=lambda x: x[1], reverse=True)

    msg = f"🏆 **Leaderboard for {month_key}** 🏆\n"
    for i, (player, score) in enumerate(leaderboard_list[:10], start=1):
        msg += f"{i}. {player} — {score} kills\n"

    await interaction.followup.send(msg)

@bot.tree.command(name="player", description="Show a player's kills for a month", guild=guild)
@app_commands.describe(player="Player ID or name", month="Month YYYY-MM")
async def player(interaction: discord.Interaction, player: str, month: str = None):
    await interaction.response.defer()
    data = load_data()
    month_key = get_month_key(month)

    if month_key not in data or player not in data[month_key]:
        await interaction.followup.send(f"No data for {player} in {month_key}.")
        return

    stats = data[month_key][player]
    total = stats.get("regular", 0) + stats.get("team", 0)
    await interaction.followup.send(
        f"📊 **{player} — {month_key}**\n"
        f"Regular kills: {stats.get('regular',0)}\n"
        f"Team kills (halved): {stats.get('team',0)}\n"
        f"**Total: {total} kills**"
    )

@bot.tree.command(name="resetmonth", description="Reset all kills for a month (Authorized only)", guild=guild)
@app_commands.describe(month="Month YYYY-MM")
async def resetmonth(interaction: discord.Interaction, month: str = None):
    if not is_authorized(interaction.user.id):
        await interaction.response.send_message("❌ Not authorized.", ephemeral=True)
        return

    await interaction.response.defer()
    data = load_data()
    month_key = get_month_key(month)

    if month_key in data:
        data[month_key] = {}
        save_data(data)
        await interaction.followup.send(f"⚠️ {interaction.user.mention} reset all data for **{month_key}**.")
    else:
        await interaction.followup.send(f"No data found for {month_key}.")

@bot.tree.command(name="storage", description="Check GitHub storage status (Authorized only)", guild=guild)
async def storage_status(interaction: discord.Interaction):
    if not is_authorized(interaction.user.id):
        await interaction.response.send_message("❌ Not authorized.", ephemeral=True)
        return
    
    await interaction.response.defer()
    
    status = f"**Storage Mode:** {'GitHub' if storage.is_production and storage.token else 'Local'}\n"
    if storage.is_production and storage.token:
        status += f"**Repo:** {storage.repo}\n"
        status += f"**Auto-save:** {'Running' if storage.auto_save.is_running() else 'Stopped'}\n"
        status += f"**Pending Saves:** {storage.pending_saves}\n"
        
        econ = storage.get_economy()
        lb = storage.get_leaderboard()
        status += f"**Economy Accounts:** {len(econ.get('users', {}))}\n"
        status += f"**Leaderboard Months:** {len(lb)}\n"
    
    await interaction.followup.send(status)

# ================= FLASK KEEP-ALIVE =================
app = Flask("")

@app.route("/")
def home():
    return f"PNG Bot is alive! Mode: {'GitHub' if storage.is_production and storage.token else 'Local'}"

def run_flask():
    port = int(os.environ.get("PORT", 3000))
    app.run(host="0.0.0.0", port=port)

threading.Thread(target=run_flask, daemon=True).start()

# ================= RUN BOT =================
if __name__ == "__main__":
    print("="*50)
    print("🚀 PNG BOT STARTING UP")
    print(f"📁 Base: {BASE_DIR}")
    print(f"🔧 Mode: {'GitHub' if storage.is_production and storage.token else 'Local'}")
    if storage.is_production and storage.token:
        print(f"📦 Repo: {storage.repo}")
        print(f"🔑 Token: {'✅' if storage.token else '❌'}")
    print("="*50)
    
    bot.run(TOKEN)

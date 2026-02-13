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
import asyncio
import math

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

@bot.event
async def on_ready():
    print(f"✅ Logged in as {bot.user}")
    
    if storage.is_production and storage.token:
        storage.auto_save.start()
        print("🔄 Auto-save started (30s)")
    
    # Add this line:
    cleanup_blackjack_games.start()
    print("🃏 Blackjack cleanup started (5min)")
    
    try:
        synced = await bot.tree.sync(guild=guild)
        print(f"🔄 Synced {len(synced)} commands")
    except Exception as e:
        print(f"❌ Sync failed: {e}")

# ================= BLACKJACK =================
BLACKJACK_MIN_BET = 10
BLACKJACK_MAX_BET = 1000

# Card values
CARD_VALUES = {
    '2': 2, '3': 3, '4': 4, '5': 5, '6': 6, '7': 7, '8': 8, '9': 9, 
    '10': 10, 'J': 10, 'Q': 10, 'K': 10, 'A': 11
}

# Card suits
SUITS = ['♠️', '♥️', '♦️', '♣️']

# Store active games
ACTIVE_BLACKJACK_GAMES = {}

class BlackjackGame:
    def __init__(self, player_id, bet_amount):
        self.player_id = str(player_id)
        self.bet_amount = bet_amount
        self.deck = self.create_deck()
        random.shuffle(self.deck)
        self.player_hand = []
        self.dealer_hand = []
        self.player_score = 0
        self.dealer_score = 0
        self.game_over = False
        self.result = None
        self.payout = 0
        self.message = None
        self.blackjack = False
        
    def create_deck(self):
        """Create a standard 52-card deck"""
        deck = []
        for suit in SUITS:
            for card in ['2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K', 'A']:
                deck.append(f"{card}{suit}")
        return deck
    
    def get_card_value(self, card):
        """Extract card value correctly (handles 10 properly)"""
        if card.startswith('10'):
            return '10'
        else:
            return card[0]  # First character: 'J', 'Q', 'K', 'A', '2'-'9'
    
    def calculate_score(self, hand):
        """Calculate hand score with proper Ace handling"""
        score = 0
        aces = 0
        
        for card in hand:
            value = self.get_card_value(card)
            if value == 'A':
                aces += 1
                score += 11
            else:
                score += CARD_VALUES[value]
        
        # Adjust aces from 11 to 1 if needed
        while score > 21 and aces > 0:
            score -= 10
            aces -= 1
            
        return score
    
    def deal_card(self, hand):
        """Deal a card to a hand"""
        card = self.deck.pop()
        hand.append(card)
        return card
    
    def start_game(self):
        """Start a new blackjack game"""
        # Deal initial cards
        self.deal_card(self.player_hand)
        self.deal_card(self.dealer_hand)
        self.deal_card(self.player_hand)
        self.deal_card(self.dealer_hand)
        
        # Calculate scores
        self.player_score = self.calculate_score(self.player_hand)
        self.dealer_score = self.calculate_score([self.dealer_hand[0]])
        
        # Check for player blackjack
        if self.player_score == 21:
            self.blackjack = True
            self.stand()  # Auto-stand on blackjack
    
    def hit(self):
        """Player hits - take another card"""
        if self.game_over:
            return False
        
        self.deal_card(self.player_hand)
        self.player_score = self.calculate_score(self.player_hand)
        
        if self.player_score > 21:
            self.game_over = True
            self.result = "bust"
            self.payout = 0
        elif self.player_score == 21:
            self.stand()
            
        return True
    
    def stand(self):
        """Player stands - dealer plays"""
        if self.game_over:
            return
        
        # Reveal dealer's full hand
        self.dealer_score = self.calculate_score(self.dealer_hand)
        
        # Dealer draws to 17 or higher
        while self.dealer_score < 17:
            self.deal_card(self.dealer_hand)
            self.dealer_score = self.calculate_score(self.dealer_hand)
        
        self.game_over = True
        
        # Determine winner
        if self.dealer_score > 21:
            self.result = "dealer_bust"
            if self.blackjack:
                self.payout = int(self.bet_amount * 2.5)  # Blackjack pays 3:2
            else:
                self.payout = self.bet_amount * 2
        elif self.dealer_score > self.player_score:
            self.result = "loss"
            self.payout = 0
        elif self.dealer_score < self.player_score:
            self.result = "win"
            if self.blackjack:
                self.payout = int(self.bet_amount * 2.5)
            else:
                self.payout = self.bet_amount * 2
        else:
            self.result = "push"
            self.payout = self.bet_amount
    
    def format_hand(self, hand, hide_first=False):
        """Format hand for display"""
        if hide_first and len(hand) > 0:
            return "?? " + " ".join(hand[1:])
        return " ".join(hand)
    
    def get_score_display(self, score, is_bust=False):
        """Get score with emoji"""
        if is_bust or score > 21:
            return f"💥 **{score}**"
        elif score == 21:
            return f"🎯 **{score}**"
        return f"**{score}**"
    
    def create_embed(self, interaction, account):
        """Create the game embed"""
        if self.game_over:
            if self.payout > self.bet_amount:
                title = "🎰 **BLACKJACK - YOU WIN!** 🎰"
                color = discord.Color.gold()
            elif self.payout == self.bet_amount:
                title = "🎰 **BLACKJACK - PUSH** 🎰"
                color = discord.Color.blue()
            else:
                title = "🎰 **BLACKJACK - YOU LOST** 🎰"
                color = discord.Color.red()
        else:
            title = "🎰 **BLACKJACK - IN PROGRESS** 🎰"
            color = discord.Color.green()
        
        embed = discord.Embed(title=title, color=color)
        
        # Player info
        embed.add_field(name="👤 Player", value=interaction.user.mention, inline=True)
        embed.add_field(name="💰 Bet", value=f"{self.bet_amount} PNG", inline=True)
        embed.add_field(name="💎 Balance", value=f"{account['balance']} PNG", inline=True)
        
        # Player hand
        player_display = self.format_hand(self.player_hand)
        player_score_text = self.get_score_display(self.player_score, self.player_score > 21)
        if self.blackjack and not self.game_over:
            hand_title = f"🃏 **YOUR HAND** {player_score_text} 🎉 **BLACKJACK!**"
        else:
            hand_title = f"🃏 **YOUR HAND** {player_score_text}"
        embed.add_field(name=hand_title, value=f"```\n{player_display}\n```", inline=False)
        
        # Dealer hand
        hide = not self.game_over
        dealer_display = self.format_hand(self.dealer_hand, hide_first=hide)
        if hide:
            visible_score = self.calculate_score([self.dealer_hand[0]])
            dealer_score_text = f"**{visible_score}** + ?"
        else:
            dealer_score_text = self.get_score_display(self.dealer_score, self.dealer_score > 21)
        embed.add_field(name=f"🤵 **DEALER** {dealer_score_text}", value=f"```\n{dealer_display}\n```", inline=False)
        
        # Result if game over
        if self.game_over:
            if self.result == "bust":
                result_text = f"💥 **BUST!** Lost {self.bet_amount} PNG"
            elif self.result == "dealer_bust":
                profit = self.payout - self.bet_amount
                result_text = f"🎉 **DEALER BUST!** +{profit} PNG!"
            elif self.result == "win":
                profit = self.payout - self.bet_amount
                result_text = f"🎉 **YOU WIN!** +{profit} PNG!"
            elif self.result == "loss":
                result_text = f"💀 **DEALER WINS!** Lost {self.bet_amount} PNG"
            elif self.result == "push":
                result_text = f"🤝 **PUSH!** Bet returned: {self.bet_amount} PNG"
            embed.add_field(name="📊 **RESULT**", value=result_text, inline=False)
        
        return embed

class BlackjackBetModal(Modal, title="💰 Place Your Blackjack Bet"):
    def __init__(self):
        super().__init__()
        self.bet = TextInput(
            label="Bet Amount (PNG)",
            placeholder=f"Min: {BLACKJACK_MIN_BET} • Max: {BLACKJACK_MAX_BET}",
            required=True
        )
        self.add_item(self.bet)
    
    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer()
        
        try:
            bet_amount = int(self.bet.value)
            if bet_amount < BLACKJACK_MIN_BET or bet_amount > BLACKJACK_MAX_BET:
                await interaction.followup.send(
                    f"❌ Bet must be between {BLACKJACK_MIN_BET} and {BLACKJACK_MAX_BET} PNG!",
                    ephemeral=True
                )
                return
            
            # Check balance
            data, account = get_account(interaction.user.id)
            if account["balance"] < bet_amount:
                await interaction.followup.send(
                    f"❌ You only have {account['balance']} PNG!",
                    ephemeral=True
                )
                return
            
            # Deduct bet
            account["balance"] -= bet_amount
            save_economy(data)
            
            # Create and start game
            game = BlackjackGame(interaction.user.id, bet_amount)
            game.start_game()
            
            # Store game
            ACTIVE_BLACKJACK_GAMES[str(interaction.user.id)] = game
            
            # Create embed and view
            embed = game.create_embed(interaction, account)
            view = BlackjackView(game)
            
            # Send message
            await interaction.followup.send(embed=embed, view=view)
            game.message = await interaction.original_response()
            
        except ValueError:
            await interaction.followup.send("❌ Enter a valid number!", ephemeral=True)

class BlackjackView(View):
    def __init__(self, game):
        super().__init__(timeout=120)
        self.game = game
    
    async def update_game(self, interaction, account):
        """Update the game message"""
        embed = self.game.create_embed(interaction, account)
        
        if self.game.game_over:
            await interaction.response.edit_message(embed=embed, view=None)
            ACTIVE_BLACKJACK_GAMES.pop(self.game.player_id, None)
            
            # Add winnings
            if self.game.payout > 0:
                data, account = get_account(int(self.game.player_id))
                account["balance"] += self.game.payout
                save_economy(data)
        else:
            await interaction.response.edit_message(embed=embed, view=self)
    
    @discord.ui.button(label="🎯 HIT", style=discord.ButtonStyle.primary, emoji="🃏", row=0)
    async def hit_button(self, interaction: discord.Interaction, button: Button):
        if str(interaction.user.id) != self.game.player_id:
            await interaction.response.send_message("❌ This isn't your game!", ephemeral=True)
            return
        
        await interaction.response.defer()
        
        if self.game.game_over:
            await interaction.followup.send("❌ Game is already over!", ephemeral=True)
            return
        
        self.game.hit()
        data, account = get_account(interaction.user.id)
        await self.update_game(interaction, account)
    
    @discord.ui.button(label="🛑 STAND", style=discord.ButtonStyle.secondary, emoji="✋", row=0)
    async def stand_button(self, interaction: discord.Interaction, button: Button):
        if str(interaction.user.id) != self.game.player_id:
            await interaction.response.send_message("❌ This isn't your game!", ephemeral=True)
            return
        
        await interaction.response.defer()
        
        if self.game.game_over:
            await interaction.followup.send("❌ Game is already over!", ephemeral=True)
            return
        
        self.game.stand()
        data, account = get_account(interaction.user.id)
        await self.update_game(interaction, account)
    
    @discord.ui.button(label="🏃 FORFEIT", style=discord.ButtonStyle.danger, emoji="❌", row=0)
    async def forfeit_button(self, interaction: discord.Interaction, button: Button):
        if str(interaction.user.id) != self.game.player_id:
            await interaction.response.send_message("❌ This isn't your game!", ephemeral=True)
            return
        
        await interaction.response.defer()
        
        self.game.game_over = True
        self.game.result = "forfeit"
        self.game.payout = 0
        
        data, account = get_account(interaction.user.id)
        embed = self.game.create_embed(interaction, account)
        await interaction.followup.edit_message(embed=embed, view=None)
        
        ACTIVE_BLACKJACK_GAMES.pop(self.game.player_id, None)
        await interaction.followup.send("🏃 You forfeited the game.", ephemeral=True)

class BlackjackStartView(View):
    def __init__(self):
        super().__init__(timeout=60)
    
    @discord.ui.button(label="💰 PLACE BET", style=discord.ButtonStyle.success, emoji="🎰", row=0)
    async def place_bet(self, interaction: discord.Interaction, button: Button):
        modal = BlackjackBetModal()
        await interaction.response.send_modal(modal)
    
    @discord.ui.button(label="❌ CANCEL", style=discord.ButtonStyle.danger, emoji="✖️", row=0)
    async def cancel(self, interaction: discord.Interaction, button: Button):
        await interaction.response.edit_message(content="❌ Blackjack cancelled.", embed=None, view=None)

@bot.tree.command(name="blackjack", description="🎰 Play blackjack against the dealer!", guild=guild)
async def blackjack(interaction: discord.Interaction):
    await interaction.response.defer()
    
    user_id = str(interaction.user.id)
    
    if user_id in ACTIVE_BLACKJACK_GAMES:
        await interaction.followup.send(
            "❌ You already have an active blackjack game! Finish that one first.",
            ephemeral=True
        )
        return
    
    data, account = get_account(interaction.user.id)
    
    # Create a temporary game just for the embed
    temp_game = BlackjackGame(interaction.user.id, 0)
    embed = discord.Embed(
        title="🎰 **BLACKJACK** 🎰",
        color=discord.Color.blue(),
        description="Welcome to Blackjack! Click PLACE BET to start."
    )
    embed.add_field(name="👤 Player", value=interaction.user.mention, inline=True)
    embed.add_field(name="💰 Balance", value=f"{account['balance']} PNG", inline=True)
    embed.add_field(name="📋 Rules", value="• Get as close to 21 as possible\n• Dealer stands on 17\n• Blackjack pays 3:2", inline=False)
    
    view = BlackjackStartView()
    await interaction.followup.send(embed=embed, view=view)

@tasks.loop(minutes=5)
async def cleanup_blackjack_games():
    """Clean up finished games"""
    to_remove = []
    for user_id, game in ACTIVE_BLACKJACK_GAMES.items():
        if game.game_over:
            to_remove.append(user_id)
    
    for user_id in to_remove:
        ACTIVE_BLACKJACK_GAMES.pop(user_id, None)
        print(f"🧹 Cleaned up blackjack game for {user_id}")
        
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

def number_to_emoji(num):
    """Convert number to emoji"""
    emoji_map = {
        0: "0️⃣", 1: "1️⃣", 2: "2️⃣", 3: "3️⃣", 4: "4️⃣", 5: "5️⃣", 6: "6️⃣", 7: "7️⃣", 8: "8️⃣", 9: "9️⃣",
        10: "🔟", 11: "1️⃣1️⃣", 12: "1️⃣2️⃣", 13: "1️⃣3️⃣", 14: "1️⃣4️⃣", 15: "1️⃣5️⃣", 16: "1️⃣6️⃣",
        17: "1️⃣7️⃣", 18: "1️⃣8️⃣", 19: "1️⃣9️⃣", 20: "2️⃣0️⃣", 21: "2️⃣1️⃣", 22: "2️⃣2️⃣", 23: "2️⃣3️⃣",
        24: "2️⃣4️⃣", 25: "2️⃣5️⃣", 26: "2️⃣6️⃣", 27: "2️⃣7️⃣", 28: "2️⃣8️⃣", 29: "2️⃣9️⃣", 30: "3️⃣0️⃣",
        31: "3️⃣1️⃣", 32: "3️⃣2️⃣", 33: "3️⃣3️⃣", 34: "3️⃣4️⃣", 35: "3️⃣5️⃣", 36: "3️⃣6️⃣", "00": "0️⃣0️⃣"
    }
    return emoji_map.get(num, str(num))

def create_spinner_animation(ball_position):
    """Create a roulette wheel spinner with ball at specific position"""
    
    # Define the wheel layout with correct colors
    wheel_segments = [
        ("0", "🟢"), ("32", "🔴"), ("15", "⚫"), ("19", "🔴"), ("4", "⚫"), ("21", "🔴"), ("2", "⚫"), ("25", "🔴"), ("17", "⚫"), ("34", "🔴"),
        ("6", "⚫"), ("27", "🔴"), ("13", "⚫"), ("36", "🔴"), ("11", "⚫"), ("30", "🔴"), ("8", "⚫"), ("23", "🔴"), ("10", "⚫"), ("5", "🔴"),
        ("24", "⚫"), ("16", "🔴"), ("33", "⚫"), ("1", "🔴"), ("20", "⚫"), ("14", "🔴"), ("31", "⚫"), ("9", "🔴"), ("22", "⚫"), ("18", "🔴"),
        ("29", "⚫"), ("7", "🔴"), ("28", "⚫"), ("12", "🔴"), ("35", "⚫"), ("3", "🔴"), ("26", "⚫"), ("00", "🟢")
    ]
    
    # Create a visual wheel with ball at current position
    wheel = []
    for i, (num, color) in enumerate(wheel_segments):
        if i == ball_position % len(wheel_segments):
            wheel.append(f"⚪{number_to_emoji(num)}{color}")  # White ball on this segment
        else:
            wheel.append(f"  {number_to_emoji(num)}{color}")
    
    # Arrange in a circle (visual representation)
    circle = (
        f"```\n"
        f"        {wheel[0]}  {wheel[1]}  {wheel[2]}  {wheel[3]}        \n"
        f"    {wheel[4]}  {wheel[5]}  {wheel[6]}  {wheel[7]}  {wheel[8]}    \n"
        f"  {wheel[9]}  {wheel[10]}  {wheel[11]}  {wheel[12]}  {wheel[13]}  \n"
        f"  {wheel[14]}  {wheel[15]}  {wheel[16]}  {wheel[17]}  {wheel[18]}  \n"
        f"    {wheel[19]}  {wheel[20]}  {wheel[21]}  {wheel[22]}  {wheel[23]}    \n"
        f"        {wheel[24]}  {wheel[25]}  {wheel[26]}  {wheel[27]}        \n"
        f"            {wheel[28]}  {wheel[29]}  {wheel[30]}            \n"
        f"```"
    )
    return circle

def create_roulette_table(result, color):
    """Create a visual roulette table with the result highlighted"""
    
    # Define the roulette layout with correct column arrangement
    col1 = ["3", "6", "9", "12", "15", "18", "21", "24", "27", "30", "33", "36"]
    col2 = ["2", "5", "8", "11", "14", "17", "20", "23", "26", "29", "32", "35"]
    col3 = ["1", "4", "7", "10", "13", "16", "19", "22", "25", "28", "31", "34"]
    
    # Format each column with colors
    col1_display = []
    for n in col1:
        num = int(n)
        color_emoji = "🔴" if num in RED_NUMBERS else "⚫"
        col1_display.append(f"{number_to_emoji(num)}{color_emoji}")
    
    col2_display = []
    for n in col2:
        num = int(n)
        color_emoji = "🔴" if num in RED_NUMBERS else "⚫"
        col2_display.append(f"{number_to_emoji(num)}{color_emoji}")
    
    col3_display = []
    for n in col3:
        num = int(n)
        color_emoji = "🔴" if num in RED_NUMBERS else "⚫"
        col3_display.append(f"{number_to_emoji(num)}{color_emoji}")
    
    # Result display
    if result in [0, "00"]:
        result_display = f"{number_to_emoji(result)} 🟢"
    else:
        color_emoji = "🔴" if color == "red" else "⚫"
        result_display = f"{number_to_emoji(int(result))} {color_emoji}"
    
    # Build the table
    table = (
        f"╔════════════════════════════════════════════════════════════╗\n"
        f"║                       🎯 **RESULT** 🎯                      ║\n"
        f"║                                                           ║\n"
        f"║                    **{result_display}**                      ║\n"
        f"║                                                           ║\n"
        f"╠════════════════════════════════════════════════════════════╣\n"
        f"║  COL 1          COL 2          COL 3                      ║\n"
        f"║  {' '.join(col1_display[:6])}  ║\n"
        f"║  {' '.join(col1_display[6:])}  ║\n"
        f"║  {' '.join(col2_display[:6])}  ║\n"
        f"║  {' '.join(col2_display[6:])}  ║\n"
        f"║  {' '.join(col3_display[:6])}  ║\n"
        f"║  {' '.join(col3_display[6:])}  ║\n"
        f"║                                                           ║\n"
        f"║                    0️⃣        🟢        0️⃣0️⃣                ║\n"
        f"╚════════════════════════════════════════════════════════════╝"
    )
    return table

class BetAmountModal(Modal, title="💰 Place Your Bet"):
    def __init__(self, parent_view, bet_type, bet_choice):
        super().__init__()
        self.parent_view = parent_view
        self.bet_type = bet_type
        self.bet_choice = bet_choice
        
        # Create descriptive label
        if isinstance(bet_choice, list):
            numbers_str = ', '.join(bet_choice)
            bet_name = f"{bet_type.title()} on {numbers_str}"
        else:
            bet_name = f"{bet_type.title()} {bet_choice}"
        
        self.amount = TextInput(
            label=f"Amount for {bet_name}",
            placeholder=f"Min: {MIN_BET_ROULETTE} PNG, Max: {MAX_BET_ROULETTE} PNG",
            required=True
        )
        self.add_item(self.amount)
    
    async def on_submit(self, interaction: discord.Interaction):
        try:
            bet_amount = int(self.amount.value)
            if bet_amount < MIN_BET_ROULETTE or bet_amount > MAX_BET_ROULETTE:
                await interaction.response.send_message(f"❌ Bet must be {MIN_BET_ROULETTE}-{MAX_BET_ROULETTE} PNG!", ephemeral=True)
                return
            await self.parent_view.spin(interaction, self.bet_type, self.bet_choice, bet_amount)
        except ValueError:
            await interaction.response.send_message("❌ Enter a valid number!", ephemeral=True)

class MultiNumberButtonView(View):
    def __init__(self, parent_view, bet_type, required_count):
        super().__init__(timeout=60)
        self.parent_view = parent_view
        self.bet_type = bet_type
        self.required_count = required_count
        self.selected_numbers = []

        # Row 1: 3, 6, 9, 12, 15, 18, 21, 24, 27, 30, 33, 36
        for n in [3, 6, 9, 12, 15, 18, 21, 24, 27, 30, 33, 36]:
            style = discord.ButtonStyle.danger if n in RED_NUMBERS else discord.ButtonStyle.secondary
            btn = Button(label=str(n), style=style, row=0)
            btn.callback = self.make_callback(str(n))
            self.add_item(btn)
        
        # Row 2: 2, 5, 8, 11, 14, 17, 20, 23, 26, 29, 32, 35
        for n in [2, 5, 8, 11, 14, 17, 20, 23, 26, 29, 32, 35]:
            style = discord.ButtonStyle.danger if n in RED_NUMBERS else discord.ButtonStyle.secondary
            btn = Button(label=str(n), style=style, row=1)
            btn.callback = self.make_callback(str(n))
            self.add_item(btn)
        
        # Row 3: 1, 4, 7, 10, 13, 16, 19, 22, 25, 28, 31, 34
        for n in [1, 4, 7, 10, 13, 16, 19, 22, 25, 28, 31, 34]:
            style = discord.ButtonStyle.danger if n in RED_NUMBERS else discord.ButtonStyle.secondary
            btn = Button(label=str(n), style=style, row=2)
            btn.callback = self.make_callback(str(n))
            self.add_item(btn)
        
        # Row 4: 0 and 00
        btn_0 = Button(label="0", style=discord.ButtonStyle.success, row=3)
        btn_0.callback = self.make_callback("0")
        self.add_item(btn_0)
        
        btn_00 = Button(label="00", style=discord.ButtonStyle.success, row=3)
        btn_00.callback = self.make_callback("00")
        self.add_item(btn_00)
        
        # Row 5: Confirm and Cancel
        confirm_btn = Button(label="✅ Confirm & Place Bet", style=discord.ButtonStyle.success, row=4)
        confirm_btn.callback = self.confirm_bet
        self.add_item(confirm_btn)
        
        cancel_btn = Button(label="❌ Cancel", style=discord.ButtonStyle.danger, row=4)
        cancel_btn.callback = self.cancel
        self.add_item(cancel_btn)

    def make_callback(self, number):
        async def callback(interaction: discord.Interaction):
            if number in self.selected_numbers:
                self.selected_numbers.remove(number)
            else:
                if len(self.selected_numbers) < self.required_count:
                    self.selected_numbers.append(number)
                else:
                    await interaction.response.send_message(
                        f"❌ You can only select {self.required_count} numbers!",
                        ephemeral=True
                    )
                    return
            
            # Update display
            if self.selected_numbers:
                selected_display = ', '.join(self.selected_numbers)
                need = self.required_count - len(self.selected_numbers)
                if need == 0:
                    content = f"**✅ Selected:** {selected_display}\n**Press Confirm to place bet!**"
                else:
                    content = f"**Selected:** {selected_display}\n**Need {need} more**"
            else:
                content = f"**Select {self.required_count} numbers**"
            
            await interaction.response.edit_message(content=content, view=self)
        return callback
    
    async def confirm_bet(self, interaction: discord.Interaction):
        if len(self.selected_numbers) != self.required_count:
            await interaction.response.send_message(
                f"❌ You must select exactly {self.required_count} numbers!",
                ephemeral=True
            )
            return
        
        modal = BetAmountModal(self.parent_view, self.bet_type, self.selected_numbers)
        await interaction.response.send_modal(modal)
    
    async def cancel(self, interaction: discord.Interaction):
        await interaction.response.edit_message(content="❌ Bet cancelled.", view=None)

class RouletteView(View):
    def __init__(self, user_id):
        super().__init__(timeout=300)
        self.user_id = str(user_id)
        self.current_bet_amount = None
        self.current_bet_type = None
        self.current_bet_choice = None

    async def spin(self, interaction: discord.Interaction, bet_type=None, bet_choice=None, bet_amount=None):
        await interaction.response.defer()
        data, account = get_account(interaction.user.id)

        # Store bet info
        self.current_bet_amount = bet_amount
        self.current_bet_type = bet_type
        self.current_bet_choice = bet_choice

        if bet_type and bet_amount:
            if account["balance"] < bet_amount:
                await interaction.followup.send("❌ Not enough balance!", ephemeral=True)
                self.current_bet_amount = None
                self.current_bet_type = None
                self.current_bet_choice = None
                return
            account["balance"] -= bet_amount
            save_economy(data)

        # ============ ANIMATION ============
        anim_msg = await interaction.followup.send("🎡 **Spinning the wheel...**")
        
        # Animate the ball
        for i in range(12):
            ball_pos = i * 3
            spinner = create_spinner_animation(ball_pos)
            
            if i < 4:
                status = "**🏀 Ball is spinning...**"
            elif i < 8:
                status = "**🏀⚡ Ball is spinning faster...**"
            else:
                status = "**🏀🎯 Ball is slowing down...**"
            
            await anim_msg.edit(content=f"{spinner}\n\n{status}")
            await asyncio.sleep(0.3)
        
        await asyncio.sleep(0.2)
        
        # ============ GET RESULT ============
        numbers = list(range(37)) + ["00"]
        result = random.choice(numbers)
        color = check_color(result)
        
        # Calculate win/loss
        win = False
        payout = 0
        
        if self.current_bet_type and self.current_bet_amount:
            bet_type = self.current_bet_type
            bet_choice = self.current_bet_choice
            bet_amount = self.current_bet_amount
            
            if bet_type in ["single", "split", "street", "corner", "six_line"]:
                if str(result) in bet_choice:  # bet_choice is a list of strings
                    win = True
                multiplier = BET_TYPES[bet_type]
            elif bet_type == "red_black" and bet_choice.lower() == color:
                win = True
                multiplier = 1
            elif bet_type == "even_odd" and result not in ["0", "00"]:
                if (bet_choice.lower() == "even" and int(result) % 2 == 0) or \
                   (bet_choice.lower() == "odd" and int(result) % 2 == 1):
                    win = True
                multiplier = 1
            elif bet_type == "low_high" and result not in ["0", "00"]:
                if (bet_choice.lower() == "low" and 1 <= int(result) <= 18) or \
                   (bet_choice.lower() == "high" and 19 <= int(result) <= 36):
                    win = True
                multiplier = 1
            elif bet_type == "dozen" and result not in ["0", "00"]:
                dozens = {"1st": range(1, 13), "2nd": range(13, 25), "3rd": range(25, 37)}
                if int(result) in dozens[bet_choice]:
                    win = True
                multiplier = 2
            elif bet_type == "column" and result not in ["0", "00"]:
                columns = {
                    "1st": {1, 4, 7, 10, 13, 16, 19, 22, 25, 28, 31, 34},  # ✅ FIXED
                    "2nd": {2, 5, 8, 11, 14, 17, 20, 23, 26, 29, 32, 35},  # ✅ FIXED
                    "3rd": {3, 6, 9, 12, 15, 18, 21, 24, 27, 30, 33, 36}   # ✅ FIXED
                }
                if int(result) in columns[bet_choice]:
                    win = True
                multiplier = 2

            if win:
                payout = bet_amount * multiplier
                account["balance"] += payout
                account["total_won"] += payout
                outcome_text = f"🎉 **WIN!** +{payout} PNG"
                color_theme = discord.Color.gold()
                save_economy(data)
            else:
                account["total_lost"] += bet_amount
                outcome_text = f"💀 **LOST** -{bet_amount} PNG"
                color_theme = discord.Color.red()
                save_economy(data)
        else:
            outcome_text = "ℹ️ No bet placed"
            color_theme = discord.Color.blue()

        # Update inactivity counter
        if self.user_id in ACTIVE_SESSIONS:
            ACTIVE_SESSIONS[self.user_id]["inactive_rounds"] = 0

        # ============ FINAL EMBED ============
        table = create_roulette_table(result, color)
        
        embed = discord.Embed(
            title="🎡 **ROULETTE RESULT** 🎡",
            color=color_theme,
            description=f"```\n{table}\n```"
        )
        
        # Bet info
        bet_info = f"**{self.current_bet_amount} PNG**" if self.current_bet_amount else "None"
        bet_type_display = self.current_bet_type.replace("_", " ").title() if self.current_bet_type else "-"
        
        if self.current_bet_choice:
            if isinstance(self.current_bet_choice, list):
                bet_choice_display = f" ({', '.join(self.current_bet_choice)})"
            else:
                bet_choice_display = f" ({self.current_bet_choice})"
        else:
            bet_choice_display = ""
        
        embed.add_field(name="👤 Player", value=interaction.user.mention, inline=True)
        embed.add_field(name="💰 Bet", value=bet_info, inline=True)
        embed.add_field(name="🎯 Type", value=f"{bet_type_display}{bet_choice_display}", inline=True)
        embed.add_field(name="📊 Result", value=f"**{result}** • {color.upper()}", inline=True)
        embed.add_field(name="💸 Outcome", value=outcome_text, inline=True)
        embed.add_field(name="💎 Balance", value=f"{account['balance']} PNG", inline=True)
        
        embed.set_footer(text="Click buttons to bet again • Stay or Leave to continue")
        
        # Reset bet for next round
        self.current_bet_amount = None
        self.current_bet_type = None
        self.current_bet_choice = None
        
        await anim_msg.edit(content=None, embed=embed, view=self)

    # ============ BUTTONS ============
    @discord.ui.button(label="🔴 RED", style=discord.ButtonStyle.danger, row=0)
    async def red(self, interaction, button: Button):
        modal = BetAmountModal(self, "red_black", "red")
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="⚫ BLACK", style=discord.ButtonStyle.secondary, row=0)
    async def black(self, interaction, button: Button):
        modal = BetAmountModal(self, "red_black", "black")
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="👥 EVEN", style=discord.ButtonStyle.primary, row=0)
    async def even(self, interaction, button: Button):
        modal = BetAmountModal(self, "even_odd", "even")
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="🥇 ODD", style=discord.ButtonStyle.primary, row=0)
    async def odd(self, interaction, button: Button):
        modal = BetAmountModal(self, "even_odd", "odd")
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="⬇️ LOW (1-18)", style=discord.ButtonStyle.success, row=1)
    async def low(self, interaction, button: Button):
        modal = BetAmountModal(self, "low_high", "low")
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="⬆️ HIGH (19-36)", style=discord.ButtonStyle.success, row=1)
    async def high(self, interaction, button: Button):
        modal = BetAmountModal(self, "low_high", "high")
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="1st 12", style=discord.ButtonStyle.secondary, row=1)
    async def first_dozen(self, interaction, button: Button):
        modal = BetAmountModal(self, "dozen", "1st")
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="2nd 12", style=discord.ButtonStyle.secondary, row=1)
    async def second_dozen(self, interaction, button: Button):
        modal = BetAmountModal(self, "dozen", "2nd")
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="3rd 12", style=discord.ButtonStyle.secondary, row=2)
    async def third_dozen(self, interaction, button: Button):
        modal = BetAmountModal(self, "dozen", "3rd")
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="1st COL", style=discord.ButtonStyle.primary, row=2)
    async def col1(self, interaction, button: Button):
        modal = BetAmountModal(self, "column", "1st")
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="2nd COL", style=discord.ButtonStyle.primary, row=2)
    async def col2(self, interaction, button: Button):
        modal = BetAmountModal(self, "column", "2nd")
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="3rd COL", style=discord.ButtonStyle.primary, row=2)
    async def col3(self, interaction, button: Button):
        modal = BetAmountModal(self, "column", "3rd")
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="🎯 SINGLE", style=discord.ButtonStyle.danger, row=3)
    async def single(self, interaction, button: Button):
        await interaction.response.send_message(
            "**Select 1 number:**", 
            ephemeral=True, 
            view=MultiNumberButtonView(self, "single", 1)
        )

    @discord.ui.button(label="🔀 SPLIT", style=discord.ButtonStyle.secondary, row=3)
    async def split(self, interaction, button: Button):
        await interaction.response.send_message(
            "**Select 2 numbers:**", 
            ephemeral=True, 
            view=MultiNumberButtonView(self, "split", 2)
        )

    @discord.ui.button(label="📊 STREET", style=discord.ButtonStyle.secondary, row=3)
    async def street(self, interaction, button: Button):
        await interaction.response.send_message(
            "**Select 3 numbers:**", 
            ephemeral=True, 
            view=MultiNumberButtonView(self, "street", 3)
        )

    @discord.ui.button(label="🔲 CORNER", style=discord.ButtonStyle.secondary, row=4)
    async def corner(self, interaction, button: Button):
        await interaction.response.send_message(
            "**Select 4 numbers:**", 
            ephemeral=True, 
            view=MultiNumberButtonView(self, "corner", 4)
        )

    @discord.ui.button(label="📏 SIX-LINE", style=discord.ButtonStyle.secondary, row=4)
    async def six_line(self, interaction, button: Button):
        await interaction.response.send_message(
            "**Select 6 numbers:**", 
            ephemeral=True, 
            view=MultiNumberButtonView(self, "six_line", 6)
        )

    @discord.ui.button(label="🛑 STAY", style=discord.ButtonStyle.primary, row=4)
    async def stay(self, interaction, button: Button):
        if self.user_id in ACTIVE_SESSIONS:
            ACTIVE_SESSIONS[self.user_id]["inactive_rounds"] = 0
        await interaction.response.send_message("👍 Staying at the table!", ephemeral=True)

    @discord.ui.button(label="🚪 LEAVE", style=discord.ButtonStyle.danger, row=4)
    async def leave(self, interaction, button: Button):
        ACTIVE_SESSIONS.pop(self.user_id, None)
        await interaction.response.send_message("👋 You left the table. Come back anytime!", ephemeral=True)
        self.stop()

@bot.tree.command(name="roulette", description="🎡 Join the roulette table and place your bets!", guild=guild)
async def roulette_cmd(interaction: discord.Interaction):
    await interaction.response.defer()
    user_id = str(interaction.user.id)
    
    if user_id not in ACTIVE_SESSIONS:
        ACTIVE_SESSIONS[user_id] = {"inactive_rounds": 0}
    
    data, account = get_account(interaction.user.id)
    
    embed = discord.Embed(
        title="🎡 **PNG CASINO - ROULETTE** 🎡",
        color=discord.Color.green(),
        description=(
            "```\n"
            "╔════════════════════════════════════════╗\n"
            "║     Welcome to the Roulette Table!     ║\n"
            "║    Click buttons below to place bets   ║\n"
            "╚════════════════════════════════════════╝\n"
            "```"
        )
    )
    
    embed.add_field(name="👤 Player", value=interaction.user.mention, inline=True)
    embed.add_field(name="💰 Balance", value=f"{account['balance']} PNG", inline=True)
    embed.add_field(name="🎯 Min Bet", value=f"{MIN_BET_ROULETTE} PNG", inline=True)
    
    payouts = (
        "**Single:** 35x\n"
        "**Split:** 17x\n"
        "**Street:** 11x\n"
        "**Corner:** 8x\n"
        "**Six-line:** 5x\n"
        "**Column/Dozen:** 2x\n"
        "**Red/Black/Even/Odd/Low/High:** 1x"
    )
    embed.add_field(name="💰 Payouts", value=payouts, inline=False)
    
    embed.set_footer(text="Place your bets and watch the wheel spin! 🎡")
    
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
        print(f"👋 Removed inactive roulette player {user_id}")

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

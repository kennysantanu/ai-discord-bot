import os
import datetime
import pytz
import sqlite3
import discord
from discord.ext import commands, tasks
from discord import app_commands

TIME_ZONE = os.getenv('TIME_ZONE') or 'Etc/UTC'
INITIAL_STOCK_PRICE = int(os.getenv('INITIAL_STOCK_PRICE', 100))
NEW_MEMBER_POINTS = int(os.getenv('NEW_MEMBER_POINTS', 0))
NEW_MEMBER_STOCKS = int(os.getenv('NEW_MEMBER_STOCKS', 0))

class Economy(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.database = sqlite3.connect("database/economy.db", check_same_thread=False)
        self.daily_event.start()

    stock_commands = app_commands.Group(name="stock", description="Stock market commands")

    @commands.Cog.listener()
    async def on_ready(self):
        self.setup_database()
        print("Economy cog loaded")

    @tasks.loop(
        time=datetime.time(
            hour=0, 
            minute=0, 
            tzinfo=datetime.timezone(
                datetime.timedelta(
                    hours=datetime.datetime.now(pytz.timezone(TIME_ZONE)).utcoffset().total_seconds() / 3600
                )
            )
        )
    )
    async def daily_event(self):
        print("### Economy daily event at", datetime.datetime.now().astimezone(pytz.timezone(TIME_ZONE)), "###")
        print("Current stock price:", self.get_current_stock_price())
        await self.update_stock_price()
        print("New stock price:", self.get_current_stock_price())

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot:
            return
        
        if not self.registered_in_guild(message.author):
            self.register_member(message.author)
            self.add_user_points(message.author.id, message.guild.id, NEW_MEMBER_POINTS)
            self.set_user_stocks(message.author.id, NEW_MEMBER_STOCKS)

        user_id = message.author.id
        guild_id = message.guild.id

        self.record_user_activity(user_id, guild_id, "message", 1)
        self.add_user_points(user_id, guild_id, 1)

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent):
        if payload.member.bot:
            return
        
        if not self.registered_in_guild(payload.member):
            self.register_member(payload.member)
            self.add_user_points(payload.member.id, payload.member.guild.id, NEW_MEMBER_POINTS)
            self.set_user_stocks(payload.member.id, NEW_MEMBER_STOCKS)

        user_id = payload.user_id
        guild_id = payload.guild_id

        self.record_user_activity(user_id, guild_id, "reaction_add", 1)
        self.add_user_points(user_id, guild_id, 1)

    @commands.Cog.listener()
    async def on_raw_reaction_remove(self, payload: discord.RawReactionActionEvent):

        user_id = payload.user_id
        guild_id = payload.guild_id

        self.record_user_activity(user_id, guild_id, "reaction_remove", -1)
        self.subtract_user_points(user_id, guild_id, 1)

    @app_commands.command(name="leaderboard", description="Shows the server leaderboard of the top 10 members with the most points")
    async def leaderboard(self, interaction: discord.Interaction):
        embed = discord.Embed(title="Economy Leaderboard", description=f"In {interaction.guild.name}", color=discord.Color.gold())
        embed.set_thumbnail(url=interaction.guild.icon.url)

        cursor = self.database.cursor()
        cursor.execute("SELECT user_id, points FROM user WHERE guild_id=? ORDER BY points DESC LIMIT 10", (interaction.guild.id,))
        leaderboard = cursor.fetchall()
        cursor.close()
        
        top_members = ""
        for i, (user_id, points) in enumerate(leaderboard):
            member = interaction.guild.get_member(user_id)
            top_members += f"{i + 1}. {member.display_name} ({points} points)" + "\n"
            
        embed.add_field(name="Top 10 Members", value=top_members, inline=False)
        
        await interaction.response.send_message(embed=embed)

    @stock_commands.command(name="price", description="Get the current stock price")
    async def price(self, interaction: discord.Interaction):
        price = self.get_current_stock_price()
        embed = discord.Embed(title="Stock Price", description=f"The current stock price is {price} points", color=discord.Color.dark_green())
        await interaction.response.send_message(embed=embed)

    def setup_database(self):
        cursor = self.database.cursor()
        with open("cogs/economy.sql", "r") as file:
            cursor.executescript(file.read())
            self.database.commit()

        # If stock table is empty, insert initial stock price
        cursor.execute("SELECT COUNT(*) FROM stock")
        if cursor.fetchone()[0] == 0:
            cursor.execute("INSERT INTO stock (timestamp, price) VALUES (?, ?)", (datetime.datetime.now().isoformat(), INITIAL_STOCK_PRICE))
            self.database.commit()

        cursor.close()

    def register_member(self, member: discord.Member):
        cursor = self.database.cursor()
        cursor.execute("INSERT INTO user (user_id, guild_id, name, points, stocks) VALUES (?, ?, ?, ?, ?)", (member.id, member.guild.id, member.name, 0, 0))
        self.database.commit()
        cursor.close()

    def registered_in_guild(self, member: discord.Member):
        cursor = self.database.cursor()
        cursor.execute("SELECT COUNT(*) FROM user WHERE user_id=? AND guild_id=?", (member.id, member.guild.id))
        count = cursor.fetchone()[0]
        cursor.close()
        return count > 0

    def get_member_info(self, member: discord.Member):
        cursor = self.database.cursor()
        cursor.execute("SELECT * FROM user WHERE user_id=?", (member.id,))
        member_info = cursor.fetchone()

        if member_info is None:
            self.register_member(member)
            cursor.execute("SELECT * FROM user WHERE user_id=?", (member.id,))
            member_info = cursor.fetchone()

        cursor.close()
        return member_info

    def add_user_points(self, user_id: int, guild_id: int, points: int):
        cursor = self.database.cursor()
        cursor.execute("UPDATE user SET points = points + ? WHERE user_id = ? AND guild_id = ?", (points, user_id, guild_id))
        self.database.commit()
        cursor.close()

    def subtract_user_points(self, user_id: int, guild_id: int, points: int):
        cursor = self.database.cursor()
        cursor.execute("UPDATE user SET points = points - ? WHERE user_id = ? AND guild_id = ?", (points, user_id, guild_id))
        self.database.commit()
        cursor.close()

    def set_user_stocks(self, user_id: int, stocks: int):
        cursor = self.database.cursor()
        cursor.execute("UPDATE user SET stocks=? WHERE user_id=?", (stocks, user_id))
        self.database.commit()
        cursor.close()

    def record_user_activity(self, user_id: int, guild_id: int, activity_type: str, amount: int):
        cursor = self.database.cursor()
        cursor.execute("INSERT INTO activity (timestamp, user_id, guild_id, type, amount) VALUES (?, ?, ?, ?, ?)", (datetime.datetime.now().isoformat(), user_id, guild_id, activity_type, amount))
        self.database.commit()
        cursor.close()

    def get_current_stock_price(self):
        cursor = self.database.cursor()
        cursor.execute("SELECT price FROM stock ORDER BY timestamp DESC LIMIT 1")
        price = cursor.fetchone()[0]
        cursor.close()
        return price
    
    def get_activity_points(self, from_date: datetime.datetime, to_date: datetime.datetime):
        cursor = self.database.cursor()
        cursor.execute("SELECT SUM(amount) FROM activity WHERE timestamp >= ? AND timestamp <= ?", (from_date.isoformat(), to_date.isoformat()))
        points = cursor.fetchone()[0]
        cursor.close()
        return points
    
    def record_stock_price(self, price: int):
        cursor = self.database.cursor()
        cursor.execute("INSERT INTO stock (timestamp, price) VALUES (?, ?)", (datetime.datetime.now().isoformat(), price))
        self.database.commit()
        cursor.close()

    def update_stock_price(self):
        weight = 1
        average_days = 30
        smoothing_factor = 0.1  # Smoothing factor to dampen large fluctuations
        max_adjustment = 0.05  # Maximum adjustment of 5%
        
        current_price = self.get_current_stock_price()
        
        # Calculate activity points
        daily_activity_points = self.get_activity_points(datetime.datetime.now() - datetime.timedelta(days=1), datetime.datetime.now())
        baseline_activity_points = self.get_activity_points(datetime.datetime.now() - datetime.timedelta(days=average_days), datetime.datetime.now())
        
        # Avoid division by zero
        if baseline_activity_points == 0:
            price_adjustment_factor = 1
        else:
            average_daily_points = baseline_activity_points / average_days
            price_adjustment_factor = (daily_activity_points / average_daily_points) * weight
        
        # Apply smoothing factor
        price_adjustment_factor = 1 + smoothing_factor * (price_adjustment_factor - 1)
        
        # Cap adjustments
        price_adjustment_factor = max(1 - max_adjustment, min(1 + max_adjustment, price_adjustment_factor))
        
        # Calculate new price
        new_price = current_price * price_adjustment_factor
        
        # Record new price
        self.record_stock_price(int(new_price))
    
async def setup(bot: commands.Bot):
    await bot.add_cog(Economy(bot))

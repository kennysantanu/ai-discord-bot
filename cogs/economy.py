import os
import io
import random
import datetime
import pytz
import sqlite3
import discord
import logging
import matplotlib.pyplot as plt
from discord.ext import commands, tasks
from discord import app_commands

TIME_ZONE = os.getenv('TIME_ZONE') or 'Etc/UTC'
INITIAL_STOCK_PRICE = int(os.getenv('INITIAL_STOCK_PRICE', 100))
NEW_MEMBER_POINTS = int(os.getenv('NEW_MEMBER_POINTS', 0))
NEW_MEMBER_STOCKS = int(os.getenv('NEW_MEMBER_STOCKS', 0))

logger = logging.getLogger(__name__)

class Economy(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.database = sqlite3.connect("database/economy.db", check_same_thread=False)
        self.setup_database()
        self.daily_event.start()

    stock_commands = app_commands.Group(name="stock", description="Stock market commands")

    @commands.Cog.listener()
    async def on_ready(self):
        logging.info("Economy cog loaded")

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
        logger.info("Economy daily event started")
        logger.info(f"Current stock price: {self.get_current_stock_price()}")
        await self.update_stock_price()
        logger.info(f"New stock price: {self.get_current_stock_price()}")

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

    @app_commands.command(name="gamble", description="Gamble your points")
    @app_commands.describe(points="The amount of points you want to gamble")
    async def gamble(self, interaction: discord.Interaction, points: int = 1):
        def draw_card():
            card = random.randint(1, 13)  # Cards are from 1 to 13 (Ace to King)
            return min(card, 10)
    
        user_id = interaction.user.id
        guild_id = interaction.guild.id

        member_info = self.get_member_info(interaction.user)
        member_points = member_info[3]

        if member_points < points:
            error_embed = discord.Embed(title="Gamble", description=f"You don't have {points} points to gamble", color=discord.Color.red())
            await interaction.response.send_message(embed=error_embed, ephemeral=True)
            return
        
        embed = discord.Embed(title="Gamble", description=f"{interaction.user.display_name} is gambling {points} points", color=discord.Color.gold())
        
        # Deal two cards for Player and Banker
        player_hand = [draw_card(), draw_card()]
        banker_hand = [draw_card(), draw_card()]
        
        player_total = sum(player_hand) % 10
        banker_total = sum(banker_hand) % 10

        embed.add_field(name="Player Hand", value=f"[{player_hand[0]}] [{player_hand[1]}] = ({player_total})", inline=False)
        embed.add_field(name="Banker Hand", value=f"[{banker_hand[0]}] [{banker_hand[1]}] = ({banker_total})", inline=False)
        
        # Determine the winner
        if player_total > banker_total:
            embed.add_field(name="You win!", value=f"You won {points} points!", inline=False)
            self.add_user_points(user_id, guild_id, points)
        elif banker_total > player_total:
            embed.add_field(name="You lose!", value=f"You lost {points} points!", inline=False)
            self.subtract_user_points(user_id, guild_id, points)
        else:
            embed.add_field(name="Its a tie!", value=f"You lost {points} points!", inline=False)
            self.subtract_user_points(user_id, guild_id, points)

        await interaction.response.send_message(embed=embed)

    @stock_commands.command(name="price", description="Get the current stock price")
    async def price(self, interaction: discord.Interaction):
        # Get the current stock price
        current_price = self.get_current_stock_price()

        # Get the stock history
        prices = []
        dates = []
        cursor = self.database.cursor()
        cursor.execute("SELECT timestamp, price FROM stock ORDER BY timestamp ASC")
        for row in cursor.fetchall():
            dates.append(datetime.datetime.strptime(row[0], "%Y-%m-%dT%H:%M:%S.%f").strftime('%m/%d'))
            prices.append(row[1])

        # Generate the chart
        plt.figure(figsize=(10, 5))
        plt.plot(dates, prices, color='green')
        plt.fill_between(dates, prices, color='green', alpha=0.3)
        plt.ylim(min(prices), max(prices))
        plt.xticks(rotation=45)
        plt.title('Stock Price History')
        plt.grid(True)
        plt.tight_layout()

        # Save the chart to a BytesIO object
        buf = io.BytesIO()
        plt.savefig(buf, format='png')
        buf.seek(0)
        plt.close()

        # Create a discord file from the BytesIO object
        file = discord.File(buf, filename="stock_price_chart.png")

        # Create an embed with the current stock price
        embed = discord.Embed(title="Stock Price", description=f"The current stock price is {current_price} points", color=discord.Color.dark_green())
        embed.set_image(url="attachment://stock_price_chart.png")

        # Send the message with the embed and the file
        await interaction.response.send_message(embed=embed, file=file)

    @stock_commands.command(name="buy", description="Buy stocks with your points")
    async def buy(self, interaction: discord.Interaction, amount: int):
        user_id = interaction.user.id
        guild_id = interaction.guild.id

        member_info = self.get_member_info(interaction.user)
        points = member_info[3]
        stocks = member_info[4]

        stock_price = self.get_current_stock_price()
        buy_price = int(stock_price * amount)

        embed = discord.Embed(title="Buy Stocks", color=discord.Color.dark_green())

        if points < buy_price:
            embed.add_field(name="Error", value=f"You don't have enough points to buy {amount} stocks for a total of {buy_price} points", inline=False)
            embed.color = discord.Color.red()
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        self.subtract_user_points(user_id, guild_id, buy_price)
        self.set_user_stocks(user_id, stocks + amount)

        embed.add_field(name="Success", value=f"{interaction.user.display_name} have bought {amount} stocks for {buy_price} points", inline=False)
        await interaction.response.send_message(embed=embed)

    @stock_commands.command(name="sell", description="Sell stocks for points")
    async def sell(self, interaction: discord.Interaction, amount: int):
        user_id = interaction.user.id
        guild_id = interaction.guild.id

        member_info = self.get_member_info(interaction.user)
        stocks = member_info[4]

        stock_price = self.get_current_stock_price()
        sell_price = int(stock_price * amount)

        embed = discord.Embed(title="Sell Stocks", color=discord.Color.red())

        if stocks < amount:
            embed.add_field(name="Error", value=f"You don't have {amount} stocks to sell", inline=False)
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        self.add_user_points(user_id, guild_id, sell_price)
        self.set_user_stocks(user_id, stocks - amount)

        embed.add_field(name="Success", value=f"{interaction.user.display_name} have sold {amount} stocks for {sell_price} points", inline=False)
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

    async def update_stock_price(self):
        WEIGHT = 1
        AVERAGE_DAYS = 30
        SMOOTHING_FACTOR = 0.1  # Smoothing factor to dampen large fluctuations
        MAX_ADJUSTMENT = 0.05  # Maximum adjustment of 5%
        
        current_price = self.get_current_stock_price()

        # Get stock history
        cursor = self.database.cursor()
        cursor.execute("SELECT price FROM stock ORDER BY timestamp ASC LIMIT ?", (AVERAGE_DAYS,))
        stock_prices = cursor.fetchall()
        stock_prices_length = len(stock_prices)
        cursor.close()
        
        daily_activity_points = self.get_activity_points(datetime.datetime.now() - datetime.timedelta(days=1), datetime.datetime.now())
        baseline_activity_points = self.get_activity_points(datetime.datetime.now() - datetime.timedelta(days=min(AVERAGE_DAYS, stock_prices_length)), datetime.datetime.now())        
        
        if daily_activity_points is None:
            daily_activity_points = 1

        if baseline_activity_points is None:
            baseline_activity_points = 1

        # Avoid division by zero
        if baseline_activity_points == 0:
            price_adjustment_factor = 1
        else:
            average_daily_points = baseline_activity_points / min(AVERAGE_DAYS, stock_prices_length)
            price_adjustment_factor = (daily_activity_points / average_daily_points) * WEIGHT
        
        # Apply smoothing factor
        price_adjustment_factor = 1 + SMOOTHING_FACTOR * (price_adjustment_factor - 1)

        # Log information
        logger.info(f"Daily activity points: {daily_activity_points}")
        logger.info(f"Average daily points: {baseline_activity_points}/{min(AVERAGE_DAYS, stock_prices_length)} = {average_daily_points}")
        logger.info(f"Price adjustment factor: {price_adjustment_factor}")

        # Cap adjustments
        price_adjustment_factor = max(1 - MAX_ADJUSTMENT, min(1 + MAX_ADJUSTMENT, price_adjustment_factor))
        
        # Calculate new price
        new_price = current_price * price_adjustment_factor
        
        # Record new price
        self.record_stock_price(int(new_price))
    
async def setup(bot: commands.Bot):
    await bot.add_cog(Economy(bot))

import os
import datetime
import pytz
import sqlite3
import discord
import logging
from discord.ext import commands, tasks

TIME_ZONE = os.getenv('TIME_ZONE') or 'Etc/UTC'
MAX_GENERATION_TOKEN = int(os.getenv('MAX_GENERATION_TOKEN')) or 20

logger = logging.getLogger(__name__)

class Database(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.database = sqlite3.connect("database/database.db")
        self.daily_reset.start()

    def cog_unload(self):
        self.daily_reset.cancel()

    @commands.Cog.listener()
    async def on_ready(self):
        # Create the user table if not exists from database/database_schema.sql
        cursor = self.database.cursor()
        with open("database_schema.sql", "r") as file:
            cursor.executescript(file.read())
            self.database.commit()
        cursor.close()
        logger.info("Database cog loaded")

    @tasks.loop(time=datetime.time(hour=0, minute=0, tzinfo=datetime.timezone(datetime.timedelta(hours=datetime.datetime.now(pytz.timezone(TIME_ZONE)).utcoffset().total_seconds() / 3600))))
    async def daily_reset(self):
        cursor = self.database.cursor()
        cursor.execute("SELECT user_id, generation_token FROM user")
        users = cursor.fetchall()
        for user in users:
            user_id = user[0]
            generation_token = user[1] + 4
            if generation_token > MAX_GENERATION_TOKEN:
                cursor.execute("UPDATE user SET generation_token=? WHERE user_id=?", (MAX_GENERATION_TOKEN, user_id))
            else:
                cursor.execute("UPDATE user SET generation_token=? WHERE user_id=?", (generation_token, user_id))

        self.database.commit()
        cursor.close()
        logger.info("Daily reset completed")

    async def register_user(self, user: discord.User):
        cursor = self.database.cursor()

        # Check if the user already in the database
        cursor.execute("SELECT * FROM user WHERE user_id=?", (user.id,))
        fetched_user = cursor.fetchone()

        if fetched_user is None:
            # Register the user
            cursor.execute("INSERT INTO user (user_id, name, nickname) VALUES (?, ?, ?)", (user.id, user.name, user.display_name))
            self.database.commit()

        cursor.close()

    async def get_generation_token(self, user: discord.User):
        # Register the user if not already registered
        await self.register_user(user)

        # Get the token
        cursor = self.database.cursor()
        cursor.execute("SELECT generation_token FROM user WHERE user_id=?", (user.id,))
        token = cursor.fetchone()[0]        
        cursor.close()
        return token
    
    async def set_generation_token(self, user: discord.User, token: int):
        # Register the user if not already registered
        await self.register_user(user)

        # Set the token
        cursor = self.database.cursor()
        cursor.execute("UPDATE user SET generation_token=? WHERE user_id=?", (token, user.id))
        self.database.commit()
        cursor.close()

async def setup(bot: commands.Bot):
    await bot.add_cog(Database(bot))

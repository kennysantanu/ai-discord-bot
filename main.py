import os
import json
import discord
import asyncio
import logging
from logging.config import dictConfig
from discord.ext import commands

# Load environment variables
TOKEN = os.getenv('DISCORD_TOKEN')
PREFIX = os.getenv('PREFIX') or "!"

# Set up logging
with open('logging_config.json', 'r') as f:
    config = json.load(f)
    dictConfig(config)

logger = logging.getLogger("bot")

# Create a new Discord bot instance
intents = discord.Intents.default()
intents.members = True
intents.message_content = True
bot = commands.Bot(command_prefix=PREFIX, intents=intents)

# On ready event
@bot.event
async def on_ready():
    await bot.tree.sync()
    logger.info(f'We have logged in as {bot.user}')

async def main():
    async with bot:
        # Load extension cogs
        await bot.load_extension('cogs.text_generation')
        await bot.load_extension('cogs.commands')
        await bot.load_extension('cogs.database')
        await bot.load_extension('cogs.economy')
        await bot.load_extension('cogs.image_generation')
        
        # Start the bot
        await bot.start(TOKEN)

if __name__ == "__main__":
    asyncio.run(main())

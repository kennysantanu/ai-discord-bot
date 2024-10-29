import os
import discord
import asyncio
from discord.ext import commands

# Load environment variables
TOKEN = os.getenv('DISCORD_TOKEN')
PREFIX = os.getenv('PREFIX') or "!"

# Create a new Discord bot instance
intents = discord.Intents.default()
intents.members = True
intents.message_content = True
bot = commands.Bot(command_prefix=PREFIX, intents=intents)

# On ready event
@bot.event
async def on_ready():
    await bot.tree.sync()
    print(f'We have logged in as {bot.user}')

async def main():
    async with bot:
        # Load extension cogs
        await bot.load_extension('cogs.image_generation')
        await bot.load_extension('cogs.text_generation')
        await bot.load_extension('cogs.commands')
        await bot.load_extension('cogs.database')
        
        # Start the bot
        await bot.start(TOKEN)

if __name__ == "__main__":
    asyncio.run(main())

import os
import discord
from discord.ext import commands
from discord import app_commands

MAX_GENERATION_TOKEN = os.getenv('MAX_GENERATION_TOKEN') or 20

class Commands(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_ready(self):
        print("Commands cog loaded")

    @app_commands.command(name="profile", description="Shows your profile")
    async def profile(self, interaction: discord.Interaction):
        database = self.bot.get_cog("Database")
        user = interaction.user
        generation_token = await database.get_generation_token(user)
        await interaction.response.send_message(embed=discord.Embed(title=f"{user.display_name}'s Profile", description=f"Generation Token: {generation_token}/{MAX_GENERATION_TOKEN}"))        

async def setup(bot: commands.Bot):
    await bot.add_cog(Commands(bot))

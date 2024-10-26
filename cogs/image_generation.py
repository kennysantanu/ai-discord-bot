import os
import json
import base64
import tempfile
import requests
import discord
from discord.ext import commands
from discord import app_commands

# Load environment variables
stable_diffusion_url = os.getenv('STABLE_DIFFUSION_URL') or "http://localhost:7860"
extra_positive_prompt = os.getenv('POSITIVE_PROMPT') or ""
extra_negative_prompt = os.getenv('NEGATIVE_PROMPT') or ""
styles = [style.strip() for style in os.getenv('STYLES').split(',')] if os.getenv('STYLES') else []
LORAS = json.loads(os.getenv('LORAS')) if os.getenv('LORAS') else {}

class ImageGeneration(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.database = self.bot.get_cog("Database")

    @commands.Cog.listener()
    async def on_ready(self):
        print("ImageGeneration cog loaded") 
        print(f"STABLE_DIFFUSION_URL: {stable_diffusion_url}")
        print(f"EXTRA_POSITIVE_PROMPT: {extra_positive_prompt}")
        print(f"EXTRA_NEGATIVE_PROMPT: {extra_negative_prompt}")
        print(f"STYLES: {styles}")
        print(f"LORAS: {LORAS}")

    @app_commands.command(name="draw", description="Generate an image based on the given text.")
    @app_commands.describe(
        prompt="Describe the image you want to generate."
    )
    async def draw(self, interaction: discord.Interaction, prompt: str):
        print(f'NEW DRAW REQUEST FROM: [{interaction.user.name}] IN [{interaction.channel}]')

        # Check if the user has enough generation tokens
        user = interaction.user
        generation_token = await self.database.get_generation_token(user)
        if generation_token <= 0:
            await interaction.response.send_message("You don't have enough generation tokens.", ephemeral=True)
            return
        
        await interaction.response.defer()

        original_prompt = prompt
        print("PROMPT:", original_prompt)

        # search for LORA key in the prompt and replace with LORA value if found
        for key, value in LORAS.items():
            if key in prompt:
                prompt = prompt.replace(key, value)

        # Load JSON file
        with open('stable_diffusion.json') as f:
            payload = json.load(f)
            payload["prompt"] = prompt + ", " + extra_positive_prompt
            payload["negative_prompt"] = extra_negative_prompt
            payload["styles"] = styles

        # Send the request to the Stable Diffusion API
        response = requests.post(url=f'{stable_diffusion_url}/sdapi/v1/txt2img', json=payload)
        r = response.json()
        print("RESPONSE:", r["info"])

        # Decode and save the image to a temporary file.
        with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as temp_file:
            temp_file.write(base64.b64decode(r['images'][0]))
            temp_file_path = temp_file.name

        # Send the image back to the channel.
        await interaction.followup.send("Here is my drawing of " + original_prompt, files=[discord.File(temp_file_path)])
        await self.database.set_generation_token(user, generation_token - 1)

async def setup(bot: commands.Bot):
    await bot.add_cog(ImageGeneration(bot))

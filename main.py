import os
import json
import requests
import base64
import tempfile
import discord
from discord import app_commands
from discord.ext import commands
from ollama import Client
from datetime import timedelta

token = os.getenv('DISCORD_TOKEN')
ollama_url = os.getenv('OLLAMA_URL')
ollama_model = os.getenv('OLLAMA_MODEL')
stable_diffusion_url = os.getenv('STABLE_DIFFUSION_URL')
extra_positive_prompt = os.getenv('POSITIVE_PROMPT')
extra_negative_prompt = os.getenv('NEGATIVE_PROMPT')
styles = [style.strip() for style in os.getenv('STYLES').split(',')] if os.getenv('STYLES') else []

wake_words = [word.strip() for word in os.getenv('WAKE_WORDS').split(',')] if os.getenv('WAKE_WORDS') else []
history_limit = 32 if os.getenv('HISTORY_LIMIT') == '' else int(os.getenv('HISTORY_LIMIT'))
response_time = 60 if os.getenv('RESPONSE_TIME') == '' else int(os.getenv('RESPONSE_TIME'))

# Create a new Ollama client instance
ollama = Client(host=ollama_url)

# Create a new Discord bot instance
intents = discord.Intents.default()
intents.members = True
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

last_response = {}

@bot.event
async def on_ready():
    await bot.tree.sync()
    print(f'We have logged in as {bot.user}')
    print(f'Ollama URL: {ollama_url}')
    print(f'Model: {ollama_model}')
    print(f'Wake Words: {wake_words}')
    print(f'History Limit: {history_limit}')
    print(f'Response Time: {response_time}')

@bot.tree.command(name="quiet", description="Make the bot stop responding to messages in the current channel.")
async def quiet(interaction: discord.Interaction):
    last_response.pop(interaction.channel.name, None)
    await interaction.response.send_message("I'll be quiet now.")

# Image generation command
@bot.tree.command(name="draw", description="Generate an image based on the given text.")
@app_commands.describe(
    prompt="Describe the image you want to generate."
)
async def draw(interaction: discord.Interaction, prompt: str):

    print(f'NEW DRAW REQUEST FROM: [{interaction.user.name}] IN [{interaction.channel}]')

    # Let the user know that the request is being processed
    await interaction.response.defer()    

    # Load JSON file
    with open('stable-diffusion.json') as f:
        payload = json.load(f)
        payload["prompt"] = prompt + ", " + extra_positive_prompt
        payload["negative_prompt"] = extra_negative_prompt
        payload["styles"] = styles

    print("PROMPT:", prompt)

    # Send the request to the Stable Diffusion API
    response = requests.post(url=f'{stable_diffusion_url}/sdapi/v1/txt2img', json=payload)
    r = response.json()
    print("RESPONSE:", r["info"])

    # Decode and save the image to a temporary file.
    with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as temp_file:
        temp_file.write(base64.b64decode(r['images'][0]))
        temp_file_path = temp_file.name

    # Send the image back to the channel.
    await interaction.followup.send("Here is my drawing of " + prompt, files=[discord.File(temp_file_path)])

@bot.event
async def on_message(message):
    # Ignore messages from the bot itself
    if message.author == bot.user:
        return

    # Ignore messages if the bot is not mentioned, the message does not contain the wake words, and the last response was not recent
    mentioned = bot.user.mentioned_in(message)
    contains_wake_word = any(word in message.content for word in wake_words)
    recent_response = (discord.utils.utcnow() < last_response.get(message.channel.name) + timedelta(seconds=response_time)) if message.channel.name in last_response else False

    if not mentioned and not contains_wake_word and not recent_response:
        return
    
    # Accept new request
    print(f'NEW CHAT REQUEST FROM: [{message.author}] IN [{message.channel}]')

    history = []
    channel = message.channel
    
    # Retrieve the message history of the current channel (limit the number of messages)
    async for msg in channel.history(limit=history_limit):

        if msg.author == bot.user:
            history.insert(0, {
                'role': 'assistant',
                'content': msg.clean_content,
            })
        else:
            history.insert(0, {
                'role': 'user',
                'content': msg.author.display_name + ': ' + msg.clean_content
            })
       
    print("HISTORY: ", history)

    # Send the messages to Ollama
    async with message.channel.typing():
        response = ollama.chat(model=ollama_model, messages=history)
        print("RESPONSE: ", response['message']['content'])

        # Send the response back to the channel
        await message.channel.send(response['message']['content'])
        last_response[message.channel.name] = discord.utils.utcnow()

bot.run(token)

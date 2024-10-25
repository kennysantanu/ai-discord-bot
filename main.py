import os
import json
import math
import requests
import base64
import tempfile
import discord
import asyncio
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

# On ready event
@bot.event
async def on_ready():
    await bot.tree.sync()
    print(f'We have logged in as {bot.user}')
    print(f'Ollama URL: {ollama_url}')
    print(f'Model: {ollama_model}')
    print(f'Wake Words: {wake_words}')
    print(f'History Limit: {history_limit}')
    print(f'Response Time: {response_time}')

## User Interfaces ##

# Split bill view
class SplitBillView(discord.ui.View):
    def __init__(self, interaction: discord.Interaction, people: list, items: list, prices: list, sub_total: float, total: float):
        super().__init__()
        # Initialize variables
        self.interaction = interaction
        self.people = people
        self.items = items
        self.prices = prices
        self.sub_total = sub_total
        self.total = total
        self.data = [] # [{"name": "Item one", "price": 10.0, "people": ["Person One", "Person Two"]}]
        self.person_sub_total = {} # {"Person One": 8.0, "Person Two": 2.0}
        self.person_percentage = {} # {"Person One": 0.8, "Person Two": 0.2}
        self.current_page = 1
        self.max_page = len(self.items)
        self.embed = discord.Embed(title=f"Split Bill Calculator ({self.current_page}/{self.max_page})")

    async def start(self):
        # Initialize the data
        for item, price in zip(self.items, self.prices):
            self.data.append({"name": item, "price": price, "people": []})

        # Populate select options
        self.people_Select.options.clear()
        for person in self.people:
            self.people_Select.add_option(label=person)
        self.people_Select.max_values = len(self.people)

        # Display the view
        await self.interaction.response.send_message(view=self, embed=self.embed)
        await self.update_page()
    
    async def update_page(self):
        # Check if all items have been split
        done = True
        for item in self.data:
            if not item["people"]:
                done = False
                break

        # Update buttons
        if self.current_page == 1:
            self.previous_button.disabled = True
        else:
            self.previous_button.disabled = False

        self.done_button.disabled = not done

        if self.current_page == self.max_page:
            self.next_button.disabled = True
        else:
            self.next_button.disabled = False            

        # Update the page
        self.embed.clear_fields()
        self.embed.title = f"Split Bill Calculator ({self.current_page}/{self.max_page})"
        self.embed.add_field(name=self.data[self.current_page-1]["name"], value=f"${self.data[self.current_page-1]['price']} ({', '.join(self.data[self.current_page-1]['people'])})", inline=False)
        await self.interaction.edit_original_response(view=self, embed=self.embed)

    async def display_result(self):        
        self.embed.clear_fields()
        self.embed.title = f"Split Bill Calculator"

        # Calculate the total amount
        for item in self.data:
            for person in item["people"]:
                self.person_sub_total[person] = self.person_sub_total.get(person, 0) + float(item["price"] / len(item["people"]))

        # Calculate the percentage
        for person in self.people:
            self.person_percentage[person] = self.person_sub_total.get(person, 0) / self.sub_total

        # Display the result
        total = 0
        for person, percentage in self.person_percentage.items():
            share = math.ceil((percentage * self.total) * 100) / 100
            self.embed.add_field(name=person, value=f"${share:.2f} ({percentage * 100:.2f}%)", inline=False)
            total += share
        
        # Calculate total
        self.embed.add_field(name="Total", value=f"${total:.2f}", inline=False)

        self.clear_items()
        await self.interaction.edit_original_response(view=self, embed=self.embed)        
        self.stop()

    @discord.ui.select(cls=discord.ui.Select, options=[], placeholder="Select people to split the item.", row=2)
    async def people_Select(self, interaction: discord.Interaction, select: discord.ui.Select):
        await interaction.response.defer()
        self.data[self.current_page-1]["people"] = self.people_Select.values
        await self.update_page()

    @discord.ui.button(label="<", style=discord.ButtonStyle.primary, row=3)
    async def previous_button(self, interaction:discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        self.current_page -= 1
        await self.update_page()
    
    @discord.ui.button(label="DONE", style=discord.ButtonStyle.green, row=3, disabled=True)
    async def done_button(self, interaction:discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        await self.display_result()

    @discord.ui.button(label=">", style=discord.ButtonStyle.primary, row=3)
    async def next_button(self, interaction:discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        self.current_page += 1
        await self.update_page()

### Commands ###
# Split bill command
@bot.tree.command(name="split", description="Split the bill between people.")
@app_commands.describe(
    people="The list of people to split the bill seperated by commas. Ex: John, Jane, Doe",
    items="The list of items seperated by commas. Ex: Item one, Item two, Item three",
    prices="The list of prices seperated by commas (without $). Ex: 10.0, 15.0, 10.0 (The number of prices must be the same as the number of items!)",
    total="The total amount of the bill after tax, tips, cashback, etc."
)
async def split(interaction: discord.Interaction, people: str, items: str, prices: str, total: float):
    if total <= 0:
        await interaction.response.send_message("The total amount must be greater than zero.", ephemeral=True)
        return
    
    itemList = []
    for item in items.split(","):
        itemList.append(item.strip())
    
    priceList = []
    for price in prices.split(","):
        try:
            float_price = float(price.strip())
            rounded_price = math.ceil(float_price * 100) / 100
            priceList.append(rounded_price)
        except ValueError:
            await interaction.response.send_message("The prices must be valid numbers.", ephemeral=True)
            return
    
    if len(itemList) != len(priceList):
        await interaction.response.send_message("The number of items and prices must be the same.", ephemeral=True)
        return
    
    sub_total = sum(priceList)
    if sub_total <= 0:
        await interaction.response.send_message("The sum of the prices must be greater than zero.", ephemeral=True)
        return
    
    peopleList = []
    for person in people.split(","):
        peopleList.append(person.strip())    

    splitBillView = SplitBillView(interaction, peopleList, itemList, priceList, sub_total, total)
    await splitBillView.start()

# Quiet command
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

async def main():
    async with bot:
        # Load extension cogs
        await bot.load_extension('cogs.database')
        await bot.load_extension('cogs.commands')        
        await bot.start(token)

if __name__ == "__main__":
    asyncio.run(main())

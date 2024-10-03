import os
import discord
from ollama import Client

token = os.getenv('DISCORD_TOKEN')
ollama_url = os.getenv('OLLAMA_URL')
ollama_model = os.getenv('OLLAMA_MODEL')

ollama = Client(host=ollama_url)

intents = discord.Intents.default()
intents.message_content = True

client = discord.Client(intents=intents)

@client.event
async def on_ready():
    print(f'We have logged in as {client.user}')

@client.event
async def on_message(message):
    if message.author == client.user:
        return

    print("Message: ", message.content)

    response = ollama.chat(model=ollama_model, messages=[
        {
            'role': 'user',
            'content': message.content,
        },
    ])

    print(response['message']['content'])
    await message.channel.send("Response: ",response['message']['content'])

client.run(token)

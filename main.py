import os
import discord
from ollama import Client

token = os.getenv('DISCORD_TOKEN')
ollama_url = os.getenv('OLLAMA_URL')
ollama_model = os.getenv('OLLAMA_MODEL')

if os.getenv('HISTORY_LIMIT') == '':
    history_limit = 32
else:
    history_limit = int(os.getenv('HISTORY_LIMIT'))

ollama = Client(host=ollama_url)

intents = discord.Intents.default()
intents.message_content = True

client = discord.Client(intents=intents)

@client.event
async def on_ready():
    print(f'We have logged in as {client.user}')
    print(f'Ollama URL: {ollama_url}')
    print(f'Model: {ollama_model}')

@client.event
async def on_message(message):
    # Ignore messages from the bot itself
    if message.author == client.user:
        return

    # Accept new request
    print(f'NEW REQUEST FROM: [{message.author}] IN [{message.channel}]')

    history = []
    channel = message.channel
    
    # Retrieve the message history of the current channel (limit the number of messages)
    async for msg in channel.history(limit=history_limit):

        if msg.author == client.user:
            history.insert(0, {
                'role': 'assistant',
                'content': msg.content,
            })
        else:
            history.insert(0, {
                'role': 'user',
                'content': msg.author.display_name + ': ' + msg.content
            })
    
    print("HISTORY: ", history)

    # Send the messages to Ollama
    async with message.channel.typing():
        response = ollama.chat(model=ollama_model, messages=history)
        print("RESPONSE: ", response['message']['content'])

        # Send the response back to the channel
        await message.channel.send(response['message']['content'])

client.run(token)

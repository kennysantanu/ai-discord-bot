import os
import discord
from ollama import Client
from datetime import timedelta

token = os.getenv('DISCORD_TOKEN')
ollama_url = os.getenv('OLLAMA_URL')
ollama_model = os.getenv('OLLAMA_MODEL')

wake_words = [word.strip() for word in os.getenv('WAKE_WORDS').split(',')] if os.getenv('WAKE_WORDS') else []
history_limit = 32 if os.getenv('HISTORY_LIMIT') == '' else int(os.getenv('HISTORY_LIMIT'))
response_time = 60 if os.getenv('RESPONSE_TIME') == '' else int(os.getenv('RESPONSE_TIME'))

ollama = Client(host=ollama_url)

intents = discord.Intents.default()
intents.message_content = True

client = discord.Client(intents=intents)

last_response = {}

@client.event
async def on_ready():
    print(f'We have logged in as {client.user}')
    print(f'Ollama URL: {ollama_url}')
    print(f'Model: {ollama_model}')
    print(f'Wake Words: {wake_words}')
    print(f'History Limit: {history_limit}')
    print(f'Response Time: {response_time}')

@client.event
async def on_message(message):
    # Ignore messages from the bot itself
    if message.author == client.user:
        return

    # Ignore messages if the bot is not mentioned, the message does not contain the wake words, and the last response was not recent
    mentioned = client.user.mentioned_in(message)
    contains_wake_word = any(word in message.content for word in wake_words)
    recent_response = (discord.utils.utcnow() < last_response.get(message.channel.name) + timedelta(seconds=response_time)) if message.channel.name in last_response else False

    if not mentioned and not contains_wake_word and not recent_response:
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

client.run(token)

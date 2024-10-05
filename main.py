import os
import discord
from ollama import Client

token = os.getenv('DISCORD_TOKEN')
ollama_url = os.getenv('OLLAMA_URL')
ollama_model = os.getenv('OLLAMA_MODEL')

history_limit = 32 if os.getenv('HISTORY_LIMIT') == '' else int(os.getenv('HISTORY_LIMIT'))
wake_words = [word.strip() for word in os.getenv('WAKE_WORDS').split(',')] if os.getenv('WAKE_WORDS') else []

ollama = Client(host=ollama_url)

intents = discord.Intents.default()
intents.message_content = True

client = discord.Client(intents=intents)

@client.event
async def on_ready():
    print(f'We have logged in as {client.user}')
    print(f'Ollama URL: {ollama_url}')
    print(f'Model: {ollama_model}')
    print(f'History Limit: {history_limit}')
    print(f'Wake Words: {wake_words}')

@client.event
async def on_message(message):
    # Ignore messages from the bot itself
    if message.author == client.user:
        return
    
    # Ignore messages that do not contain bot mention or wake words
    if client.user.mentioned_in(message) is False and any(word in message.content for word in wake_words) is False:
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

client.run(token)
